"""离线性能基准：冻结页面上对比旧（渲染 HTML/BeautifulSoup）与新（wikitext/mwparserfromhell）的解析成本。

不含网络与旧实现的业务逻辑，只测"拿到输入之后"的解析+抽取层；传输负载差异
（渲染 HTML 数百 KB vs wikitext JSON 十几 KB）另由在线探针记录（2026-09-27 实测
257KB vs 18KB，约 14 倍）。反爬行为是间歇性的，端到端计时不可 CI 化，故本基准
只用冻结输入，结果可复现。

用法：python scripts/vcpedia_perf_baseline.py
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

CORPUS = SERVER / "tests" / "support" / "vcpedia_corpus"
RANDOM_REVIEW = SERVER / "data" / "test_outputs" / "precommit-review-random-20260912"
ROUNDS = 5


def old_parse(html_text):
    """旧路径的解析层：BeautifulSoup 全页解析 + .poem 文本提取。"""
    soup = BeautifulSoup(html_text, "html.parser")
    parts = []
    for poem in soup.select(".poem"):
        for tag in poem.select("rp, rt, .template-ruby-hidden, .reference, .hover-change-after"):
            tag.decompose()
        for br in poem.find_all("br"):
            br.replace_with("\n")
        parts.append(poem.get_text())
    return "\n".join(parts)


def new_parse(wikitext, title):
    """新路径的解析层：mwparserfromhell 解析 + 完整抽取。"""
    from src.world.get_new_songs.wikitext_parser import parse_details
    return parse_details(wikitext, title)


def timed(fn, *args):
    best = None
    for _ in range(ROUNDS):
        start = time.perf_counter()
        fn(*args)
        elapsed = time.perf_counter() - start
        best = elapsed if best is None else min(best, elapsed)
    return best


def _html_oracles():
    """title -> 旧实现 HTML 表层路径（从回放记录解析，不写入仓库元数据）。"""
    import glob
    import subprocess
    out = subprocess.run(["git", "worktree", "list", "--porcelain"],
                         capture_output=True, text=True, cwd=str(SERVER)).stdout
    main_repo = next(line.split(None, 1)[1] for line in out.splitlines() if line.startswith("worktree "))
    base = Path(main_repo) / "server" / "data" / "test_outputs"
    html = {}
    for run in ("run-37a454d954", "run-3b548a8817"):
        for f in sorted(glob.glob(str(base / "precommit-review-cache-a7fb24317a" / run / "*.json"))):
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                continue
            inp = d.get("input")
            for e in ([inp] if isinstance(inp, dict) else (inp or []) if isinstance(inp, list) else []):
                if isinstance(e, dict) and e.get("title") and e.get("html_path") and Path(e["html_path"]).exists():
                    html[e["title"]] = e["html_path"]
    for f in sorted(glob.glob(str(base / "precommit-review-random-20260912" / "*.api.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        t = (d.get("parse") or {}).get("title")
        h = f.replace(".api.json", ".html")
        if t and Path(h).exists():
            html[t] = h
    return html


def main():
    meta = json.loads((CORPUS / "meta.json").read_text(encoding="utf-8"))
    oracles = _html_oracles()
    rows = []
    for title, entry in sorted(meta.items()):
        wt_path = CORPUS / entry["file"]
        html_path = oracles.get(title)
        if not html_path:
            continue
        wikitext = wt_path.read_text(encoding="utf-8")
        html = Path(html_path).read_text(encoding="utf-8")
        rows.append({
            "title": title,
            "wikitext_bytes": len(wikitext.encode("utf-8")),
            "html_bytes": len(html.encode("utf-8")),
            "old_s": timed(old_parse, html),
            "new_s": timed(new_parse, wikitext, title),
        })

    if not rows:
        raise SystemExit("没有同时具备 wikitext 与 html oracle 的语料页")
    payload_ratio = statistics.mean(r["html_bytes"] / max(r["wikitext_bytes"], 1) for r in rows)
    old_total = statistics.median(r["old_s"] for r in rows)
    new_total = statistics.median(r["new_s"] for r in rows)
    print(f"样本: {len(rows)} 页（同时有冻结 HTML 与 wikitext 的页面）")
    print(f"传输负载: 渲染 HTML / wikitext 中位数倍数 ≈ {payload_ratio:.1f}x")
    print(f"解析+抽取耗时中位数: 旧 {old_total * 1000:.1f} ms | 新 {new_total * 1000:.1f} ms")
    print()
    print("%-18s %10s %10s %10s %10s" % ("页面", "HTML KB", "wiki KB", "旧 ms", "新 ms"))
    for r in rows:
        print("%-18s %10.1f %10.1f %10.1f %10.1f" % (
            r["title"][:16], r["html_bytes"] / 1024, r["wikitext_bytes"] / 1024,
            r["old_s"] * 1000, r["new_s"] * 1000))
    out = SERVER / "data" / "test_outputs" / "perf-baseline-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows, "payload_ratio": payload_ratio,
                               "old_median_s": old_total, "new_median_s": new_total},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n产物: {out}")


if __name__ == "__main__":
    main()
