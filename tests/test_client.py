"""Client tests against a mocked HTTP layer (httpx.MockTransport) — no network."""
from __future__ import annotations

import json

import httpx
import pytest

from qed_proof import AsyncQedProof, QedProof, QedProofError, QedProofTimeout, actions
from qed_proof.client import DEFAULT_BASE_URL


def _client(handler) -> QedProof:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url=DEFAULT_BASE_URL)
    return QedProof(api_key="qed_sk_super_secret_value", http_client=http_client)


def _async_client(handler) -> AsyncQedProof:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url=DEFAULT_BASE_URL)
    return AsyncQedProof(api_key="qed_sk_super_secret_value", http_client=http_client)


def _claim_row(claim_id: str, **overrides) -> dict:
    row = {"claim_id": claim_id, "state": "decided", "attempts": 1, "receipt_id": f"rcpt_{claim_id}",
           "verdict": "verified"}
    row.update(overrides)
    return row


def test_submit_claim_posts_expected_body_and_auth():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        assert request.url.path == "/v1/claims"
        return httpx.Response(202, json={"claim_id": "c1", "created": True, "state": "queued", "attempts": 1,
                                         "receipt_id": None, "verdict": None})

    qp = _client(handler)
    action = actions.github_commit_push(target="acme/widgets", sha="a" * 40, branch="main")
    result = qp.submit_claim(action, agent_id="agent-1", client_claim_id="deploy-42")

    assert seen["auth"] == "Bearer qed_sk_super_secret_value"
    assert seen["body"] == {
        "client_claim_id": "deploy-42", "agent_id": "agent-1", "action": "github.commit.push",
        "target": "acme/widgets", "params": {"sha": "a" * 40, "branch": "main"},
        "claimed_at": seen["body"]["claimed_at"],
    }
    assert seen["body"]["claimed_at"].endswith("Z")
    assert result.claim_id == "c1" and result.created is True and result.state == "queued"


def test_idempotent_resubmit_reports_created_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"claim_id": "c1", "created": False, "state": "decided", "attempts": 3,
                                         "receipt_id": "rcpt_1", "verdict": "verified"})

    qp = _client(handler)
    action = actions.github_commit_push(target="acme/widgets", sha="a" * 40, branch="main")
    result = qp.submit_claim(action, agent_id="agent-1", client_claim_id="deploy-42")
    assert result.created is False
    assert result.receipt_id == "rcpt_1" and result.verdict == "verified"


def test_wait_for_verdict_returns_once_decided():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        state = "queued" if calls["n"] < 3 else "decided"
        return httpx.Response(200, json={"claim_id": "c1", "state": state, "attempts": calls["n"],
                                         "receipt_id": "rcpt_1" if state == "decided" else None,
                                         "verdict": "verified" if state == "decided" else None})

    qp = _client(handler)
    result = qp.wait_for_verdict("c1", timeout=5, poll_interval=0.01)
    assert result.decided and result.receipt_id == "rcpt_1"
    assert calls["n"] == 3


def test_wait_for_verdict_times_out():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"claim_id": "c1", "state": "queued", "attempts": 1,
                                         "receipt_id": None, "verdict": None})

    qp = _client(handler)
    with pytest.raises(QedProofTimeout):
        qp.wait_for_verdict("c1", timeout=0.05, poll_interval=0.01)


def test_401_raises_qed_proof_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "invalid or missing API key"})

    qp = _client(handler)
    with pytest.raises(QedProofError) as exc_info:
        qp.get_claim("c1")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid or missing API key"


def test_429_with_retry_after_then_success():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"detail": "rate limit exceeded"}, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"claim_id": "c1", "state": "decided", "attempts": 1,
                                         "receipt_id": "rcpt_1", "verdict": "verified"})

    qp = _client(handler)
    result = qp.wait_for_verdict("c1", timeout=5, poll_interval=0.01)
    assert calls["n"] == 2
    assert result.decided and result.receipt_id == "rcpt_1"


def test_get_receipt_sends_no_authorization_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        assert request.url.path == "/v1/receipts/rcpt_1"
        return httpx.Response(200, json={"body": {}, "signature": {}})

    qp = _client(handler)
    qp.get_receipt("rcpt_1")
    assert seen["auth"] is None


