"""迁移前 HTML 解析参照实现，供等价回归在测试期加载。

迁移前的 `VCPediaFetcher` 已删除，这里按需从 git 取回它的两个纯解析方法
（`_parse_page` / `_get_data_from_infobox`）并在隔离命名空间中执行，不导入被删除的模块。
取源点固定为 `LEGACY_COMMIT`，避免参照物随分支漂移。
"""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from bs4 import BeautifulSoup

# 迁移提交 50b12f3 的父提交：迁移前最后一个包含 HTML 解析实现的版本。
LEGACY_COMMIT = "910af44"
LEGACY_PATH = "server/src/world/get_new_songs/vcpedia_fetcher.py"
_METHODS = ("def _get_data_from_infobox", "def _parse_page")
_NEXT_METHOD = "def _save_data"


def _read_legacy_source() -> str:
    """从本地 git 对象库取迁移前文件；不可用时明确失败而不是静默跳过。"""
    result = subprocess.run(
        ["git", "show", f"{LEGACY_COMMIT}:{LEGACY_PATH}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"取迁移前参照实现失败：{result.stderr.strip()}")
    return result.stdout


def _extract_methods(source: str) -> str:
    lines = source.split("\n")
    start = next(i for i, line in enumerate(lines) if line.strip().startswith(_METHODS[0]))
    end = next(i for i, line in enumerate(lines) if i > start and line.strip().startswith(_NEXT_METHOD))
    body = lines[start:end]
    # 去掉方法体尾部的空行，保持缩进不变。
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body)


@lru_cache(maxsize=1)
def legacy_parser_class() -> Any:
    """返回只含两个解析方法的参照类。"""
    methods = _extract_methods(_read_legacy_source())
    namespace: Dict[str, Any] = {
        "re": re,
        "BeautifulSoup": BeautifulSoup,
        "Any": Any,
        "Dict": Dict,
        "List": list,
        "Optional": None,
    }
    code = "class LegacyVCPediaParser:\n" + methods + "\n"
    exec(compile(code, "<legacy_vcpedia_fetcher>", "exec"), namespace)  # noqa: S102 - 固定来源的测试参照物
    return namespace["LegacyVCPediaParser"]


def legacy_parse_page(html: str, title: str) -> Dict[str, Any]:
    """按迁移前的 HTML 解析产出详情字典（不含 short_summary，与 parse_details 对齐）。"""
    return legacy_parser_class()()._parse_page(html, title)  # noqa: SLF001 - 参照实现刻意直调
