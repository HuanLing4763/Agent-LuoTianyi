"""首框关联区间：首个外层歌曲框之后、第二个之前的 staff 只补空或缺字段。

正文、标题、空行不会结束区间；首框前和第二框及以后的 staff 不并入。
首框非空字段优先，多 staff 的同名字段采用首个非空值。参数内嵌套歌曲框不计数。
"""

from __future__ import annotations

import pytest

from src.world.get_new_songs.wikitext_parser import parse_details

TITLE = "固定样例"


def test_staff_before_the_first_songbox_is_not_infobox_material():
    source = "{{创作者名单|group1=曲绘|list1=前置作者}}\n{{VOCALOID_Songbox|演唱=洛天依}}\n== 简介 ==\n正文。"

    data = parse_details(source, TITLE)

    assert data["infobox"] == {"演唱": "洛天依"}, "首个歌曲框之前的 staff 不得并入信息框"


@pytest.mark.parametrize("between", ["\n", "\n\n\n", "\n正文。\n", "\n== 简介 ==\n正文。\n=== 背景 ===\n"])
def test_staff_in_first_box_interval_can_cross_prose_and_headings(between):
    source = (
        f"{{{{VOCALOID_Songbox|演唱=洛天依}}}}{between}"
        "{{创作者名单|group1=PV|list1=关联作者}}\n== 歌词 ==\n<poem>歌词</poem>"
    )

    assert parse_details(source, TITLE)["infobox"] == {"演唱": "洛天依", "PV": "关联作者"}


def test_second_outer_box_closes_staff_interval_without_overwriting_first():
    source = """{{创作者名单|曲绘=前置作者}}
{{VOCALOID_Songbox|演唱=洛天依|作曲=首框作者}}
== 简介 ==
正文。
{{创作者名单|PV=关联作者}}
{{VOCALOID_Songbox|演唱=第二歌手|编曲=第二作者|简介={{创作者名单|调教=第二框内作者}}}}
{{创作者名单|曲绘=第二框后作者}}
{{VOCALOID_Songbox|演唱=第三歌手}}
{{创作者名单|作词=第三框后作者}}
"""

    assert parse_details(source, TITLE)["infobox"] == {
        "演唱": "洛天依", "作曲": "首框作者", "PV": "关联作者",
    }


def test_first_box_nonempty_fields_win_and_staff_only_fills_missing_or_empty():
    source = """{{VOCALOID_Songbox|歌手=首框歌手|作曲=首框作曲|PV=|曲绘=}}
{{创作者名单|演唱=staff歌手|作曲=staff作曲|PV=补PV|调教=补调教}}
{{创作者名单|PV=后PV|曲绘=补曲绘}}
"""

    data, needed = parse_details(source, TITLE, with_missing=True)

    assert data["infobox"] == {
        "演唱": "首框歌手", "作曲": "首框作曲", "PV": "补PV", "调教": "补调教", "曲绘": "补曲绘",
    }
    assert needed["infobox"] == []


def test_repeated_staff_keys_and_templates_use_first_nonempty_value():
    source = """{{VOCALOID_Songbox|PV=|调教=}}
{{创作者名单|PV=|PV=首PV|PV=后PV|group1=作曲|list1=|group2=作曲|list2=首作曲|group3=作曲|list3=后作曲}}
{{创作者名单|PV=又一PV|作曲=又一作曲|调教=}}
{{创作者名单|调教=首调教}}
{{创作者名单|调教=后调教}}
"""

    data, needed = parse_details(source, TITLE, with_missing=True)

    assert data["infobox"] == {"PV": "首PV", "作曲": "首作曲", "调教": "首调教"}
    assert needed["infobox"] == []


@pytest.mark.parametrize(
    "nested",
    [
        "{{VOCALOID_Songbox|演唱=内框歌手}}",
        "{{hide|content={{VOCALOID_Songbox|演唱=内框歌手}}}}",
        "<div>{{VOCALOID_Songbox|演唱=内框歌手}}</div>",
        "<section><div>{{hide|content={{VOCALOID_Songbox|演唱=内框歌手}}}}</div></section>",
        "{{hide|title={{VOCALOID_Songbox|演唱=内框歌手}}|content=正文}}",
        "{{Unknown|1=<div>{{hide|content={{VOCALOID_Songbox|演唱=内框歌手}}}}</div>}}",
    ],
)
def test_nested_songboxes_do_not_end_first_box_interval_through_frames(nested):
    source = (
        "{{VOCALOID_Songbox|演唱=首框歌手|简介=" + nested + "}}\n"
        "== 背景 ==\n{{创作者名单|PV=应补入}}\n"
        "{{VOCALOID_Songbox|演唱=二框歌手}}\n{{创作者名单|曲绘=不应补入}}"
    )

    assert parse_details(source, TITLE)["infobox"] == {"演唱": "首框歌手", "PV": "应补入"}


