"""覆盖率回归：两首在等价实现下抽不到歌词的页面，必须能被抽出歌词。

固化的 wikitext 为 VCPedia 真实页面响应（`tests/support/vcpedia_lyrics_recovery.json`）。
这两个页面在迁移前的 HTML 实现下 `lyrics` 为空，属于"陌生格式取不到"的典型；本用例把它们
从"取不到"变成"取得到"，并锁住该行为。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.world.get_new_songs.wikitext_parser import parse_details

FIXTURES = json.loads(
    (Path(__file__).resolve().parents[2] / "support" / "vcpedia_lyrics_recovery.json").read_text(encoding="utf-8")
)

# 迁移前实现下 lyrics 为空的页面
RECOVERED = ["乐鸣东方", "人是猫"]


@pytest.mark.parametrize("title", RECOVERED)
def test_page_without_lyrics_before_now_yields_lyrics(title):
    data = parse_details(FIXTURES[title], title)

    assert data["type"] == "Song"
    assert str(data["lyrics"]).strip(), f"{title} 的歌词仍为空"


def test_recovered_pages_keep_a_searchable_lyric_line():
    """恢复出的歌词要包含可检索的完整行，而不是零散字符。"""
    data = parse_details(FIXTURES["乐鸣东方"], "乐鸣东方")
    lines = [line.strip() for line in str(data["lyrics"]).splitlines() if line.strip()]

    assert len(lines) >= 8, f"歌词行数过少：{len(lines)}"
    assert any(len(line) >= 6 for line in lines), "没有长度足够的完整行可供检索"
