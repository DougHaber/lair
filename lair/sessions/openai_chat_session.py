import datetime
import json
import os
import zoneinfo
from typing import Any, Dict, List, Optional, cast

import openai

import lair
import lair.components.tools
import lair.reporting
from lair.logging import logger

from lair.components.history import ChatHistory
from lair.components.tools import ToolSet
from .base_chat_session import BaseChatSession


class OpenAIChatSession(BaseChatSession):
    def __init__(self, *, history: Optional[ChatHistory] = None, tool_set: Optional[ToolSet] = None):
        super().__init__(history=history, tool_set=tool_set)
        self.openai: openai.OpenAI | None = None
        self.recreate_openai_client()

        lair.events.subscribe("config.update", lambda d: self.recreate_openai_client(), instance=self)

    def _get_openai_client(self):
        logger.debug("Create OpenAI() client: base_url=%s" % lair.config.get("openai.api_base"))
        self.openai = openai.OpenAI(
            api_key=os.environ.get(lair.config.get("openai.api_key_environment_variable")) or "none",
            base_url=lair.config.get("openai.api_base"),
        )

    def recreate_openai_client(self):
        self._get_openai_client()

    def invoke(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        disable_system_prompt: bool = False,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        """
        Call the underlying model without altering state (no history)
        """
        if messages is None:
            messages = []

            if not disable_system_prompt:
                messages.append({"role": "system", "content": self.get_system_prompt()})

            messages.extend(self.history.get_messages())

        messages_str = self.reporting.messages_to_str(messages)
        self.last_prompt = messages_str

        model_name = lair.config.get("model.name")
        logger.debug(f"OpenAIChatSession(): completions.create(model={model_name}, len(messages)={len(messages)})")
        assert self.openai is not None
        answer = self.openai.chat.completions.create(
            messages=cast(Any, messages),
            model=model_name,
            temperature=temperature if temperature is not None else lair.config.get("model.temperature"),
            max_completion_tokens=lair.config.get("model.max_tokens"),
        )

        return (answer.choices[0].message.content or "").strip()

    def _process_tool_calls(self, message, messages, tool_messages):
        """Handle tool calls returned by the model."""
        message_dict = message.dict()
        if lair.config.get("chat.verbose"):
            self.reporting.assistant_tool_calls(message_dict, show_heading=True)

        messages.append(message_dict)
        tool_messages.append(message_dict)

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            result = self.tool_set.call_tool(name, arguments, tool_call.id)
            tool_response_messsage = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            }

            if lair.config.get("chat.verbose"):
                self.reporting.tool_message(tool_response_messsage, show_heading=True)
            messages.append(tool_response_messsage)
            tool_messages.append(tool_response_messsage)
            logger.debug(f"Tool result: {tool_response_messsage}")

    def invoke_with_tools(self, messages: Optional[List[Dict[str, Any]]] = None, disable_system_prompt: bool = False):
        """
        Call the underlying model without altering state (no history)

        Returns:
            tuple[str, list[dict]]: A tuple containing:
              - str: The response for the model
              - list[dict]: New messages from assistant & tool responses
        """
        if messages is None:
            messages = []

            if not disable_system_prompt:
                messages.append({"role": "system", "content": self.get_system_prompt()})

            messages.extend(self.history.get_messages())

        tool_messages: list[dict[str, Any]] = []

        cycle = 0
        while True:
            logger.debug(
                "OpenAIChatSession(): completions.create(model=%s, len(messages)=%d), cycle=%d"
                % (lair.config.get("model.name"), len(messages), cycle)
            )
            assert self.openai is not None
            answer = self.openai.chat.completions.create(
                messages=cast(Any, messages),
                model=lair.config.get("model.name"),
                temperature=lair.config.get("model.temperature"),
                max_completion_tokens=lair.config.get("model.max_tokens"),
                tools=self.tool_set.get_definitions(),
            )

            message = answer.choices[0].message
            if message.tool_calls:
                self._process_tool_calls(message, messages, tool_messages)
                cycle += 1
            else:
                self.last_prompt = self.reporting.messages_to_str(messages)

                return (message.content or "").strip(), tool_messages

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
        try:
            models = []
            assert self.openai is not None
            for model in self.openai.models.list():
                models.append(
                    {
                        "id": model.id,
                        "created": datetime.datetime.fromtimestamp(model.created, tz=zoneinfo.ZoneInfo("UTC")),
                        "object": model.object,
                        "owned_by": model.owned_by,
                    }
                )

            return models
        except Exception as error:
            if ignore_errors:
                logger.debug(f"Failed to retrieve models: {error}")
                return
            else:
                raise
