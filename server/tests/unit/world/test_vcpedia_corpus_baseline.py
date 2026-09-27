"""语料触发行为基线：26 页冻结页面上的抽取结果必须与记录基线一致。

冻结源码是确定性输入；本测试固化当前实现的逐页产出（类型、歌词长度、简介、缺口旗标），
任何改动若使某页的歌词回退、缺口误报或漏报，这里会先红。基线由
``scripts/vcpedia_freeze_corpus.py`` 生成并随语料一起更新。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.world.get_new_songs.wikitext_parser import parse_details

CORPUS = Path(__file__).resolve().parents[2] / "support" / "vcpedia_corpus"
META = json.loads((CORPUS / "meta.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("title", sorted(META))
def test_corpus_page_matches_recorded_baseline(title):
    entry = META[title]
    source = (CORPUS / entry["file"]).read_text(encoding="utf-8")

    data, needed = parse_details(source, title, with_missing=True)

    assert data["type"] == entry["baseline"]["type"]
    assert len(str(data.get("lyrics") or "")) == entry["baseline"]["lyrics_len"]
    assert bool([s for s in (data.get("summary") or []) if s]) == entry["baseline"]["summary_nonempty"]
    assert len(data.get("infobox") or {}) == entry["baseline"]["infobox_n"]
    assert needed == entry["baseline"]["needed"]


def test_corpus_covers_the_trigger_classes():
    """语料必须同时覆盖：无触发、真缺失触发、部分抽取触发——缺一类即失去回归意义。"""
    triggered = [t for t, m in META.items() if m["baseline"]["needed"]["lyrics"]]
    with_lyrics = [t for t, m in META.items() if m["baseline"]["lyrics_len"] > 0]

    assert len(with_lyrics) >= 10, "完整抽取的页面样本不足"
    assert len(triggered) >= 2, "触发补提的页面样本不足（真缺失/部分抽取）"
    assert any(META[t]["baseline"]["lyrics_len"] == 0 for t in triggered), "真缺失触发样本缺失"
    assert any(META[t]["baseline"]["lyrics_len"] > 0 for t in triggered), "部分抽取触发样本缺失"
