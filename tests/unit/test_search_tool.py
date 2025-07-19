import lair

from lair.components.tools.search_tool import SearchTool


class DummyResponse:
    def __init__(self, text):
        self.text = text
        self.called = False

    def raise_for_status(self):
        self.called = True


def setup_requests(monkeypatch, text):
    resp = DummyResponse(text)

    def fake_get(url, timeout):
        return resp

    monkeypatch.setattr(
        lair.components.tools.search_tool.requests,
        "get",
        fake_get,
        raising=False,
    )
    return resp


def setup_extract(monkeypatch, result):
    def fake_extract(text, include_comments=False, include_tables=False):
        return result

    monkeypatch.setattr(
        lair.components.tools.search_tool.trafilatura,
        "extract",
        fake_extract,
        raising=False,
    )


def make_tool(monkeypatch):
    class DummyDDGS:
        def __init__(self):
            self.params = []

        def text(self, query, max_results):
            self.params.append(("text", query, max_results))
            return []

        def news(self, query, max_results):
            self.params.append(("news", query, max_results))
            return []

    monkeypatch.setattr(lair.components.tools.search_tool.duckduckgo_search, "DDGS", DummyDDGS)
    return SearchTool()


def test_get_content_truncates(monkeypatch):
    lair.config.set("tools.search.max_length", 5, no_event=True)
    lair.config.set("tools.search.timeout", 1, no_event=True)
    setup_extract(monkeypatch, "abcdefghij")
    resp = setup_requests(monkeypatch, "<html>")
    tool = make_tool(monkeypatch)
    result = tool._get_content("http://x")
    assert resp.called and result == "abcde"


def test_get_content_failure(monkeypatch, caplog):
    lair.config.set("tools.search.max_length", 5, no_event=True)
    lair.config.set("tools.search.timeout", 1, no_event=True)
    setup_extract(monkeypatch, "")
    setup_requests(monkeypatch, "<html>")
    tool = make_tool(monkeypatch)
    with caplog.at_level("DEBUG"):
        result = tool._get_content("http://x")
    assert result == "" and "Failed to extract content" in caplog.text


def test_get_content_exception(monkeypatch, caplog):
    lair.config.set("tools.search.max_length", 5, no_event=True)
    lair.config.set("tools.search.timeout", 1, no_event=True)

    def boom(url, timeout):
        raise RuntimeError("bad")

    monkeypatch.setattr(
        lair.components.tools.search_tool.requests,
        "get",
        boom,
        raising=False,
    )
    tool = make_tool(monkeypatch)
    with caplog.at_level("DEBUG"):
        result = tool._get_content("http://x")
    assert result == "" and "Failed to get content" in caplog.text


def test_search_web_success(monkeypatch):
    lair.config.set("tools.search.max_results", 1, no_event=True)
    tool = make_tool(monkeypatch)
    monkeypatch.setattr(SearchTool, "_get_content", lambda self, url: "text")
    ddgs = tool.ddgs

    def text_stub(q, max_results):
        ddgs.params.append(("text", q, max_results))
        return [
            {"title": "A", "href": "url1"},
            {"title": "B", "href": "url2"},
        ]

    ddgs.text = text_stub
    result = tool.search_web("query")
    assert result["results"][0]["title"] == "A"
    assert ("text", "query", 4) in ddgs.params


def test_search_web_error(monkeypatch):
    lair.config.set("tools.search.max_results", 1, no_event=True)
    tool = make_tool(monkeypatch)
    monkeypatch.setattr(SearchTool, "_get_content", lambda self, url: "")
    tool.ddgs.text = lambda q, max_results: []
    assert tool.search_web("q") == {"error": "Search failed"}


def test_search_news_success(monkeypatch):
    lair.config.set("tools.search.max_results", 1, no_event=True)
    tool = make_tool(monkeypatch)
    monkeypatch.setattr(SearchTool, "_get_content", lambda self, url: "content")
    ddgs = tool.ddgs

    def news_stub(q, max_results):
        ddgs.params.append(("news", q, max_results))
        return [
            {"date": "d", "title": "T", "url": "nurl"},
        ]

    ddgs.news = news_stub
    result = tool.search_news("query")
    assert result["results"][0]["date"] == "d"
    assert ("news", "query", 4) in ddgs.params


def test_search_news_exception(monkeypatch):
    lair.config.set("tools.search.max_results", 1, no_event=True)
    tool = make_tool(monkeypatch)

    def raise_exc(q, max_results):
        raise ValueError("nope")

    tool.ddgs.news = raise_exc
    out = tool.search_news("q")
    assert "error" in out and "nope" in out["error"]


def test_search_web_exception(monkeypatch):
    lair.config.set("tools.search.max_results", 1, no_event=True)
    tool = make_tool(monkeypatch)

    def boom(q, max_results):
        raise RuntimeError("fail")

    tool.ddgs.text = boom
    result = tool.search_web("bad")
    assert "fail" in result["error"]


def test_search_news_failure_and_limit(monkeypatch):
    lair.config.set("tools.search.max_results", 1, no_event=True)
    tool = make_tool(monkeypatch)
    calls = []

    def news_stub(q, max_results):
        return [
            {"date": "d1", "title": "t1", "url": "u1"},
            {"date": "d2", "title": "t2", "url": "u2"},
        ]

    monkeypatch.setattr(tool, "_get_content", lambda url: calls.append(url) or "")
    tool.ddgs.news = news_stub
    result = tool.search_news("q")
    assert result == {"error": "Search failed"}
    # When _get_content returns empty, it should still try at most two entries due to limit
    assert len(calls) == 2
