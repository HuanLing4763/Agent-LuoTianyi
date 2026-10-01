"""Deterministic statistics/exit-code tests, never wall-clock speed assertions in CI."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts import vcpedia_perf_baseline as perf


def page(title):
    return {"title": title, "html": "html", "source": "wiki", "html_bytes": 120,
            "wikitext_bytes": 10, "source_sha256": "a", "html_sha256": "b"}


def complete(title):
    return {"name": title, "type": "Song", "infobox": {}, "summary": [], "lyrics": "", "spaced_lyrics": ""}


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.now


def test_warmup_alternation_all_samples_and_paired_statistics():
    clock, calls = FakeClock(), []

    def parser(side):
        def parse(value, title):
            calls.append((side, title, value))
            clock.now += 4 if side == "old" else 2
            return complete(title)
        return parse

    result = perf.benchmark([page("a"), page("b")], parsers={s: parser(s) for s in ("old", "new")}, clock=clock)
    assert len(calls) == 2 * (2 + 9) * 2
    assert clock.calls == 2 * 9 * 2 * 2
    assert [side for side, _, _ in calls[:6]] == ["old", "new", "new", "old", "old", "new"]
    assert calls[22][0] == "new"
    assert all(len(row["samples"]) == 9 for row in result["rows"])
    assert result["rows"][0]["samples"][0]["order"] == ["old", "new"]
    assert result["rows"][1]["samples"][0]["order"] == ["new", "old"]
    assert result["sum_old_medians_s"] == 8
    assert result["sum_new_medians_s"] == 4
    assert result["sum_medians_group_ratio"] == result["median_paired_speedup"] == 2
    assert result["median_file_bytes_ratio"] == 12
    assert result["new_faster"]


def test_medians_not_best_case_or_ratio_of_unpaired_medians():
    clock, counters = FakeClock(), {("old", "a"): 0, ("new", "a"): 0, ("old", "b"): 0, ("new", "b"): 0}
    samples = {("old", "a"): [99, 99, 1, 10, 10, 10, 10, 10, 10, 10, 100],
               ("new", "a"): [99, 99] + [2] * 9, ("old", "b"): [99, 99] + [3] * 9,
               ("new", "b"): [99, 99] + [6] * 9}

    def parser(side):
        def parse(value, title):
            key = side, title
            clock.now += samples[key][counters[key]]
            counters[key] += 1
            return complete(title)
        return parse

    pages = [page("a"), {**page("b"), "html_bytes": 30}]
    result = perf.benchmark(pages, parsers={s: parser(s) for s in ("old", "new")}, clock=clock)
    assert result["rows"][0]["old_median_s"] == 10
    assert result["median_paired_speedup"] == (5 + 0.5) / 2
    assert result["sum_medians_group_ratio"] == 13 / 8
    assert result["median_file_bytes_ratio"] == (12 + 3) / 2


def test_parser_failures_are_never_silently_skipped():
    def broken(value, title):
        raise ValueError("parse failed")

    with pytest.raises(ValueError, match="parse failed"):
        perf.benchmark([page("bad")], parsers={"old": broken, "new": broken})
    with pytest.raises(ValueError, match="incomplete"):
        perf.benchmark([page("bad")], parsers={"old": lambda *_: None, "new": lambda *_: None})
    with pytest.raises(ValueError, match="empty/duplicate"):
        perf.benchmark([])


def test_controlled_check_runs_three_whole_groups_and_writes_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(perf, "prepare", lambda _: [page("fixed")])
    monkeypatch.setattr(perf, "environment", lambda _: {})
    called = []

    def run_group(pages):
        called.append(pages)
        return {"new_faster": len(called) != 2}

    output = tmp_path / "performance.json"
    assert perf.run("unused", output, check=True, runner=run_group) == 1
    assert len(called) == 3
    assert all(pages == [page("fixed")] for pages in called)
    assert json.loads(output.read_text())["check_passed"] is False


def test_fixed_group_cannot_silently_shrink(tmp_path):
    corpus = Path(__file__).resolve().parents[2] / "support" / "vcpedia_corpus"
    source = tmp_path / "inputs"
    shutil.copytree(corpus, source, ignore=shutil.ignore_patterns("results", "__pycache__"))
    path = source / "manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["benchmark_titles"].pop()
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="fixed sample lock"):
        perf.prepare(path)


def test_cli_missing_manifest_returns_real_failure_code(tmp_path):
    output = tmp_path / "never.json"
    assert perf.main(["--manifest", str(tmp_path / "missing.json"), "--output", str(output), "--check"]) == 1
    assert not output.exists()
