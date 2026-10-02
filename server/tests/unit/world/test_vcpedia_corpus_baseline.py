"""Evidence-backed offline regressions: snapshots are not independent correctness."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from support.vcpedia_corpus import oracle_support
from support.vcpedia_corpus.oracle_support import compare, counts, normalized, score
from support.vcpedia_legacy_html import parse_html

from scripts.vcpedia_freeze_corpus import load_manifest
from src.world.get_new_songs.wikitext_parser import parse_details

CORPUS = Path(__file__).resolve().parents[2] / "support" / "vcpedia_corpus"
META = json.loads((CORPUS / "meta.json").read_text(encoding="utf-8"))
MANIFEST, PAIRS = load_manifest(CORPUS / "manifest.json")


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch):
    import requests

    def fail(*args, **kwargs):
        raise AssertionError("corpus evaluation must not access network or LLM")

    monkeypatch.setattr(requests.sessions.Session, "request", fail)


@pytest.mark.parametrize("title", [title for title, entry in META.items() if "baseline" in entry])
def test_corpus_page_matches_recorded_baseline(title):
    data, needed = parse_details(PAIRS[title][0], title, with_missing=True)
    expected = META[title]["baseline"]
    actual = {"type": data["type"], "lyrics_len": len(str(data.get("lyrics") or "")),
              "summary_nonempty": bool([s for s in data.get("summary", []) if s]),
              "infobox_n": len(data.get("infobox") or {}), "needed": needed}
    assert actual == expected


def _historical_parser():
    raw = (CORPUS / "reference" / "vcpedia_fetcher.py.txt").read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == "3208aae7a2f2dc74f9c77f2c8b7bcee680b596a5"
    tree = ast.parse(raw.decode("utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)
               and node.name in {"_parse_page", "_get_data_from_infobox"}]
    assert len(methods) == 2
    isolated = ast.Module(body=[ast.ClassDef(name="Reference", bases=[], keywords=[], body=methods,
                                            decorator_list=[])], type_ignores=[])
    namespace = {"BeautifulSoup": BeautifulSoup, "re": re, "Dict": dict, "List": list, "Any": object}
    exec(compile(ast.fix_missing_locations(isolated), "frozen historical methods", "exec"), namespace)
    return namespace["Reference"]()._parse_page


@pytest.mark.parametrize("title", [title for title, (_, html) in PAIRS.items() if html is not None])
def test_full_legacy_adapter_equals_frozen_original_on_every_pair(title):
    reference = _historical_parser()
    assert parse_html(PAIRS[title][1], title) == reference(PAIRS[title][1], title)


@pytest.mark.parametrize("html", [
    "<h2>other</h2><p>fallback</p>",
    '<h2>简介</h2><p>hello<a>world</a></p><h3>stop</h3><p>not intro</p>',
    '<table class="moe-infobox infobox"><tr><td>作编曲</td></tr><tr><td>作者</td></tr></table>',
    '<h2>歌词</h2><div class="Tabs"><p>no poem</p></div><div class="poem"><p>ignored</p></div>',
    '<h2>歌词</h2><table class="navbox"></table><div class="poem"><p>A(和声)<span>B</span></p></div>',
])
def test_legacy_adapter_preserves_old_edge_behaviour(html):
    assert parse_html(html, "synthetic") == _historical_parser()(html, "synthetic")


def test_independent_content_outcomes_keep_known_gaps_visible():
    actual = compare(PAIRS, parse_html, parse_details)
    reviewed = json.loads((CORPUS / "reviewed_outcomes.json").read_text(encoding="utf-8"))
    assert actual["rows"] == reviewed["rows"]
    assert actual["rows"]["Foxy"]["old"]["lyrics_exact"]
    assert not actual["rows"]["Foxy"]["new"]["lyrics_exact"]
    assert not actual["rows"]["Sharing The World"]["new"]["lyrics_exact"]
    assert actual["rows"]["山塘恋雨"]["new"]["lyrics_exact"]
    assert not actual["rows"]["山塘恋雨"]["new"]["summary_facts"]["5.2.1"]


def test_selected_counts_are_boolean_slots_with_separate_lyrics_page_counts():
    reviewed = json.loads((CORPUS / "reviewed_outcomes.json").read_text(encoding="utf-8"))["rows"]
    selected = {title: reviewed[title] for title in MANIFEST["selected_titles"]}
    assert counts(selected) == {
        "old": {"check_slots": 78, "matched_slots": 58, "unmatched_slots": 20,
                "lyrics_pages": 12, "lyrics_exact_pages": 2, "lyrics_nonexact_pages": 10},
        "new": {"check_slots": 78, "matched_slots": 67, "unmatched_slots": 11,
                "lyrics_pages": 12, "lyrics_exact_pages": 9, "lyrics_nonexact_pages": 3},
    }


@pytest.mark.parametrize(("lyrics", "exact", "representative"), [
    ("first\nsecond\nmiddle\nfourth\nlast", True, True),
    ("first\nmiddle\nlast", False, True),
    ("", False, False),
])
def test_lyric_slots_preserve_correlated_exact_and_representative_diagnostics(lyrics, exact, representative):
    expected = {"type": "Song", "lyrics": "first\nsecond\nmiddle\nfourth\nlast",
                "infobox": {}, "summary_facts": []}
    checks = score({"type": "Song", "lyrics": lyrics}, expected)
    assert checks["lyrics_exact"] is exact
    assert checks["lyrics_representative_order"] is representative
    # One damaged lyric can fail both slots; the slots are not distinct defects.
    totals = counts({"sample": {"old": checks, "new": checks}})["new"]
    assert totals["check_slots"] == 3
    assert totals["matched_slots"] == 1 + exact + representative
    assert totals["unmatched_slots"] == (not exact) + (not representative)
    assert totals["lyrics_pages"] == 1
    assert totals["lyrics_exact_pages"] == int(exact)


def test_normalization_only_converts_zh_cn_and_removes_whitespace():
    assert normalized(" 歌詞\tＡa（合聲）!\n") == "歌词Ａa（合声）!"


def test_content_cli_reports_slot_semantics_without_hiding_known_gaps(tmp_path, capsys):
    output = tmp_path / "content.json"
    assert oracle_support.main(["--manifest", str(CORPUS / "manifest.json"),
                                "--output", str(output), "--check"]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert json.loads(capsys.readouterr().out) == report["selected_counts"]
    assert "not independent defects or accuracy" in report["counts_semantics"]
    assert report["selected_counts"]["new"]["unmatched_slots"] == 11
    assert report["effect_complete"] is False
    assert report["unreviewed_change"] is False
    assert report["extended_counts"] == counts(report["rows"])


def test_oracle_facts_occur_in_page_text_and_review_descriptions_are_present():
    """Check whole-page occurrences and nonempty descriptions/text, not section or lyric boundaries."""
    oracle = json.loads((CORPUS / "oracle.json").read_text(encoding="utf-8"))["pages"]
    for title, expected in oracle.items():
        source, html = PAIRS[title]
        visible = normalized(BeautifulSoup(html, "html.parser").get_text())
        for fact in expected["summary_facts"]:
            assert normalized(fact) in visible, (title, fact)
        assert expected["basis"] and expected["selection"]["scope"]
        assert expected["lyrics"] and source


def test_archive_is_complete_and_selected_subsets_are_coverage_based():
    assert len(PAIRS) == 29
    assert sum(html is not None for _, html in PAIRS.values()) == 28
    ledger = json.loads((CORPUS / "candidate-ledger.json").read_text(encoding="utf-8"))
    assert ledger["candidate_count"] == len(ledger["pages"]) == 31
    assert len(MANIFEST["selected_titles"]) == 12
    benchmark_titles = MANIFEST["benchmark_titles"]
    assert benchmark_titles and len(benchmark_titles) == len(set(benchmark_titles))
    assert set(benchmark_titles) <= {title for title, (_, html) in PAIRS.items() if html is not None}
    decisions = json.loads((CORPUS / "curation.json").read_text(encoding="utf-8"))["selection_decisions"]
    assert {d["title"] for d in decisions if d["retained_in_archive"]} == set(PAIRS)
    assert all(d["representative"] in PAIRS and d["reason"] for d in decisions)
    assert {"Foxy", "Sharing The World", "社畜烧酒", "山塘恋雨"} <= set(MANIFEST["selected_titles"])


def test_candidate_flags_curation_and_strict_present_manifest_agree():
    present = set(PAIRS)
    ledger = json.loads((CORPUS / "candidate-ledger.json").read_text(encoding="utf-8"))
    curation = json.loads((CORPUS / "curation.json").read_text(encoding="utf-8"))
    for page in ledger["pages"]:
        assert page["retained_input"] == page["selection"]["retained_in_archive"] == (page["title"] in present)
    assert set(curation["kept"]) == present
    assert set(curation["dropped"]) == {p["title"] for p in ledger["pages"]} - present
    assert {d["title"] for d in curation["decisions"] if d["keep"]} == present


@pytest.mark.parametrize(("title", "literal"), [
    ("长平传", "馝花紡裰擾蚙蠰"),
    ("达拉崩吧", "啦啦达拉崩巴"),
    ("礼物pre-Sent", "（怎敢跳脱程序 直白将爱提起）"),
])
def test_raw_protected_glyph_ruby_and_parenthetical_witnesses(title, literal):
    lyrics = parse_details(PAIRS[title][0], title)["lyrics"]
    assert literal in lyrics  # Deliberately no zhconv/whitespace normalization here.


def test_gap_flags_are_not_lyric_completeness_or_activity_claims():
    for title in ("Foxy", "社畜烧酒", "Sharing The World", "I LOVE YOU(Adaa)"):
        _, needed = parse_details(PAIRS[title][0], title, with_missing=True)
        assert needed["lyrics"]
    for title in ("周刊Synthesizer V排行榜72", "亚种", "普罗米修斯"):
        data = parse_details(PAIRS[title][0], title)
        assert data["type"] != "Song"  # "Person" fallback is not an independent ontology assertion.