def test_get_keys_sends_no_authorization_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        assert request.url.path == "/.well-known/poaw-keys.json"
        return httpx.Response(200, json={"keys": []})

    qp = _client(handler)
    qp.get_keys()
    assert seen["auth"] is None


def test_api_key_never_appears_in_exception_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "invalid or missing API key"})

    qp = _client(handler)
    with pytest.raises(QedProofError) as exc_info:
        qp.get_claim("c1")
    assert "qed_sk_super_secret_value" not in str(exc_info.value)
    assert "qed_sk_super_secret_value" not in repr(exc_info.value)
    assert "qed_sk_super_secret_value" not in repr(qp)


def test_env_var_fallback(monkeypatch):
    monkeypatch.setenv("QED_PROOF_API_KEY", "qed_sk_from_env")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"claim_id": "c1", "state": "queued", "attempts": 1,
                                         "receipt_id": None, "verdict": None})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url=DEFAULT_BASE_URL)
    qp = QedProof(http_client=http_client)
    qp.get_claim("c1")
    assert seen["auth"] == "Bearer qed_sk_from_env"


def test_list_claims_sends_expected_params_and_auth_omitting_none():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["params"] = dict(request.url.params)
        assert request.url.path == "/v1/claims"
        return httpx.Response(200, json={"claims": [_claim_row("c1")], "next_cursor": None})

    qp = _client(handler)
    page = qp.list_claims(agent_id="agent-1")

    assert seen["auth"] == "Bearer qed_sk_super_secret_value"
    # limit is always sent (default 50); cursor/action/verdict/state are omitted when None.
    assert seen["params"] == {"limit": "50", "agent_id": "agent-1"}
    assert page.claims[0].claim_id == "c1" and page.next_cursor is None


def test_list_claims_sends_all_filters_when_given():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"claims": [], "next_cursor": None})

    qp = _client(handler)
    qp.list_claims(limit=10, cursor="abc", agent_id="agent-1", action="github.commit.push",
                   verdict="verified", state="decided")

    assert seen["params"] == {
        "limit": "10", "cursor": "abc", "agent_id": "agent-1",
        "action": "github.commit.push", "verdict": "verified", "state": "decided",
    }


def test_list_claims_limit_out_of_range_raises_locally_without_a_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP request should be made when limit is invalid")

    qp = _client(handler)
    with pytest.raises(ValueError):
        qp.list_claims(limit=0)
    with pytest.raises(ValueError):
        qp.list_claims(limit=201)


def test_iter_claims_follows_next_cursor_across_two_pages_then_stops():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        calls.append(cursor)
        if cursor is None:
            return httpx.Response(200, json={"claims": [_claim_row("c1"), _claim_row("c2")],
                                             "next_cursor": "page2"})
        assert cursor == "page2"
        return httpx.Response(200, json={"claims": [_claim_row("c3")], "next_cursor": None})

    qp = _client(handler)
    claims = list(qp.iter_claims(page_size=2))

    assert [c.claim_id for c in claims] == ["c1", "c2", "c3"]
    assert calls == [None, "page2"]


async def test_async_list_claims_sends_expected_params_and_auth():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"claims": [_claim_row("c1")], "next_cursor": None})

    qp = _async_client(handler)
    page = await qp.list_claims(action="github.commit.push")

    assert seen["auth"] == "Bearer qed_sk_super_secret_value"
    assert seen["params"] == {"limit": "50", "action": "github.commit.push"}
    assert page.claims[0].claim_id == "c1"


async def test_async_list_claims_limit_out_of_range_raises_locally():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP request should be made when limit is invalid")

    qp = _async_client(handler)
    with pytest.raises(ValueError):
        await qp.list_claims(limit=500)


async def test_async_iter_claims_follows_next_cursor_across_two_pages_then_stops():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        calls.append(cursor)
        if cursor is None:
            return httpx.Response(200, json={"claims": [_claim_row("c1"), _claim_row("c2")],
                                             "next_cursor": "page2"})
        assert cursor == "page2"
        return httpx.Response(200, json={"claims": [_claim_row("c3")], "next_cursor": None})

    qp = _async_client(handler)
    claims = [c async for c in qp.iter_claims(page_size=2)]

    assert [c.claim_id for c in claims] == ["c1", "c2", "c3"]
    assert calls == [None, "page2"]
