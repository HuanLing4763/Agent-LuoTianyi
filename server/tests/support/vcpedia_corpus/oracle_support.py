"""Independent content scoring, not a production-parser-derived expected value."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from zhconv import convert


def normalized(text):
    return re.sub(r"\s+", "", convert(str(text), "zh-cn"))


def ordered_lines(text, lines):
    value, offset = normalized(text), 0
    for line in lines:
        position = value.find(normalized(line), offset)
        if position < 0:
            return False
        offset = position + len(normalized(line))
    return True


def score(data, oracle):
    """Score exact selected text, ordered representative lines, keys and facts separately."""
    lyrics = oracle["lyrics"]
    lines = lyrics.splitlines()
    representative = [lines[0], lines[len(lines) // 2], lines[-1]]
    info = data.get("infobox", {})
    summary = "\n".join(data.get("summary", []))
    return {"type": data.get("type") == oracle["type"],
            "lyrics_exact": normalized(data.get("lyrics", "")) == normalized(lyrics),
            "lyrics_representative_order": ordered_lines(data.get("lyrics", ""), representative),
            "infobox": {key: normalized(info.get(key, "")) == normalized(value)
                        for key, value in oracle["infobox"].items()},
            "summary_facts": {fact: normalized(fact) in normalized(summary) for fact in oracle["summary_facts"]}}


def compare(pairs, old_parse, new_parse, oracle_path=None):
    path = oracle_path or Path(__file__).with_name("oracle.json")
    oracle = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = {}
    for title, expected in oracle["pages"].items():
        source, html = pairs[title]
        rows[title] = {"old": score(old_parse(html, title), expected),
                       "new": score(new_parse(source, title), expected)}
    return {"scope": "selected first-candidate independent content checks; not whole-song/global accuracy",
            "old_24_song_claim": "unverified: this is cache21 + random10, not the historical daily first24",
            "rows": rows}


def counts(rows):
    result = {}
    for side in ("old", "new"):
        flat = []
        for row in rows.values():
            values = row[side]
            flat.extend([values["type"], values["lyrics_exact"], values["lyrics_representative_order"]])
            flat.extend(values["infobox"].values())
            flat.extend(values["summary_facts"].values())
        exact = sum(row[side]["lyrics_exact"] for row in rows.values())
        result[side] = {"content_items": len(flat), "matched": sum(flat), "known_gap_items": len(flat) - sum(flat),
                        "lyric_exact_pages": exact, "lyric_nonexact_pages": len(rows) - exact}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="fail on unreviewed outcome changes, not on known gaps")
    args = parser.parse_args(argv)
    server = Path(__file__).resolve().parents[3]
    sys.path[:0] = [str(server), str(server / "tests")]
    from support.vcpedia_legacy_html import parse_html

    from scripts.vcpedia_freeze_corpus import json_bytes, load_manifest
    from src.world.get_new_songs.wikitext_parser import parse_details

    try:
        manifest, pairs = load_manifest(args.manifest)
        report = compare(pairs, parse_html, parse_details, args.manifest.parent / "oracle.json")
        selected = {title: report["rows"][title] for title in manifest["selected_titles"]}
        report["selected_titles"] = manifest["selected_titles"]
        report["selected_counts"] = counts(selected)
        report["extended_counts"] = counts(report["rows"])
        outcomes = json.loads((args.manifest.parent / "reviewed_outcomes.json").read_text(encoding="utf-8"))
        report["unreviewed_change"] = report["rows"] != outcomes["rows"]
        report["effect_complete"] = report["selected_counts"]["new"]["known_gap_items"] == 0
        report["known_gap_policy"] = "Matching reviewed outcomes is regression stability, not effect acceptance."
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(json_bytes(report))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"content comparison failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report["selected_counts"], ensure_ascii=False))
    return int(args.check and report["unreviewed_change"])


if __name__ == "__main__":
    raise SystemExit(main())
