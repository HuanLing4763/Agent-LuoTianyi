"""VCPedia 回归语料的冻结与选材。

从四个既有来源收集带 wikitext 源码的页面，按标题去重，记录每页的最后编辑者/时间与
模板签名，然后按两条选材标准收缩：编者近期不活跃的页面剔除（其结构反映已死的编辑
习惯），结构相似簇只保留代表页。输出 tests/support/vcpedia_corpus/ 下的源码与元数据，
供 test_vcpedia_corpus_baseline.py 固化触发行为。

用法：python scripts/vcpedia_freeze_corpus.py          # 全流程
     python scripts/vcpedia_freeze_corpus.py --offline # 只重组本地已有素材，不访问网络
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

OUT = SERVER / "tests" / "support" / "vcpedia_corpus"
FIXTURE_TAG = "dsh-backup-stash0"
_FIXTURE_DIR = "server/tests/world/fixtures"
APP_UA = "AgentLuo/1.0 (+https://github.com/SheepLiu712/Agent-LuoTianyi)"


def _artifacts_base():
    """历史回放素材在主工作区的 data 目录；worktree 内没有。"""
    if (SERVER / "data" / "test_outputs" / "precommit-review-cache-a7fb24317a").exists():
        return SERVER / "data" / "test_outputs"
    out = subprocess.run(["git", "worktree", "list", "--porcelain"],
                         capture_output=True, text=True, cwd=str(SERVER)).stdout
    for line in out.splitlines():
        if line.startswith("worktree "):
            candidate = Path(line.split(None, 1)[1]) / "server" / "data" / "test_outputs"
            if (candidate / "precommit-review-cache-a7fb24317a").exists():
                return candidate
    return SERVER / "data" / "test_outputs"


def _untracked_ref():
    """备份 tag 指向 stash 提交；未跟踪文件在其第三个父提交（untracked 树）。"""
    rev = subprocess.run(["git", "rev-parse", f"{FIXTURE_TAG}^3"],
                         capture_output=True, text=True, cwd=str(SERVER)).stdout.strip()
    return rev or FIXTURE_TAG


def _absorb_replay(pages, base):
    cache_review = base / "precommit-review-cache-a7fb24317a"
    for run in ("run-37a454d954", "run-3b548a8817"):
        for f in sorted(glob.glob(str(cache_review / run / "*.json"))):
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                continue
            inp = d.get("input")
            items = [inp] if isinstance(inp, dict) else (inp or []) if isinstance(inp, list) else []
            for e in items:
                if not isinstance(e, dict):
                    continue
                wt, hp = e.get("wikitext_path"), e.get("html_path")
                if e.get("title") and wt and os.path.exists(wt):
                    pages.setdefault(e["title"], {"origins": []})
                    pages[e["title"]].setdefault("wikitext", Path(wt).read_text(encoding="utf-8"))
                    pages[e["title"]]["origins"].append(f"replay:{run}")
                    if hp and os.path.exists(hp):
                        pages[e["title"]]["html_path"] = hp


def _absorb_random(pages, base):
    for f in sorted(glob.glob(str(base / "precommit-review-random-20260912" / "*.api.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        title = (d.get("parse") or {}).get("title")
        wt = f.replace(".api.json", ".wikitext")
        if title and os.path.exists(wt):
            pages.setdefault(title, {"origins": []})
            pages[title].setdefault("wikitext", Path(wt).read_text(encoding="utf-8"))
            pages[title]["origins"].append("random-review")
            html = f.replace(".api.json", ".html")
            if os.path.exists(html):
                pages[title]["html_path"] = html


def _absorb_browser_fixed(pages, base):
    browser_fixed = base / "browser-fixed-20260911-113745-20e80d"
    for n in (1, 2, 3):
        meta, raw = browser_fixed / f"{n}.source.json", browser_fixed / f"{n}.raw.wikitext"
        if not raw.exists():
            continue
        title = None
        if meta.exists():
            m = re.search(r"'title': '([^']+)'", meta.read_text(encoding="utf-8"))
            title = m.group(1) if m else None
        pages.setdefault(title or f"page{n}", {"origins": []})
        pages[title or f"page{n}"].setdefault("wikitext", raw.read_text(encoding="utf-8"))
        pages[title or f"page{n}"]["origins"].append("browser-fixed")


def _absorb_tag_fixtures(pages):
    untracked = _untracked_ref()
    for fixture in ("vcpedia_fixed_acceptance.json", "vcpedia_frozen_consecutive.json"):
        blob = subprocess.run(["git", "show", f"{untracked}:{_FIXTURE_DIR}/{fixture}"],
                              capture_output=True, text=True, encoding="utf-8", cwd=str(SERVER)).stdout
        for record in json.loads(blob):
            page = record["response"]["parse"]
            pages.setdefault(page["title"], {"origins": []})
            pages[page["title"]].setdefault("wikitext", page["wikitext"]["*"])
            pages[page["title"]]["origins"].append(f"tag:{fixture}")
    blob = subprocess.run(["git", "show", f"{untracked}:{_FIXTURE_DIR}/vcpedia_recorded_lyrics.json"],
                          capture_output=True, text=True, encoding="utf-8", cwd=str(SERVER)).stdout
    for title, record in json.loads(blob).items():
        pages.setdefault(title, {"origins": []})
        pages[title].setdefault("wikitext", record["wikitext"])
        pages[title]["origins"].append("tag:recorded_lyrics")


def collect_candidates() -> dict:
    """title -> {"wikitext": str, "html_path": str|None, "origins": [..]}"""
    base = _artifacts_base()
    pages = {}
    _absorb_replay(pages, base)
    _absorb_random(pages, base)
    _absorb_browser_fixed(pages, base)
    _absorb_tag_fixtures(pages)
    return pages


def structural_signature(wikitext):
    import mwparserfromhell as mw

    from src.world.get_new_songs.template_rules import template_name
    code = mw.parse(wikitext)
    return sorted(set(template_name(t.name) for t in code.ifilter_templates()))


def similarity_clusters(pages):
    names = sorted(pages)
    clusters = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = set(pages[names[i]]["templates"])
            b = set(pages[names[j]]["templates"])
            if a and b and len(a & b) / len(a | b) >= 0.6:
                for cl in clusters:
                    if names[i] in cl or names[j] in cl:
                        cl.update([names[i], names[j]])
                        break
                else:
                    clusters.append({names[i], names[j]})
    return clusters


def fetch_edit_metadata(titles):
    """最后编辑者/时间（逐页）与站点最近变更的活跃编辑者计数。"""
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": APP_UA})
    edit = {}
    for t in titles:
        try:
            r = s.get("https://vcpedia.cn/api.php", params={
                "action": "query", "format": "json", "formatversion": "2",
                "prop": "revisions", "titles": t, "rvprop": "timestamp|user", "rvlimit": "1"},
                timeout=15)
            for pg in r.json().get("query", {}).get("pages", []):
                rev = (pg.get("revisions") or [{}])[0]
                edit[t] = {"user": rev.get("user"), "timestamp": (rev.get("timestamp") or "")[:10]}
        except Exception as exc:
            edit[t] = {"user": None, "timestamp": None, "error": str(exc)}
        time.sleep(0.15)
    try:
        rc = s.get("https://vcpedia.cn/api.php", params={
            "action": "query", "format": "json", "list": "recentchanges",
            "rcprop": "user", "rclimit": "500"}, timeout=15).json()
        return edit, Counter(c.get("user") for c in rc.get("query", {}).get("recentchanges", []))
    except Exception:
        return edit, {}


def curate(pages):
    """选材：编者近期不活跃者剔除（Foxy 作为唯一真缺失触发样本例外）；相似簇留活跃代表。"""
    dropped = {}
    drop_for_dup = set()
    for cl in similarity_clusters(pages):
        ordered = sorted(cl, key=lambda t: -pages[t].get("edits_recent", 0))
        drop_for_dup.update(ordered[1:])
    kept = {}
    for title, v in pages.items():
        if title in drop_for_dup:
            dropped[title] = "结构相似簇的重复代表"
            continue
        if v.get("edits_recent", 0) == 0 and title != "Foxy":
            dropped[title] = f"最后编辑者 {v.get('editor')} 近期不活跃"
            continue
        kept[title] = v
    return kept, dropped


def _write_corpus(kept):
    OUT.mkdir(parents=True, exist_ok=True)
    meta_path = OUT / "meta.json"
    previous = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta = {}
    for title, v in sorted(kept.items()):
        slug = re.sub(r"[^\w.-]+", "_", title).strip("_")
        (OUT / f"{slug}.wikitext").write_text(v["wikitext"], encoding="utf-8", newline="\n")
        meta[title] = {"file": f"{slug}.wikitext", "templates": v["templates"],
                       "editor": v.get("editor"), "edit_ts": v.get("edit_ts"),
                       "edits_recent": v.get("edits_recent"), "origins": v["origins"],
                       "html_path": v.get("html_path"),
                       "baseline": previous.get(title, {}).get("baseline")}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    offline = "--offline" in sys.argv
    pages = collect_candidates()
    for v in pages.values():
        v["templates"] = structural_signature(v["wikitext"])
    counts = None
    if offline:
        meta_path = OUT / "meta.json"
        if meta_path.exists():
            old = json.loads(meta_path.read_text(encoding="utf-8"))
            for t, v in pages.items():
                if t in old:
                    v["editor"], v["edits_recent"] = old[t]["editor"], old[t]["edits_recent"]
    else:
        edit, counts = fetch_edit_metadata(sorted(pages))
        for t, v in pages.items():
            v["editor"] = edit.get(t, {}).get("user")
            v["edit_ts"] = edit.get(t, {}).get("timestamp")
            v["edits_recent"] = int(counts.get(v["editor"], 0))
    kept, dropped = curate(pages)
    if not offline:
        _write_corpus(kept)
        (OUT / "curation.json").write_text(json.dumps(
            {"dropped": dropped, "candidate_count": len(pages)},
            ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"候选页（去重后）: {len(pages)} | 保留 {len(kept)} / 剔除 {len(dropped)}")
    for t, why in sorted(dropped.items()):
        print(f"  剔除 {t[:20]}: {why}")


if __name__ == "__main__":
    main()
