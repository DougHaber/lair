import abc
import copy
from typing import Union, List, Dict, Any, Optional

import lair
import lair.sessions.serializer
import lair.reporting
import lair.util.prompt_template
from lair.components.history import ChatHistory
from lair.logging import logger  # noqa


class BaseChatSession(abc.ABC):

    @abc.abstractmethod
    def __init__(self, *, history=None, tool_set: lair.components.tools.ToolSet = None):
        """
        Arguments:
           history: History class to provide. Defaults to a new ChatHistory()
           tool_set: ToolSet to use. Defaults to a new ToolSet()
        """
        self.reporting = lair.reporting.Reporting()
        self.last_prompt = None
        self.last_response = None

        self.session_id = None  # Id for session management, provided by SessionManager()
        self.session_alias = None  # Alias string for session management purposes
        self.session_title = None  # Short title for the session

        self.history = history or ChatHistory()
        self.tool_set = tool_set or lair.components.tools.ToolSet()

    @abc.abstractmethod
    def invoke(self, messages: list = None, disable_system_prompt=False):
        """
        Call the underlying model without altering state (no history)

        Returns:
            str: The response for the model
        """
        pass

    @abc.abstractmethod
    def invoke_with_tools(self, messages: list = None, disable_system_prompt=False):
        """
        Call the underlying model without altering state (no history)

        Returns:
            tuple[str, list[dict]]: A tuple containing:
              - str: The response for the model
              - list[dict]: tool call history messages
        """
        pass

    def chat(self, message: Optional[Union[str, List[Dict[str, Any]]]] = None) -> str:
        """
        Adds a message to the chat history, sends a chat completion request, and returns the response.

        Parameters:
            message (str, list, or None): The message to process. This can either be:
                - A string representing a single message,
                - A list following the allowed structure for the content section
                  (e.g., [{'role': 'user', 'content': message}]), or
                - None, which indicates no message was provided.

        Returns:
            str: The response generated by the chat completion request.
        """
        if message:
            if isinstance(message, str):
                self.history.add_message('user', message)
            elif isinstance(message, list):
                self.history.add_messages(message)

        try:
            if lair.config.get('tools.enabled'):
                answer, tool_messages = self.invoke_with_tools()
            else:
                answer = self.invoke()
                tool_messages = None
        except (Exception, KeyboardInterrupt):
            self.history.rollback()
            raise

        self.last_response = answer

        if tool_messages:
            self.history.add_tool_messages(tool_messages)
        self.history.add_message('assistant', answer)
        self.history.commit()

        if self.session_title is None and lair.config.get('session.auto_generate_titles.enabled'):
            self.auto_generate_title()

        return answer

    def auto_generate_title(self):
        if self.history.num_messages() < 2 or not lair.config.get('session.auto_generate_titles.enabled'):
            return None

        user_message = None
        assistant_reply = None
        for message in self.history.get_messages():
            if not user_message and message['role'] == 'user' and message['content']:
                user_message = message['content']
            elif not assistant_reply and message['role'] == 'assistant' and message['content']:
                assistant_reply = message['content']

            if user_message and assistant_reply:
                break

        if not (user_message and assistant_reply):
            logger.debug(f"auto_generate_title(): failed: Could not find a user message and assistant reply  (session={self.session_id})")
            return None

        message = self.invoke(
            disable_system_prompt=True,
            model=lair.config.get('session.auto_generate_titles.model'),
            temperature=lair.config.get('session.auto_generate_titles.temperature'),
            messages=[
                {
                    'role': 'system',
                    'content': lair.util.prompt_template.fill(lair.config.get('session.auto_generate_titles.template')),
                },
                {
                    'role': 'user',
                    'content': f'USER\n{user_message[:128]}\n\nASSISTANT\n{assistant_reply[:128]}',
                }
            ]
        )

        logger.debug(f"auto_generate_title(): session={self.session_id}, title={message}")
        self.session_title = message
        return message

    def get_system_prompt(self):
        return lair.util.prompt_template.fill(lair.config.get('session.system_prompt_template'))

    def save_to_file(self, filename):
        lair.sessions.serializer.save(self, filename)

    def load_from_file(self, filename):
        lair.sessions.serializer.load(self, filename)

    def to_dict(self):
        return lair.sessions.serializer.session_to_dict(self)

    def update_from_dict(self, state):
        return lair.sessions.serializer.update_session_from_dict(self)

    @abc.abstractmethod
    def list_models(self, *, ignore_errors=False):
        """
        Retrieve a list of available models and their metadata.

        This method fetches a list of models using the OpenAI API and returns a
        formatted list of dictionaries containing metadata about each model, such as
        its ID, creation date, object type, and ownership.

        Parameters:
            ignore_errors (bool, optional):
                If True, any exceptions encountered during the retrieval of models
                will be logged at the debug level, and the method will return `None`
                instead of raising the exception. If False, exceptions will be propagated.

        Returns:
            list[dict] | None:
                A list of dictionaries, each representing a model with the following keys:
                - 'id' (str): The model's unique identifier.
                - 'created' (datetime.datetime): The model's creation timestamp in UTC.
                - 'object' (str): The type of object (e.g., "model").
                - 'owned_by' (str): The identifier of the entity that owns the model.

                Returns `None` if an exception occurs and `ignore_errors` is True.

        Raises:
            Exception:
                If an error occurs during model retrieval and `ignore_errors` is False.
        """
        pass

    def new_session(self, preserve_alias=False, preserve_id=False):
        if not preserve_id:
            self.session_id = None
        if not preserve_alias:
            self.session_alias = None

        self.session_title = None
        self.last_prompt = None
        self.last_response = None
        self.history.clear()

    def import_state(self, chat_session):
        """
        Import state from another chat session.
        This is used when switching session types.
        """
        self.session_id = chat_session.session_id
        self.session_alias = chat_session.session_alias
        self.session_title = chat_session.session_title
        self.last_prompt = chat_session.last_prompt
        self.last_response = chat_session.last_response

        self.history = copy.deepcopy(chat_session.history)
        # NOTE: Currently the old sessions tool_set is used instead of a copy.
        #     This might need to be adjusted in the future. The toolset can have multiple
        #     tools and tools can be stateful, so generating a new toolset is non-trivial.
        self.tool_set = chat_session.tool_set
