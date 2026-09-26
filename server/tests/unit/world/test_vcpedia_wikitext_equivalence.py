"""迁移等价回归：解析产出必须与迁移前的固定期望一致。

每条样例给出同一页面的人工配对 wikitext 源码、渲染 HTML 与期望产出。期望值是迁移前
HTML 实现（`VCPediaFetcher._parse_page`）在这些样例上的产出，一次性固化在这里，测试本身
不依赖 git 历史或已删除的实现。样例是人工配对，不是真实站点采样。
"""

from __future__ import annotations

import pytest

from src.world.get_new_songs.wikitext_parser import parse_details, parse_song_titles

TITLE = "固定样例"

# (wikitext 源码, 同一页面的渲染 HTML, 迁移前实现的产出)
SAMPLES = [
    (
        "{{VOCALOID_Songbox|演唱=洛天依|image=cover.jpg|width=300|style=red}}\n== 简介 ==\n人物正文。",
        '<table class="moe-infobox infobox"><tr><td>演唱</td><td>洛天依</td></tr></table>'
        "<h2>简介</h2><p>人物正文。</p>",
        {"type": "Person", "infobox": {"演唱": "洛天依"}, "summary": ["人物正文。"], "lyrics": "", "spaced_lyrics": ""},
    ),
    (
        "== 简介 ==\n正文。\n{{创作者名单|group1=PV|list1=作者}}\n=== 背景 ===\n不可追加\n"
        "== 歌词 ==\n<poem>散文<span>第一句歌词</span><span>第二句歌词（副歌）</span>尾声</poem>\n"
        "<poem>第二版本</poem>",
        "<h2>简介</h2><p>正文。</p><div><table><tr><td>PV</td><td>作者</td></tr></table></div>"
        "<h3>背景</h3><p>不可追加</p><h2>歌词</h2>"
        '<div class="poem"><p>散文<span>第一句歌词</span><span>第二句歌词（副歌）</span>尾声</p></div>'
        '<div class="poem"><p>第二版本</p></div>',
        {
            "type": "Song", "infobox": {"PV": "作者"}, "summary": ["正文。"],
            "lyrics": "第一句歌词 第二句歌词", "spaced_lyrics": "第一句歌词 第二句歌词",
        },
    ),
    (
        "== 简介 ==\n开头。截至现在有123次播放，45次收藏。结尾。\n== 歌词 ==\n普通正文并非poem\n"
        "<poem>甲（副歌）<br/>乙</poem>",
        "<h2>简介</h2><p>开头。截至现在有123次播放，45次收藏。结尾。</p>"
        "<h2>歌词</h2><p>普通正文并非poem</p>"
        '<div class="poem"><p>甲（副歌）<br/>乙</p></div>',
        {
            "type": "Song", "infobox": {}, "summary": ["开头。。结尾。"],
            "lyrics": "甲乙", "spaced_lyrics": "甲乙",
        },
    ),
    (
        "<poem>无标题歌词</poem>\n=== 歌词 ===\n<poem>三级标题</poem>",
        '<div class="poem"><p>无标题歌词</p></div><h3>歌词</h3><div class="poem"><p>三级标题</p></div>',
        {"type": "Person", "infobox": {}, "summary": [], "lyrics": "", "spaced_lyrics": ""},
    ),
    (
        "== 歌词 ==\n<poem>旧版</poem>\n== 新版歌词 ==\n<poem>新版一\n新版二</poem>",
        '<h2>歌词</h2><div class="poem"><p>旧版</p></div>'
        '<h2>新版歌词</h2><div class="poem"><p>新版一\n新版二</p></div>',
        {
            "type": "Song", "infobox": {}, "summary": [""],
            "lyrics": "新版一 新版二", "spaced_lyrics": "新版一 新版二",
        },
    ),
]


@pytest.mark.parametrize("source,html,expected", SAMPLES)
def test_wikitext_parsing_keeps_pre_migration_output(source, html, expected):
    assert parse_details(source, TITLE) == {"name": TITLE, **expected}


@pytest.mark.parametrize("source,html,expected", SAMPLES)
def test_samples_cover_the_documented_result_fields(source, html, expected):
    """期望值本身就覆盖了对外契约的字段集合，避免断言退化成空比较。"""
    assert set(expected) == {"type", "infobox", "summary", "lyrics", "spaced_lyrics"}
    assert any(value for value in expected.values()), "样例必须有实际内容，不能全是空值"


def test_comparison_rejects_a_different_page():
    """确认上面的比对有分辨力：换一页的同名字段必须不同。"""
    first = parse_details(SAMPLES[2][0], TITLE)
    other = parse_details("== 简介 ==\n完全不同的正文。\n== 歌词 ==\n<poem>别的歌词</poem>", TITLE)

    assert first["lyrics"] != other["lyrics"]
    assert first["summary"] != other["summary"]
    assert first["lyrics"], "示例页必须解析出非空歌词，否则断言没有分辨力"


LIST_SOURCE = """{{Navbox|title=[[洛天依]]|group1=[[原创曲]]|list1=
[[真名|显示名*]] [[另一页|显示名]] {{lj|目标|别名}} [[殿堂曲之梦]]
[[Help:说明|说明]] [[歌曲#歌词|锚点]] [[#五月|五月]] [[2026]]
[[Category:歌曲|分类显示]] [[Template:文档|模板显示]] [[普通|首页]]
[https://example.org 外部曲] [[用户:甲]] [[正常曲]]}}"""

LIST_EXPECTED = ["显示名", "别名", "说明", "锚点", "外部曲", "用户:甲", "正常曲"]


def test_template_list_keeps_pre_migration_display_names():
    """列表入口仍产出同一批显示名：顺序、星号剥离与导航链接过滤都不变。"""
    assert parse_song_titles(LIST_SOURCE) == LIST_EXPECTED