@pytest.mark.parametrize(
    "container",
    ["{{hide|content=BOX}}", "<div>BOX</div>", "<section>{{hide|content=<div>BOX</div>}}</section>"],
)
def test_page_level_containers_keep_outer_box_counting(container):
    first = container.replace("BOX", "{{VOCALOID_Songbox|演唱=首框歌手}}")
    second = container.replace("BOX", "{{VOCALOID_Songbox|演唱=二框歌手}}")
    source = first + "\n{{创作者名单|PV=应补入}}\n" + second + "\n{{创作者名单|曲绘=不应补入}}"

    assert parse_details(source, TITLE)["infobox"] == {"演唱": "首框歌手", "PV": "应补入"}


EMPTY_VISIBLE_VALUES = ["<nowiki></nowiki>", "-{}-", " \t ", "<nowiki> \t </nowiki>", "-{ \t }-"]


@pytest.mark.parametrize("value", EMPTY_VISIBLE_VALUES)
@pytest.mark.parametrize("placement", ["songbox", "same_staff", "later_staff"])
def test_staff_precedence_uses_final_visible_emptiness(value, placement):
    source = {
        "songbox": "{{VOCALOID_Songbox|演唱=" + value + "}}{{创作者名单|演唱=关联歌手}}",
        "same_staff": "{{VOCALOID_Songbox}}{{创作者名单|演唱=" + value + "|演唱=关联歌手}}",
        "later_staff": "{{VOCALOID_Songbox}}{{创作者名单|演唱=" + value + "}}{{创作者名单|演唱=关联歌手}}",
    }[placement]

    data, needed = parse_details(source, TITLE, with_missing=True)

    assert data["infobox"] == {"演唱": "关联歌手"}
    assert needed["infobox"] == []


@pytest.mark.parametrize("value", EMPTY_VISIBLE_VALUES)
@pytest.mark.parametrize("placement", ["songbox", "staff"])
def test_visible_empty_field_without_replacement_stays_missing(value, placement):
    source = (
        "{{VOCALOID_Songbox|演唱=" + value + "}}" if placement == "songbox"
        else "{{VOCALOID_Songbox}}{{创作者名单|演唱=" + value + "}}"
    )

    data, needed = parse_details(source, TITLE, with_missing=True)

    assert not data["infobox"].get("演唱", "").strip()
    assert needed["infobox"] == ["演唱"]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("<nowiki>臺灣</nowiki>", "臺灣"),
        ("-{臺灣}-", "臺灣"),
        ("<nowiki>-{}-</nowiki>", "-{}-"),
        ("<nowiki>{{未知模板}}</nowiki>", "{{未知模板}}"),
    ],
)
@pytest.mark.parametrize("placement", ["songbox", "same_staff", "later_staff"])
def test_nonempty_protected_first_value_wins_without_second_conversion(value, expected, placement):
    source = {
        "songbox": "{{VOCALOID_Songbox|演唱=" + value + "}}{{创作者名单|演唱=后歌手}}",
        "same_staff": "{{VOCALOID_Songbox}}{{创作者名单|演唱=" + value + "|演唱=后歌手}}",
        "later_staff": "{{VOCALOID_Songbox}}{{创作者名单|演唱=" + value + "}}{{创作者名单|演唱=后歌手}}",
    }[placement]

    data, needed = parse_details(source, TITLE, with_missing=True)

    assert data["infobox"] == {"演唱": expected}
    assert needed["infobox"] == []


@pytest.mark.parametrize("value", EMPTY_VISIBLE_VALUES)
@pytest.mark.parametrize("with_staff", [False, True])
def test_table_empty_values_remain_missing_or_accept_staff(value, with_staff):
    source = (
        '{{VOCALOID_Songbox}}<table class="moe-infobox infobox">'
        "<tr><td>演唱</td><td>" + value + "</td></tr></table>"
        + ("{{创作者名单|演唱=关联歌手}}" if with_staff else "")
    )

    data, needed = parse_details(source, TITLE, with_missing=True)

    assert data["infobox"].get("演唱", "").strip() == ("关联歌手" if with_staff else "")
    assert needed["infobox"] == ([] if with_staff else ["演唱"])


def test_table_preserves_protected_values_at_single_conversion_boundary():
    source = """{{VOCALOID_Songbox}}
<table class="moe-infobox infobox">
<tr><td>演唱</td><td><nowiki>臺灣</nowiki></td></tr>
<tr><td>作曲</td><td>-{臺灣}-</td></tr>
<tr><td>开放字段</td><td><nowiki>-{}-{{未知}}</nowiki></td></tr>
</table>{{创作者名单|演唱=后歌手|作曲=后作曲}}
"""

    data, needed = parse_details(source, TITLE, with_missing=True)

    assert data["infobox"] == {"演唱": "臺灣", "作曲": "臺灣", "开放字段": "-{}-{{未知}}"}
    assert needed["infobox"] == []
