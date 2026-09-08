import json
import sys
from pathlib import Path

server_root = str(Path(__file__).resolve().parent.parent.parent)
if server_root not in sys.path:
    sys.path.insert(0, server_root)

import pytest

from src.world.get_new_songs.mediawiki import (
    MediaWikiClient,
    MediaWikiPageNotFoundError,
    MediaWikiRequestError,
    parse_song_titles_from_template,
)


class FakeSession:
    """模拟 MediaWiki API 响应的会话。

    `json_responses` 按请求 URL 的 query 参数返回对应 JSON；未登记的 URL 抛 requests
    风格的连接异常，用于验证 MediaWikiClient 把网络错误转换成 MediaWikiRequestError。
    """

    def __init__(self, responses):
        self.responses = responses
        self.requested_urls = []

    def get(self, url, **kwargs):
        self.requested_urls.append((url, kwargs.get("params") or {}))
        import requests

        query_params = kwargs.get("params") or {}
        for matcher, payload in self.responses:
            if all(query_params.get(key) == value for key, value in matcher.items()):
                resp = requests.Response()
                resp.status_code = 200
                resp._content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                return resp
        raise requests.ConnectionError("network unreachable")


def _api_json(session, params):
    response = session.get("https://vcpedia.cn/api.php", params=params)
    return response.json()


def _query_json(title, *, missing=False):
    page = {"pageid": 1, "ns": 0, "title": title}
    if missing:
        page["missing"] = ""
        return {"batchcomplete": True, "query": {"pages": [page]}}
    page["revisions"] = [
        {"slots": {"main": {"contentmodel": "wikitext", "content": f"== {title} =="}}}
    ]
    return {"batchcomplete": True, "query": {"pages": [page]}}


def _make_client(session):
    return MediaWikiClient("https://vcpedia.cn", session=session)


def test_get_wikitext_returns_main_slot_content():
    session = FakeSession(
        [({"action": "query", "titles": "煌"}, _query_json("煌"))]
    )
    client = _make_client(session)

    text = client.get_wikitext("煌")

    assert text == "== 煌 =="


def test_get_wikitext_uses_revision_params():
    session = FakeSession([({"action": "query", "titles": "煌"}, _query_json("煌"))])
    client = _make_client(session)

    client.get_wikitext("煌")

    requested_params = session.requested_urls[0][1]
    assert requested_params["prop"] == "revisions"
    assert requested_params["rvslots"] == "main"
    assert requested_params["rvprop"] == "content"
    assert requested_params["formatversion"] == "2"


def test_get_wikitext_raises_when_page_missing():
    session = FakeSession([({"action": "query", "titles": "不存在"}, _query_json("不存在", missing=True))])
    client = _make_client(session)

    with pytest.raises(MediaWikiPageNotFoundError):
        client.get_wikitext("不存在")


def test_get_wikitext_raises_request_error_on_network_failure():
    session = FakeSession([])
    client = _make_client(session)

    with pytest.raises(MediaWikiRequestError):
        client.get_wikitext("煌")


TEMPLATE_WIKITEXT = """{{Navbox
|name = 洛天依/2026
|title = 洛天依2026年歌曲
|list1 = {{Navbox|child
| [[煌]]、[[同心锁]]
}}
|list2 = {{Navbox|child
| [[分类:洛天依歌曲]]
| [[Template:文档]]
| [[File:示例.jpg]]
| [[2026年]]、[[2012]]
| {{原创曲}}、{{殿堂曲}}
}}
}}"""


def test_parse_song_titles_keeps_displayed_song_names_in_order():
    titles = parse_song_titles_from_template(TEMPLATE_WIKITEXT)

    assert titles == ["煌", "同心锁"]


def test_parse_song_titles_filters_non_song_links():
    titles = parse_song_titles_from_template(TEMPLATE_WIKITEXT)

    assert "分类:洛天依歌曲" not in titles
    assert "Template:文档" not in titles
    assert "示例.jpg" not in titles
    assert "2026年" not in titles
    assert "2012" not in titles


def test_parse_song_titles_handles_pipe_display_names():
    wikitext = "{{Navbox|[[洛天依/2026|2026年]]、[[同名|]]、[[目标页|显示名]]}}"

    titles = parse_song_titles_from_template(wikitext)

    assert "同名" not in titles
    assert titles == ["显示名"]


def test_parse_song_titles_returns_empty_for_invalid_input():
    assert parse_song_titles_from_template("") == []
    assert parse_song_titles_from_template(None) == []
    assert parse_song_titles_from_template(123) == []
