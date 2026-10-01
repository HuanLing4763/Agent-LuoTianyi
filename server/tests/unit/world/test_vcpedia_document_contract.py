"""VCPedia 文档引用与条款承接校验；不把说明文件存在视为功能验收通过。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

REPOSITORY = Path(__file__).resolve().parents[4]
REVIEW = REPOSITORY / "server/tests/support/vcpedia_review"
SPEC = REPOSITORY / "docs/开发进程文档/vcpedia-wikitext-migration.md"
DOCUMENTS = (
    SPEC,
    REVIEW / "README.md",
    REPOSITORY / "server/README.md",
    REPOSITORY / "server/tests/unit/world/README.md",
    REPOSITORY / "server/tests/support/vcpedia_corpus/README.md",
)


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.name)
def test_vcpedia_document_local_links_resolve(document):
    text = document.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        relative = unquote(target.split("#", 1)[0])
        assert (document.parent / relative).resolve().exists(), f"{document.name}: {target}"


def test_review_accounts_for_all_stable_acceptance_ids():
    contract_ids = {f"VCP-{number:02d}" for number in range(1, 27)}
    spec_ids = set(re.findall(r"VCP-\d{2}", SPEC.read_text(encoding="utf-8")))
    assert spec_ids == contract_ids
    inventory = json.loads((REVIEW / "document_inventory.json").read_text(encoding="utf-8"))
    assert inventory["reviewed_head"] == "b0d0a8ee10ad441bd19937959ba885d26299772c"
    assert inventory["reviewed_commit_count"] == 18
    for entry in inventory["entries"]:
        assert entry["history"], entry["path"]
        assert entry["disposition"], entry["path"]
        assert set(entry["contract_ids"]) <= contract_ids, entry["path"]
        assert entry["contract_ids"], entry["path"]
        assert entry["issue"].endswith("/issues/196"), entry["path"]


def test_inventory_keeps_documents_deleted_before_review():
    inventory = json.loads((REVIEW / "document_inventory.json").read_text(encoding="utf-8"))
    documents = {
        Path(entry["path"]).name: entry
        for entry in inventory["entries"]
        if entry["review_category"] == "standalone_document"
    }
    assert set(documents) == {
        "vcpedia-wikitext-migration.md",
        "vcpedia-extraction-rules.md",
        "vcpedia-keyword-baseline.md",
    }
    for entry in documents.values():
        assert entry["introduced_in_pr"]
        assert not entry["present_at_reviewed_head"]
        assert entry["history"][0]["status"] == "A"
        assert entry["history"][-1]["status"] == "D"
