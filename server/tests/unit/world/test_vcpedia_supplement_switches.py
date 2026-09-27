"""补提链路的开关与契约：片段合并、模型调用、材料的构造时机。

外部边界替换 HTTP POST 与补提模型；断言的是配置组合下观察到的行为。
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import requests

from src.world.get_new_songs import vcpedia_fetcher as fetcher_module
from src.world.get_new_songs.source_extraction import collect_materials
from src.world.get_new_songs.vcpedia_fetcher import VCPediaFetcher

EMBED_SOURCE = "== 简介 ==\n{{embed|1=可渲染片段}}\n"


def fake_response(payload):
    result = requests.Response()
    result.status_code = 200
    result._content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    result.encoding = "utf-8"
    return result


def fake_post(payload):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return fake_response(payload)

    return post, calls


def needed_summary():
    return {"infobox": [], "summary": True, "lyrics": False}


class FakeExtractionModule:
    """补提模型的替身：记录调用，返回预置答案。"""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    async def generate_response(self, **kwargs):
        self.calls.append(kwargs)
        return self.answer


def test_collect_materials_merges_fragments_when_enabled():
    post, calls = fake_post({"parse": {"text": {"*": "<p>站点渲染的简介内容</p>"}}})
    data = {"summary": []}

    materials = collect_materials(data, needed_summary(), EMBED_SOURCE,
                                  "https://vcpedia.cn", "某歌", post=post, merge_fragments=True)

    assert data["summary"] == ["站点渲染的简介内容"]
    assert len(calls) == 1
    assert materials["text"]


def test_collect_materials_skips_fragments_when_disabled():
    post, calls = fake_post({"parse": {"text": {"*": "<p>不应被请求</p>"}}})
    data = {"summary": []}

    materials = collect_materials(data, needed_summary(), EMBED_SOURCE,
                                  "https://vcpedia.cn", "某歌", post=post, merge_fragments=False)

    assert calls == []
    assert data["summary"] == []
    assert materials["text"], "关闭片段合并后模型材料仍须构造"


def test_collect_materials_does_nothing_without_needs():
    post, calls = fake_post({"parse": {"text": {"*": "<p>x</p>"}}})

    materials = collect_materials({"summary": []}, {"infobox": [], "summary": False, "lyrics": False},
                                  EMBED_SOURCE, "https://vcpedia.cn", "某歌", post=post)

    assert materials == {}
    assert calls == []


def test_fetcher_gates_fragment_merge_by_config(monkeypatch, tmp_path):
    monkeypatch.setattr(fetcher_module, "fetch_wikitext", lambda *a, **k: "== 简介 ==\n正文")
    seen = []
    monkeypatch.setattr(fetcher_module, "collect_materials",
                        lambda *a, **k: seen.append(k.get("merge_fragments")) or {})

    fetcher = fetcher_module.VCPediaFetcher(
        {"activated": True, "use_llm": False, "data_dir": str(tmp_path / "cache"),
         "merge_rendered_fragments": False})
    fetcher.fetch_entity_description("某歌")
    assert seen == [], "片段合并与补提模型全关时，不得进入 collect_materials"

    fetcher_default = fetcher_module.VCPediaFetcher(
        {"activated": True, "use_llm": False, "data_dir": str(tmp_path / "cache2")})
    fetcher_default.fetch_entity_description("某歌")
    assert seen == [True], "默认配置保持片段合并打开"


def test_fetcher_extract_missing_merges_model_answer(monkeypatch, tmp_path):
    fake = FakeExtractionModule(json.dumps({"summary": ["模型补全的简介"]}, ensure_ascii=False))
    monkeypatch.setattr(fetcher_module, "fetch_wikitext", lambda *a, **k: "{{VOCALOID_Songbox|演唱=洛天依}}\n== 简介 ==\n")

    fetcher = fetcher_module.VCPediaFetcher(
        {"activated": True, "use_llm": True, "data_dir": str(tmp_path / "cache")},
        extraction_llm_module=fake)
    data = fetcher.fetch_entity_description("某歌")

    assert len(fake.calls) == 1
    assert json.loads(fake.calls[0]["needed"])["summary"] is True
    assert data["summary"] == ["模型补全的简介"]


def test_fetcher_extract_missing_survives_bad_model_answer(monkeypatch, tmp_path):
    fake = FakeExtractionModule("这不是JSON")
    monkeypatch.setattr(fetcher_module, "fetch_wikitext", lambda *a, **k: "{{VOCALOID_Songbox|演唱=洛天依}}\n== 简介 ==\n")

    fetcher = fetcher_module.VCPediaFetcher(
        {"activated": True, "use_llm": True, "data_dir": str(tmp_path / "cache")},
        extraction_llm_module=fake)
    data = fetcher.fetch_entity_description("某歌")

    # 页面标题下无正文，基抽取产出 [""]；非法模型答案不得替换或合并进结果。
    assert data["summary"] == [""]


def test_fetcher_without_llm_never_calls_model(monkeypatch, tmp_path):
    fake = FakeExtractionModule("{}")
    monkeypatch.setattr(fetcher_module, "fetch_wikitext", lambda *a, **k: "{{VOCALOID_Songbox|演唱=洛天依}}\n== 简介 ==\n")

    fetcher = fetcher_module.VCPediaFetcher(
        {"activated": True, "use_llm": False, "data_dir": str(tmp_path / "cache")},
        extraction_llm_module=fake)
    fetcher.fetch_entity_description("某歌")

    assert fake.calls == [], "use_llm 关闭时不得调用补提模型"
