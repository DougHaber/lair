import duckduckgo_search
import requests
import trafilatura

import lair
from lair.logging import logger


class SearchTool:
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

    def __init__(self):
        self.ddgs = duckduckgo_search.DDGS()

    def add_to_tool_set(self, tool_set):
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

    def _get_content(self, url):
        max_length = lair.config.get("tools.search.max_length")

        try:
            response = requests.get(url, timeout=lair.config.get("tools.search.timeout"))
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

    def search_web(self, query):
        max_results = lair.config.get("tools.search.max_results")

        try:
            results = self.ddgs.text(query, max_results=max_results * 4)
            final_results = []
            for result in results:
                content = self._get_content(result["href"])
                if content:
                    final_results.append({"title": result["title"], "url": result["href"], "content": content})
                    if len(final_results) > max_results:
                        break

            if final_results:
                return {"results": final_results}
            else:
                return {"error": "Search failed"}
        except Exception as error:
            logger.warning(f"search_web(): Encountered error: {error}")
            return {"error": str(error)}

    def search_news(self, query):
        max_results = lair.config.get("tools.search.max_results")

        try:
            results = self.ddgs.news(query, max_results=max_results * 4)
            final_results = []
            for result in results:
                content = self._get_content(result["url"])
                if content:
                    final_results.append(
                        {"date": result["date"], "title": result["title"], "url": result["url"], "content": content}
                    )
                if len(final_results) > max_results:
                    break

            if final_results:
                return {"results": final_results}
            else:
                return {"error": "Search failed"}
        except Exception as error:
            logger.warning(f"search_news(): Encountered error: {error}")
            return {"error": str(error)}
