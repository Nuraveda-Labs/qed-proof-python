"""SPEC conformance: every vector in `tests/vectors/manifest.json` must verify to exactly the
expected report. This is the same manifest and vector files the reference `check.py` uses (vendored
byte-for-byte by `scripts/sync_sdk_spec.py`), so a receipt verifies identically here and in the
spec's own tool."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from qed_proof import pipeline_digest, verify_receipt

VECTORS_DIR = Path(__file__).parent / "vectors"
MANIFEST = json.loads((VECTORS_DIR / "manifest.json").read_text())
KEYSET = json.loads((VECTORS_DIR / MANIFEST["keyset"]).read_text())


@pytest.mark.parametrize("entry", MANIFEST["vectors"], ids=lambda e: e["file"])
def test_vector_matches_expected_report(entry):
    receipt = json.loads((VECTORS_DIR / entry["file"]).read_text())
    pipeline = json.loads((VECTORS_DIR / entry["pipeline"]).read_text()) if "pipeline" in entry else None
    report = verify_receipt(receipt, KEYSET, pipeline=pipeline).to_dict()
    assert report == entry["expected"], f"{entry['file']}: {entry['description']}"


def test_manifest_covers_all_thirty_five_vectors():
    assert len(MANIFEST["vectors"]) == 35


def _vector(name):
    return json.loads((VECTORS_DIR / name).read_text())


def test_pipeline_digest_matches_policy_digest_in_vector_022():
    pipeline = _vector("pipeline.example.json")
    assert pipeline_digest(pipeline) == _vector("022-valid-policy-checked.json")["body"]["policy"]["digest"]


def test_pipeline_digest_ignores_key_order():
    pipeline = _vector("pipeline.example.json")
    reordered = dict(reversed(list(pipeline.items())))
    assert list(reordered) != list(pipeline)
    assert pipeline_digest(reordered) == pipeline_digest(pipeline)


def test_change_entry_reports_entry_kind_and_no_verdict():
    report = verify_receipt(_vector("027-valid-change.json"), KEYSET)
    assert report.entry_kind == "change"
    assert report.verdict is None
    assert report.valid is True
    assert "claim_digest" not in report.checks
    assert report.to_dict()["entry_kind"] == "change"
