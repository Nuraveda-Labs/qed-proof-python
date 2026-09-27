"""Drift guard: every `required` property of every object in the vendored receipt schema must appear
as a key in the matching TypedDict in `qed_proof.types`. If the schema changes shape and the types
aren't updated, this fails."""
from __future__ import annotations

import json
import typing
from importlib import resources

from qed_proof import types as T


def _schema() -> dict:
    text = resources.files("qed_proof").joinpath("receipt.schema.json").read_text(encoding="utf-8")
    return json.loads(text)


def _keys_of(td: type) -> set[str]:
    return set(typing.get_type_hints(td, include_extras=True).keys())


# (schema node getter, TypedDict) pairs covering every object definition in the schema that carries
# a `required` list.
def _mapping(schema: dict):
    body = schema["$defs"]["body"]
    return [
        (schema, T.Receipt),
        (body, T.ReceiptBody),
        (body["properties"]["issuer"], T.Issuer),
        (body["properties"]["agent"], T.Agent),
        (body["properties"]["agent"]["properties"]["erc8004"], T.Erc8004),
        (body["properties"]["claim"], T.Claim),
        (body["properties"]["observation"], T.Observation),
        (body["properties"]["observation"]["properties"]["verifier"], T.VerifierRef),
        (body["properties"]["verdict"], T.VerdictBlock),
        (body["properties"]["attestation"], T.Attestation),
        (schema["$defs"]["signature"], T.Signature),
        (schema["$defs"]["proof"], T.Proof),
        (schema["$defs"]["proof"]["properties"]["anchor"], T.Anchor),
    ]


def test_every_required_schema_property_is_a_typed_dict_key():
    schema = _schema()
    missing = []
    for node, td in _mapping(schema):
        required = node.get("required", [])
        keys = _keys_of(td)
        for prop in required:
            if prop not in keys:
                missing.append(f"{td.__name__}.{prop}")
    assert not missing, f"TypedDicts missing required schema properties: {missing}"


def test_every_typed_dict_key_exists_in_the_schema_object():
    """Catch the opposite drift too: a TypedDict key that no longer means anything in the schema."""
    schema = _schema()
    bad = []
    for node, td in _mapping(schema):
        allowed = set(node.get("properties", {}).keys())
        for key in _keys_of(td):
            if key not in allowed:
                bad.append(f"{td.__name__}.{key}")
    assert not bad, f"TypedDict keys with no matching schema property: {bad}"
