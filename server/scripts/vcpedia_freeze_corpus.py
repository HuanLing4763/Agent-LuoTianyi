"""Validate and reproduce an explicitly supplied offline corpus, never its oracle.

No network, git tags, worktree discovery or production parser output is used here.
Import manifests and separately reviewed expected values have distinct lifecycles.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote, urlparse

import mwparserfromhell as mw
from bs4 import BeautifulSoup
from mwparserfromhell.nodes import Heading, Tag, Template, Text

ACTIVE_URL = "https://vcpedia.cn/Special:活跃用户"
HTML_KIND = "mediawiki parse.text fragment"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def relative_file(root, name):
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError(f"invalid relative path: {name!r}")
    path = Path(name)
    if path.is_absolute() or PureWindowsPath(name).drive or ".." in path.parts:
        raise ValueError(f"path must stay inside corpus: {name}")
    result = (root / path).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes corpus: {name}")
    return result


def checked_bytes(root, record):
    path = relative_file(root, record["path"])
    data = path.read_bytes()
    if sha256(data) != record["sha256"]:
        raise ValueError(f"SHA256 mismatch: {record['path']}")
    return data


def _active_unfiltered(soup):
    form = soup.select_one("#mw-content-text form")
    if form is None:
        raise ValueError("active-users form missing")
    username = form.select_one('input[name="username"]')
    if username is None or username.get("value", ""):
        raise ValueError("filtered active-users snapshot")
    if form.select('input[type="checkbox"][checked]'):
        raise ValueError("group-filtered active-users snapshot")
    for link in soup.select("#mw-content-text a[href]"):
        href = unquote(link["href"])
        if re.search(r"[?&](offset|from|username|dir)=", href):
            raise ValueError("active-users pagination is incomplete")
    if soup.select("#mw-content-text .mw-nextlink, #mw-content-text .mw-prevlink"):
        raise ValueError("active-users pagination is incomplete")


def parse_active_users(html, capture):
    """Only an intact, unfiltered, single-page official list can classify users."""
    url = unquote(capture.get("final_url", capture.get("url", "")))
    if url != ACTIVE_URL or capture.get("http_status") != 200 or not capture.get("retrieved_at"):
        raise ValueError("official active-users capture metadata missing/failed")
    if "</html>" not in html.lower() or '"wgCanonicalSpecialPageName":"Activeusers"' not in html:
        raise ValueError("truncated/challenge/non-active-users response")
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("#mw-content-text")
    if main is None or "过去30天有过某种活动" not in main.get_text():
        raise ValueError("official 30-day definition missing")
    _active_unfiltered(soup)
    users = {}
    for link in main.select("li a.mw-userlink"):
        row = link.find_parent("li")
        count = re.search(r"过去30天有([\d,]+)次操作", row.get_text())
        name = link.get_text(strip=True)
        if not count or name in users:
            raise ValueError("malformed/duplicate active-user row")
        groups = [a.get_text(strip=True) for a in row.select('a[href^="/VCPedia:"]')]
        users[name] = {"operations_30d": int(count[1].replace(",", "")),
                       "groups": groups, "bot": "机器人" in groups}
    if not users or len(users) != capture.get("user_count"):
        raise ValueError("active-users count/completeness mismatch")
    return users


def activity(user, users):
    if not user:
        return "unknown"
    return "active_30d" if user in users else "inactive_30d"


def _node_shape(node):
    if isinstance(node, Template):
        return ["template", str(node.name).strip().casefold(),
                [[str(p.name).strip().casefold(), _shape(p.value)] for p in node.params]]
    if isinstance(node, Tag):
        return ["tag", str(node.tag).casefold(),
                [[str(a.name), str(a.value)] for a in node.attributes], _shape(node.contents or "")]
    if isinstance(node, Heading):
        title = str(node.title)
        kind = "lyrics" if "歌词" in title else "summary" if "简介" in title else "other"
        return ["heading", node.level, kind]
    if isinstance(node, Text):
        text = str(node)
        return ["text", bool(text.strip()), "\n" in text, bool(re.search(r"[()（）\[\]]", text)),
                "-{" in text, "截至" in text]
    return [type(node).__name__]


def _shape(code):
    parsed = code if isinstance(code, mw.wikicode.Wikicode) else mw.parse(str(code))
    return [_node_shape(node) for node in parsed.nodes]


def structural_signature(source):
    """Ordered AST nesting, parameter slots, tags and business boundaries, not Jaccard."""
    return sha256(json_bytes(_shape(mw.parse(source))))


def curate(pages, sources, users):
    """Conservative exact-structure grouping; pinned/boundary witnesses never drop."""
    groups = defaultdict(list)
    for page in pages:
        signature = structural_signature(sources[page["title"]])
        key = (signature, tuple(sorted(page["boundaries"])))
        groups[key].append(page)
    kept, dropped, decisions = [], [], []
    for (signature, _), members in sorted(groups.items()):
        ordered = sorted(members, key=lambda p: _preference(p, users))
        representative = ordered[0]
        for page in ordered:
            protected = page.get("protected_reason")
            keep = page is representative or bool(protected)
            (kept if keep else dropped).append(page["title"])
            decisions.append({"title": page["title"], "keep": keep, "representative": representative["title"],
                              "ast_sha256": signature,
                              "reason": protected or ("unique AST/business boundary representative" if keep else
                                                     "same ordered AST and identical business boundaries")})
    return {"kept": sorted(kept), "dropped": sorted(dropped), "decisions": sorted(decisions, key=lambda d: d["title"])}


def _preference(page, users):
    editor = page.get("revision_editor", {})
    name = editor.get("user")
    known = editor.get("source_sha1_matches") is True
    active_human = known and name in users and not users[name]["bot"]
    return (not bool(page.get("protected_reason")), not active_human, not known, page["title"])


def _response_parse(data):
    value = json.loads(data)
    if "body" in value:
        value = json.loads(value["body"])
    return value["parse"]


def _validate_pair(root, page, source):
    capture = page["capture"]
    raw = checked_bytes(root, capture)
    response = gzip.decompress(raw) if capture["path"].endswith(".gz") else raw
    if sha256(response) != capture["response_sha256"]:
        raise ValueError(f"response SHA256 mismatch: {page['title']}")
    parsed = _response_parse(response)
    if parsed["title"] != page["title"] or parsed["pageid"] != page["pageid"]:
        raise ValueError(f"response identity mismatch: {page['title']}")
    if parsed.get("revid") != page["revid"]:
        raise ValueError(f"capture revision mismatch: {page['title']}")
    if parsed["wikitext"]["*"] != source:
        raise ValueError(f"wikitext not from paired response: {page['title']}")
    html = parsed["text"]["*"]
    if sha256(html.encode()) != page["pair"]["html_text_sha256"]:
        raise ValueError(f"HTML response hash mismatch: {page['title']}")
    if page["pair"].get("kind") != HTML_KIND or page["pair"].get("same_response") is not True:
        raise ValueError(f"pair evidence missing: {page['title']}")
    if page.get("html") and checked_bytes(root, page["html"]).decode("utf-8") != html:
        raise ValueError(f"HTML not from paired response: {page['title']}")
    return html


def _validate_page(root, page):
    raw = checked_bytes(root, {"path": page["file"], "sha256": page["sha256"]})
    source = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if not source or not page.get("boundaries") or not page.get("source_url"):
        raise ValueError(f"page metadata incomplete: {page.get('title')}")
    if urlparse(page["source_url"]).netloc != "vcpedia.cn":
        raise ValueError("unexpected source site")
    if page.get("source_only"):
        if not page.get("protected_reason"):
            raise ValueError("unexplained source-only sample")
        return source, None
    return source, _validate_pair(root, page, source)


def load_manifest(path):
    """Validate every listed input; return manifest plus decoded pairs outside timing."""
    path = Path(path).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2 or not manifest.get("rights"):
        raise ValueError("unsupported manifest or missing rights")
    root = path.parent
    active = manifest["active_users"]
    html = checked_bytes(root, active["snapshot"]).decode("utf-8")
    users = parse_active_users(html, active["capture"])
    if users != active["users"]:
        raise ValueError("structured users differ from complete official snapshot")
    for record in manifest.get("evidence", []):
        checked_bytes(root, record)
    pairs = {}
    for page in manifest["pages"]:
        if page["title"] in pairs:
            raise ValueError("duplicate title; revisions must not be collapsed")
        pairs[page["title"]] = _validate_page(root, page)
    if not pairs or len(pairs) != manifest["candidate_count"]:
        raise ValueError("missing corpus page")
    titles = manifest["benchmark_titles"]
    if not titles or len(titles) != len(set(titles)) or not set(titles) <= pairs.keys():
        raise ValueError("invalid fixed benchmark group")
    if any(pairs[title][1] is None for title in titles):
        raise ValueError("benchmark pair missing")
    return manifest, pairs


def _input_records(manifest):
    yield manifest["active_users"]["snapshot"]
    yield from manifest.get("evidence", [])
    for page in manifest["pages"]:
        yield {"path": page["file"], "sha256": page["sha256"]}
        if page.get("capture"):
            yield page["capture"]
        if page.get("html"):
            yield page["html"]


def freeze(manifest_path, output):
    """Stage after complete validation. Never overwrite an existing corpus/oracle."""
    manifest_path, output = Path(manifest_path).resolve(), Path(output).resolve()
    if output.is_relative_to(manifest_path.parent):
        raise ValueError("output must not be inside source corpus")
    manifest, pairs = load_manifest(manifest_path)
    if output.exists():
        raise ValueError("output already exists; reproduce into a new directory, then review explicitly")
    sources = {title: pair[0] for title, pair in pairs.items()}
    decisions = curate(manifest["pages"], sources, manifest["active_users"]["users"])
    # Imported evidence is not authorization to delete pages or approve parser output.
    if decisions["dropped"]:
        raise ValueError("redundancy candidates need separate human selection approval; no pages written")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".vcpedia-freeze-", dir=output.parent))
    try:
        for record in _input_records(manifest):
            target = relative_file(staging, record["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(checked_bytes(manifest_path.parent, record))
        (staging / ".gitattributes").write_text(
            "*.wikitext text eol=lf\n*.json text eol=lf\n*.html text eol=lf\n*.txt text eol=lf\n*.gz binary\n",
            encoding="utf-8", newline="\n")
        (staging / "manifest.json").write_bytes(json_bytes(manifest))
        (staging / "curation.json").write_bytes(json_bytes(decisions))
        meta = {p["title"]: {"file": p["file"], "sha256": p["sha256"]} for p in manifest["pages"]}
        (staging / "meta.json").write_bytes(json_bytes(meta))
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return decisions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true", help="explicit reminder: this tool is always offline")
    args = parser.parse_args(argv)
    try:
        decisions = freeze(args.manifest, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"corpus freeze failed: {exc}", file=sys.stderr)
        return 1
    print(f"validated {len(decisions['kept'])} pages; oracle was not generated or refreshed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
