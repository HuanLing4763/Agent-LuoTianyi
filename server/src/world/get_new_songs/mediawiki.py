"""基于 VCPedia MediaWiki API 的只读获取能力（新歌知识）。

本模块逐步替代旧的 HTML 抓取路径：通过标准 MediaWiki API 获取页面 wikitext，
并从「洛天依/年份」模板 wikitext 中解析歌曲名列表。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any, Dict, List

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)

# vcpedia.cn 的反爬策略会拒绝 requests 默认 UA 与常见浏览器 UA（403/567 挑战页），
# 但放行以 curl/ 开头的 UA。优先探测本机真实 curl 版本，探测失败时回退到该常量，
# 而不是无条件宣称一个未必存在的 curl 版本。
_DEFAULT_USER_AGENT = "curl/8.5.0"


def _detect_curl_user_agent() -> str:
    """返回本机 curl 的真实版本标识（如 curl/8.6.0）。

    系统未安装 curl 或取版本失败时返回空串，由调用方决定是否回退常量。
    """
    curl_path = shutil.which("curl") or shutil.which("curl.exe")
    if not curl_path:
        return ""
    try:
        result = subprocess.run(
            [curl_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning(f"探测 curl 版本失败: {exc}")
        return ""
    if result.returncode != 0:
        return ""
    first_line = (result.stdout or "").splitlines()[0] if result.stdout else ""
    if first_line and first_line.split():
        # `curl --version` 首行形如 `curl 8.6.0 (...)`；站点反爬只按 `curl` 前缀放行，
        # 拼接成与真实 curl 网络请求一致的 UA 形式 `curl/<版本>`。
        return f"{first_line.split()[0]}/{first_line.split()[1]}"
    return ""


class MediaWikiRequestError(RuntimeError):
    """MediaWiki API 请求失败：网络错误、超时或非 200 响应。"""


class MediaWikiPageNotFoundError(MediaWikiRequestError):
    """请求的页面不存在（API 返回 missing）。"""


class MediaWikiClient:
    """按页面标题获取 wikitext 的只读客户端。

    `session` 可注入 Fake 会话用于测试，默认使用 requests.Session。
    默认 User-Agent 优先取本机真实 curl 版本；站点反爬会拒绝 requests 默认 UA
    与浏览器 UA，但放行 curl/ 前缀（探测失败时回退到 `_DEFAULT_USER_AGENT`）。
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: int = 20,
        session: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api.php"
        self.timeout_seconds = timeout_seconds
        if session is None:
            session = requests.Session()
            user_agent = _detect_curl_user_agent() or _DEFAULT_USER_AGENT
            session.headers.update({"User-Agent": user_agent})
        self.session = session

    def fetch_json(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """向 MediaWiki API 发起 GET 请求并返回 JSON 响应。

        网络失败、超时或非 200 响应时抛出 MediaWikiRequestError，不自动重试。
        """
        try:
            response = self.session.get(self.api_url, params=params, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.warning(f"MediaWiki API request failed: {exc}")
            raise MediaWikiRequestError(str(exc)) from exc

    def get_wikitext(self, title: str) -> str:
        """返回页面最新版本的 main-slot wikitext 文本。

        页面不存在时抛出 MediaWikiPageNotFoundError。
        """
        payload = self.fetch_json(
            {
                "action": "query",
                "prop": "revisions",
                "titles": title,
                "rvslots": "main",
                "rvprop": "content",
                "formatversion": "2",
                "format": "json",
            }
        )
        pages = ((payload.get("query") or {}).get("pages")) or []
        page = pages[0] if pages else {}
        if page.get("missing") or "revisions" not in page:
            raise MediaWikiPageNotFoundError(f"MediaWiki page not found: {title}")
        try:
            return page["revisions"][0]["slots"]["main"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise MediaWikiRequestError(
                f"MediaWiki response has no wikitext content for {title}"
            ) from exc


def parse_song_titles_from_template(wikitext: str | None) -> List[str]:
    """从「洛天依/年份」导航模板的 wikitext 解析歌曲名列表（按出现顺序）。

    过滤掉分类/模板/媒体/帮助目标、纯数字、年份和导航分组词。
    """
    if not wikitext or not isinstance(wikitext, str):
        return []

    # 过滤词：模板结构词、年份、播放量分组和导航链接文本
    bad_exact = {
        "原创曲", "非原创曲", "传说曲", "殿堂曲", "部分", "25万以上", "25万以下",
        "模板文档", "查看", "编辑", "历史", "刷新",
        "简体", "繁體", "大陆简体", "香港繁體", "臺灣正體", "不转换",
        "跳转到导航", "跳转到搜索",
    }
    year_pattern = re.compile(r"^\d{4}年?$")
    namespace_pattern = re.compile(r"^(分类|Category|模板|Template|File|文件|帮助|Help):")

    seen: set[str] = set()
    titles: List[str] = []

    for match in re.finditer(r"\[\[([^\]|]+?)(?:\|([^\]]*?))?\]\]", wikitext):
        target = match.group(1).strip()
        display = (match.group(2) or "").strip()

        # [[同名|]] 之类空显示名没有可展示文本，跳过，不降级到目标页
        if namespace_pattern.match(target) or (display == "" and match.group(2) is not None):
            continue

        text = display if display else target
        if not text:
            continue
        if text in bad_exact:
            continue
        if year_pattern.match(text):
            continue
        if text.isdigit():
            continue

        text = text.rstrip("*").strip()
        if not text:
            continue

        if text not in seen:
            seen.add(text)
            titles.append(text)

    logger.info(f"从模板 wikitext 解析到 {len(titles)} 个歌曲条目。")
    return titles
