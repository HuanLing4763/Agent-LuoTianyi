"""规则文件的位置与双副本一致性：源码运行用 server/config，wheel 安装回退包内副本。"""

from __future__ import annotations

from pathlib import Path

from src.world.get_new_songs import template_rules
from src.world.get_new_songs.template_rules import _rules_path


def _source_config() -> Path:
    return Path(__file__).resolve().parents[3] / "config/vcpedia_templates.json"


def test_source_config_takes_priority_in_source_layout():
    assert _source_config().exists(), "源码布局下 server/config 的规则文件必须存在"
    assert _rules_path() == _source_config()


def test_packaged_copy_exists_and_matches_source_config():
    packaged = Path(template_rules.__file__).resolve().parent / "vcpedia_templates.json"

    assert packaged.exists(), "包内副本缺失：wheel 安装将无法加载模板规则"
    assert _source_config().read_text(encoding="utf-8") == packaged.read_text(encoding="utf-8"), (
        "server/config 与包内副本漂移：修改规则时两份必须同步更新"
    )
