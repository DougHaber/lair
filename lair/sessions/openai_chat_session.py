"""OpenAI chat session implementation."""

from __future__ import annotations

import datetime
import json
import os
import zoneinfo
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

import openai

import lair
import lair.reporting
from lair.components.history import ChatHistory
from lair.components.tools import ToolSet
from lair.logging import logger

from .base_chat_session import BaseChatSession

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessage, ChatCompletionToolParam
else:
    ChatCompletionMessage = Any  # type: ignore
    ChatCompletionToolParam = Any  # type: ignore


class OpenAIChatSession(BaseChatSession):
    """Chat session that uses the OpenAI API."""

    def __init__(self, *, history: ChatHistory | None = None, tool_set: ToolSet | None = None) -> None:
        """
        Initialize the chat session.

        Args:
            history: Optional history instance. Defaults to a new ``ChatHistory`` instance.
            tool_set: Optional tool set. Defaults to a new ``ToolSet`` instance.

        """
        super().__init__(history=history, tool_set=tool_set)
        self.openai: openai.OpenAI | None = None
        self.recreate_openai_client()

        lair.events.subscribe("config.update", lambda d: self.recreate_openai_client(), instance=self)

    def _get_openai_client(self) -> None:
        """Instantiate the underlying OpenAI client using current configuration."""
        base_url = cast(str | None, lair.config.get("openai.api_base"))
        logger.debug(f"Create OpenAI() client: base_url={base_url}")
        api_key_env = cast(str, lair.config.get("openai.api_key_environment_variable"))
        api_key = os.environ.get(api_key_env) or "none"
        self.openai = openai.OpenAI(api_key=api_key, base_url=base_url)

    def recreate_openai_client(self) -> None:
        """Recreate the OpenAI client when configuration changes."""
        self._get_openai_client()

    def invoke(
        self,
        messages: list[dict[str, Any]] | None = None,
        disable_system_prompt: bool = False,
        **kwargs: object,
    ) -> str:
        """
        Call the underlying model without altering the chat history.

        Args:
            messages: Optional list of messages to send. If ``None``, the current
                chat history is used.
            disable_system_prompt: If ``True``, the system prompt is omitted.
            **kwargs: Additional options passed to the API client. Supported keys:
                ``model`` and ``temperature``.

        Returns:
            str: The model response with surrounding whitespace stripped.

        """
        if messages is None:
            messages = []

            if not disable_system_prompt:
                messages.append({"role": "system", "content": self.get_system_prompt()})

            messages.extend(self.history.get_messages())

        messages_str = self.reporting.messages_to_str(messages)
        self.last_prompt = messages_str

        model_name = cast(str, lair.config.get("model.name"))
        model_override = cast(str | None, kwargs.get("model"))
        if model_override is not None:
            model_name = model_override
        temperature_override = cast(float | None, kwargs.get("temperature"))
        logger.debug(f"OpenAIChatSession(): completions.create(model={model_name}, len(messages)={len(messages)})")
        if self.openai is None:
            raise RuntimeError("OpenAI client is not initialized")
        answer = self.openai.chat.completions.create(
            messages=cast(Any, messages),
            model=model_name,
            temperature=(
                temperature_override
                if temperature_override is not None
                else cast(float | None, lair.config.get("model.temperature"))
            ),
            max_completion_tokens=cast(int | None, lair.config.get("model.max_tokens")),
        )
        content = answer.choices[0].message.content
        return content.strip() if content is not None else ""

    def _process_tool_calls(
        self,
        message: ChatCompletionMessage,
        messages: list[dict[str, Any]],
        tool_messages: list[dict[str, Any]],
    ) -> None:
        """
        Handle tool calls returned by the model.

        Args:
            message: The assistant message containing tool calls.
            messages: The running list of messages sent to the model.
            tool_messages: A collection of tool messages to append to the session.

        """
        message_dict = message.dict()
        if lair.config.get("chat.verbose"):
            self.reporting.assistant_tool_calls(message_dict, show_heading=True)

        messages.append(message_dict)
        tool_messages.append(message_dict)

        for tool_call in message.tool_calls or []:
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

    def invoke_with_tools(
        self,
        messages: list[dict[str, Any]] | None = None,
        disable_system_prompt: bool = False,
        **kwargs: object,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Call the model and process tool calls without altering the chat history.

        Args:
            messages: Optional list of messages to send. If ``None``, the current
                chat history is used.
            disable_system_prompt: If ``True``, the system prompt is omitted.
            **kwargs: Additional options passed to the API client.

        Returns:
            tuple[str, list[dict[str, Any]]]: The response from the model and the
            list of generated tool messages.

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
                "OpenAIChatSession(): completions.create("
                f"model={lair.config.get('model.name')}, len(messages)={len(messages)}), cycle={cycle}"
            )
            message = self._invoke_once(messages)
            if not message.tool_calls:
                self.last_prompt = self.reporting.messages_to_str(messages)
                content = message.content
                return (content.strip() if content is not None else ""), tool_messages

            self._process_tool_calls(message, messages, tool_messages)
            cycle += 1

    def _invoke_once(self, messages: list[dict[str, Any]]) -> ChatCompletionMessage:
        if self.openai is None:
            raise RuntimeError("OpenAI client is not initialized")
        answer = self.openai.chat.completions.create(
            messages=cast(Any, messages),
            model=cast(str, lair.config.get("model.name")),
            temperature=cast(float | None, lair.config.get("model.temperature")),
            max_completion_tokens=cast(int | None, lair.config.get("model.max_tokens")),
            tools=cast(Iterable[ChatCompletionToolParam], self.tool_set.get_definitions()),
        )
        return answer.choices[0].message

    def list_models(self, *, ignore_errors: bool = False) -> list[dict[str, Any]] | None:
        """
        Retrieve a list of available models and their metadata.

        Args:
            ignore_errors: When ``True``, errors are logged and ``None`` is returned
                instead of raising an exception.

        Returns:
            list[dict[str, Any]] | None: A list of model metadata dictionaries or
            ``None`` if an error occurs and ``ignore_errors`` is ``True``.

        Raises:
            Exception: If an error occurs and ``ignore_errors`` is ``False``.

        """
        try:
            models: list[dict[str, Any]] = []
            if self.openai is None:
                raise RuntimeError("OpenAI client is not initialized")
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
                return None
            else:
                raise

        return None
