"""Failure-closed freezing and official activity semantics, without private data/git."""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from scripts import vcpedia_freeze_corpus as tool

CORPUS = Path(__file__).resolve().parents[2] / "support" / "vcpedia_corpus"


def manifest():
    return json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))


def test_official_complete_list_and_inactive_semantics():
    active = manifest()["active_users"]
    html = (CORPUS / active["snapshot"]["path"]).read_text(encoding="utf-8")
    users = tool.parse_active_users(html, active["capture"])
    assert len(users) == 40
    assert users["Fiction Blue"]["operations_30d"] == 77
    assert users["小祺"]["operations_30d"] == 53
    assert users["这只阿皮有点皮"]["operations_30d"] == 268
    assert tool.activity("Fiction Blue", users) == "active_30d"
    assert tool.activity("not-in-the-complete-list", users) == "inactive_30d"
    assert tool.activity(None, users) == "unknown"
    assert users["学生bot"]["bot"]


@pytest.mark.parametrize("change", ["challenge", "truncated", "pagination", "filter", "count", "http", "source"])
def test_incomplete_activity_snapshot_is_error_not_empty_list(change):
    active = manifest()["active_users"]
    html = (CORPUS / active["snapshot"]["path"]).read_text(encoding="utf-8")
    capture = active["capture"].copy()
    if change == "challenge":
        html = "<html>Anubis challenge</html>"
    elif change == "truncated":
        html = html.replace("</html>", "")
    elif change == "pagination":
        html = html.replace('class="mw-body-content">', 'class="mw-body-content"><a href="?offset=next">next</a>')
    elif change == "filter":
        html = html.replace("name='username' value=''", "name='username' value='Fiction'")
    elif change == "count":
        capture["user_count"] -= 1
    elif change == "http":
        capture["http_status"] = 403
    else:
        capture["final_url"] = "https://vcpedia.cn/api.php?action=query&list=recentchanges"
    with pytest.raises(ValueError):
        tool.parse_active_users(html, capture)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/private/file", "folder\\file"])
def test_manifest_paths_must_be_portable_and_contained(tmp_path, name):
    with pytest.raises(ValueError):
        tool.relative_file(tmp_path, name)


def test_freeze_is_reproducible_without_git_or_oracle_generation(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("git/network/production parser not allowed")

    import requests

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    first, second = tmp_path / "first", tmp_path / "second"
    tool.freeze(CORPUS / "manifest.json", first)
    tool.freeze(first / "manifest.json", second)
    assert tool.load_manifest(first / "manifest.json") == tool.load_manifest(second / "manifest.json")
    assert not (first / "oracle.json").exists()
    assert not any("baseline" in value for value in json.loads((first / "meta.json").read_text()).values())
    assert (first / ".gitattributes").exists()


def test_freeze_rejects_output_inside_source():
    with pytest.raises(ValueError, match="inside source"):
        tool.freeze(CORPUS / "manifest.json", CORPUS / "recursive-output")
    assert not (CORPUS / "recursive-output").exists()


def test_failure_never_overwrites_existing_corpus_or_oracle(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "oracle.json"
    marker.write_bytes(b"human-approved expected values")
    assert tool.main(["--manifest", str(CORPUS / "manifest.json"), "--output", str(output)]) == 1
    assert marker.read_bytes() == b"human-approved expected values"


@pytest.mark.parametrize("change", ["missing", "hash", "pair", "metadata"])
def test_invalid_inputs_fail_before_output_is_written(tmp_path, change):
    source = tmp_path / "inputs"
    shutil.copytree(CORPUS, source, ignore=shutil.ignore_patterns("results", "__pycache__"))
    value = manifest()
    page = value["pages"][0]
    if change == "missing":
        (source / page["file"]).unlink()
    elif change == "hash":
        (source / page["file"]).write_text("corruption", encoding="utf-8")
    elif change == "pair":
        page["pair"]["same_response"] = False
    else:
        value["active_users"]["capture"].pop("retrieved_at")
    (source / "manifest.json").write_bytes(tool.json_bytes(value))
    output = tmp_path / "output"
    assert tool.main(["--manifest", str(source / "manifest.json"), "--output", str(output)]) == 1
    assert not output.exists()


def test_structure_keeps_nesting_and_slots_not_only_template_names():
    assert tool.structural_signature("{{tabs|text1=<poem>{{color|red|歌}}</poem>}}") != tool.structural_signature(
        "{{tabs|text2={{color|red|<poem>歌</poem>}}}}")


def test_deterministic_groups_prefer_active_human_and_protect_counterexample():
    base = {"boundaries": ["poem"], "revision_editor": {"user": "inactive", "source_sha1_matches": True}}
    inactive = {**copy.deepcopy(base), "title": "a"}
    active = {**copy.deepcopy(base), "title": "b", "revision_editor": {"user": "human", "source_sha1_matches": True}}
    pinned = {**copy.deepcopy(base), "title": "c", "protected_reason": "old-better known counterexample"}
    users = {"human": {"bot": False}}
    result = tool.curate([inactive, active], {"a": "<poem>A</poem>", "b": "<poem>B</poem>"}, users)
    assert result["kept"] == ["b"] and result["dropped"] == ["a"]
    assert result == tool.curate([active, inactive], {"a": "<poem>A</poem>", "b": "<poem>B</poem>"}, users)
    assert "c" in tool.curate([inactive, pinned], {"a": "<poem>A</poem>", "c": "<poem>C</poem>"}, users)["kept"]
