"""Tools for performing DuckDuckGo web and news searches."""

from collections.abc import Iterable, Mapping
from typing import Any, Callable, cast

import requests
import trafilatura
from ddgs import DDGS  # Duck Duck Go Search

import lair
from lair.components.tools.tool_set import ToolSet
from lair.logging import logger


class SearchTool:
    """Tool for performing web and news searches using DuckDuckGo."""

    name = "search"
    SEARCH_WEB_DEFINITION = {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Perform a DuckDuckGo web search and return extracted text content from the top results. "
                "Each result includes the title, url, and content. The content is truncated to a maximum length."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The search query string."}},
                "required": ["query"],
            },
        },
    }
    SEARCH_NEWS_DEFINITION = {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": (
                "Perform a DuckDuckGo news search and return extracted text content from the top results. "
                "Each result includes the date, title, url, and content. The content is truncated to a maximum length."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The news search query string."}},
                "required": ["query"],
            },
        },
    }

    def __init__(self) -> None:
        """Instantiate the underlying DuckDuckGo search client."""
        self.ddgs = DDGS()

    def add_to_tool_set(self, tool_set: ToolSet) -> None:
        """
        Register the search tools with a :class:`ToolSet` instance.

        Args:
            tool_set: The :class:`ToolSet` to register the tools with.

        """
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="search_web",
            flags=["tools.search.enabled"],
            definition=self.SEARCH_WEB_DEFINITION,
            handler=self.search_web,
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="search_news",
            flags=["tools.search.enabled"],
            definition=self.SEARCH_NEWS_DEFINITION,
            handler=self.search_news,
        )

    def _get_content(self, url: str) -> str:
        """
        Fetch content from a URL and extract readable text.

        Args:
            url: The URL to download.

        Returns:
            The extracted text truncated to ``tools.search.max_length`` characters
            or an empty string if extraction fails.

        """
        max_length = cast(int, lair.config.get("tools.search.max_length"))

        try:
            timeout = cast(float, lair.config.get("tools.search.timeout"))
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()

            text_content = trafilatura.extract(response.text, include_comments=False, include_tables=False)
            if not text_content:
                logger.debug(f"search_tool()._get_content(): Failed to extract content from: {url}")
                return ""

            logger.debug(f"search_tool()._get_content(): Success: {url}")
            return text_content[:max_length] if len(text_content) > max_length else text_content
        except Exception as e:
            # Since failures are expected and handled, this is logged at a debug level
            logger.debug(f"Failed to get content from {url}: {e}")
            return ""

    def search_web(self, query: str) -> dict[str, Any]:
        """
        Perform a DuckDuckGo web search.

        Args:
            query: The search query string.

        Returns:
            A dictionary containing the search results or an ``error`` key on
            failure.

        """
        max_results = cast(int, lair.config.get("tools.search.max_results"))
        try:
            results = self.ddgs.text(query, max_results=max_results * 4)
            return self._filter_results(
                results,
                max_results,
                "href",
                lambda r, c: {"title": r["title"], "url": r["href"], "content": c},
            )
        except Exception as error:
            logger.warning(f"search_web(): Encountered error: {error}")
            return {"error": str(error)}

    def search_news(self, query: str) -> dict[str, Any]:
        """
        Perform a DuckDuckGo news search.

        Args:
            query: The news search query string.

        Returns:
            A dictionary containing the search results or an ``error`` key on
            failure.

        """
        max_results = cast(int, lair.config.get("tools.search.max_results"))

        try:
            results = self.ddgs.news(query, max_results=max_results * 4)
            return self._filter_results(
                results,
                max_results,
                "url",
                lambda r, c: {
                    "date": r["date"],
                    "title": r["title"],
                    "url": r["url"],
                    "content": c,
                },
            )
        except Exception as error:
            logger.warning(f"search_news(): Encountered error: {error}")
            return {"error": str(error)}

    def _filter_results(
        self,
        results: Iterable[Mapping[str, Any]],
        max_results: int,
        url_key: str,
        builder: Callable[[Mapping[str, Any], str], Mapping[str, Any]],
    ) -> dict[str, Any]:
        final_results = []
        for result in results:
            content = self._get_content(result[url_key])
            if not content:
                continue
            final_results.append(builder(result, content))
            if len(final_results) > max_results:
                break

        return {"results": final_results} if final_results else {"error": "Search failed"}
