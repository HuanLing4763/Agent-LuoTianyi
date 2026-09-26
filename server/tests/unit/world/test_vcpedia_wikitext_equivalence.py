"""迁移等价回归：同一页面的人工配对 HTML 与 wikitext 产出相同详情。

评测断言的是**两个实现之间的关系**，不是照抄一个实现的输出：
左侧是迁移前的 HTML 解析（`tests/support/legacy_vcpedia_parser.py` 从固定 commit 取回），
右侧是新的 wikitext 解析。任一侧单独漂移都会让用例失败。
样例是人工配对，不是真实站点采样。
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from src.world.get_new_songs.wikitext_parser import parse_details, parse_song_titles
from support.legacy_vcpedia_parser import legacy_parse_page

TITLE = "固定样例"

# (wikitext 源码, 同一页面的渲染 HTML)
EQUIVALENT_SAMPLES = [
    (
        "{{VOCALOID_Songbox|演唱=洛天依|image=cover.jpg|width=300|style=red}}\n== 简介 ==\n人物正文。",
        '<table class="moe-infobox infobox"><tr><td>演唱</td><td>洛天依</td></tr></table>'
        "<h2>简介</h2><p>人物正文。</p>",
    ),
    (
        "== 简介 ==\n正文。\n{{创作者名单|group1=PV|list1=作者}}\n=== 背景 ===\n不可追加\n"
        "== 歌词 ==\n<poem>散文<span>第一句歌词</span><span>第二句歌词（副歌）</span>尾声</poem>\n"
        "<poem>第二版本</poem>",
        "<h2>简介</h2><p>正文。</p><div><table><tr><td>PV</td><td>作者</td></tr></table></div>"
        "<h3>背景</h3><p>不可追加</p><h2>歌词</h2>"
        '<div class="poem"><p>散文<span>第一句歌词</span><span>第二句歌词（副歌）</span>尾声</p></div>'
        '<div class="poem"><p>第二版本</p></div>',
    ),
    (
        "== 简介 ==\n开头。截至现在有123次播放，45次收藏。结尾。\n== 歌词 ==\n普通正文并非poem\n"
        "<poem>甲（副歌）<br/>乙</poem>",
        "<h2>简介</h2><p>开头。截至现在有123次播放，45次收藏。结尾。</p>"
        "<h2>歌词</h2><p>普通正文并非poem</p>"
        '<div class="poem"><p>甲（副歌）<br/>乙</p></div>',
    ),
    (
        "<poem>无标题歌词</poem>\n=== 歌词 ===\n<poem>三级标题</poem>",
        '<div class="poem"><p>无标题歌词</p></div><h3>歌词</h3><div class="poem"><p>三级标题</p></div>',
    ),
    (
        "== 歌词 ==\n<poem>旧版</poem>\n== 新版歌词 ==\n<poem>新版一\n新版二</poem>",
        '<h2>歌词</h2><div class="poem"><p>旧版</p></div>'
        '<h2>新版歌词</h2><div class="poem"><p>新版一\n新版二</p></div>',
    ),
]


@pytest.mark.parametrize("source,html", EQUIVALENT_SAMPLES)
def test_wikitext_parsing_matches_legacy_html_output(source, html):
    legacy = legacy_parse_page(html, TITLE)
    current = parse_details(source, TITLE)

    assert current == legacy


@pytest.mark.parametrize("source,html", EQUIVALENT_SAMPLES)
def test_equivalent_samples_keep_documented_fields(source, html):
    """等价之外，结果字段本身就是对外契约的一部分。"""
    assert set(parse_details(source, TITLE)) == {
        "name", "type", "infobox", "summary", "lyrics", "spaced_lyrics",
    }


def test_equivalence_assertions_reject_different_pages():
    """确认上面的比对有分辨力：换成另一页的 HTML 必须不相等，且两侧都不是空结果。"""
    source = "== 歌词 ==\n<poem>甲乙</poem>"
    html = '<h2>歌词</h2><div class="poem"><p>甲乙</p></div>'
    other_page_html = '<h2>歌词</h2><div class="poem"><p>完全不同</p></div>'

    assert parse_details(source, TITLE) == legacy_parse_page(html, TITLE)
    assert parse_details(source, TITLE) != legacy_parse_page(other_page_html, TITLE)
    # 参照实现确实解析出了内容，比对不是两个空结果的巧合。
    assert legacy_parse_page(html, TITLE)["lyrics"] == "甲乙"


LIST_SOURCE = """{{Navbox|title=[[洛天依]]|group1=[[原创曲]]|list1=
[[真名|显示名*]] [[另一页|显示名]] {{lj|目标|别名}} [[殿堂曲之梦]]
[[Help:说明|说明]] [[歌曲#歌词|锚点]] [[#五月|五月]] [[2026]]
[[Category:歌曲|分类显示]] [[Template:文档|模板显示]] [[普通|首页]]
[https://example.org 外部曲] [[用户:甲]] [[正常曲]]}}"""

LIST_HTML = """<div id="mw-content-text">
<a href="/洛天依">洛天依</a><a href="/原创曲">原创曲</a>
<a href="/真名">显示名*</a><a href="/另一页">显示名</a><a href="/目标">别名</a>
<a href="/殿堂曲之梦">殿堂曲之梦</a><a href="/Help:说明">说明</a>
<a href="/歌曲#歌词">锚点</a><a href="#五月">五月</a><a href="/2026">2026</a>
<a href="/Category:歌曲">分类显示</a><a href="/Template:文档">模板显示</a>
<a href="/普通">首页</a><a href="https://example.org">外部曲</a>
<a href="/用户:甲">用户:甲</a><a href="/正常曲">正常曲</a></div>"""

LIST_EXPECTED = ["显示名", "别名", "说明", "锚点", "外部曲", "用户:甲", "正常曲"]


def test_template_list_keeps_legacy_display_names():
    """列表入口仍产出同一批显示名（顺序、星号剥离、导航链接过滤保持一致）。"""
    assert parse_song_titles(LIST_SOURCE) == LIST_EXPECTED
    assert legacy_list_texts(LIST_HTML) == LIST_EXPECTED


def legacy_list_texts(html: str) -> list[str]:
    """按迁移前的链接遍历规则复算显示名，作为列表侧的参照。"""
    bad_exact = {
        "原创曲", "非原创曲", "传说曲", "殿堂曲", "部分", "25万以上", "25万以下", "模板文档",
        "查看", "编辑", "历史", "刷新", "简体", "繁體", "大陆简体", "香港繁體", "臺灣正體",
        "不转换", "跳转到导航", "跳转到搜索", "洛天依", "2026", "bilibili", "ACE Studio",
        "X studio", "VOCALOID中文殿堂曲", "ACE殿堂曲", "文档", "嵌入",
    }
    bad_contains = ["Template:", "模板:", "分类:", "Category:", "帮助", "首页", "随机页面", "最近更改", "殿堂曲", "传说曲"]
    blocked_href = ("action=", "Template:", "Category:", "分类:")

    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", id="mw-content-text") or soup
    seen: set[str] = set()
    songs: list[str] = []
    for anchor in content.find_all("a"):
        text = anchor.get_text(strip=True)
        href = anchor.get("href", "") or ""
        if not text or text in bad_exact or any(marker in text for marker in bad_contains) or text.isdigit():
            continue
        if not href or href.startswith("#") or any(marker in href for marker in blocked_href):
            continue
        text = text.rstrip("*").strip()
        if text and text not in seen:
            seen.add(text)
            songs.append(text)
    return songs
