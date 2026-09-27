"""Typed helpers that build an :class:`Action` for the five live verifier profiles plus
``http.url.status``. Param names, types and target formats follow ``oss/spec/profiles/*.md`` and the
node's verifier ``Params`` models (``oss/node/src/poaw_node/verifiers/{github,x,slack,http}.py``).

Each helper validates cheaply-checkable shape locally (regexes for a commit SHA, a fingerprint hex
digest, a Slack target, ...) and raises ``ValueError`` with a clear message on a bad value. It cannot
catch everything the node will reject (e.g. an unreadable repo) — that still comes back as a 422 from
``submit_claim``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HANDLE = re.compile(r"^@[A-Za-z0-9_]{1,15}$")
_SLACK_TARGET = re.compile(r"^slack://(T[A-Z0-9]{2,20})/([CG][A-Z0-9]{2,20})$")
_SLACK_TS = re.compile(r"^[0-9]{10}\.[0-9]{6}$")


@dataclass(frozen=True)
class Action:
    """An action + target + params ready to hand to ``QedProof.submit_claim``."""

    action: str
    target: str
    params: dict[str, Any]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def github_commit_push(target: str, sha: str, branch: str) -> Action:
    """`github.commit.push` v1: `branch` contains `sha` on the remote."""
    _require(bool(_REPO.match(target)), "target must look like 'owner/repo'")
    _require(bool(_SHA40.match(sha)), "sha must be 40 lowercase hex characters")
    _require(isinstance(branch, str) and bool(branch), "branch must be a non-empty string")
    return Action("github.commit.push", target, {"sha": sha, "branch": branch})


def github_pr_open(target: str, number: int, base: str | None = None, head_sha: str | None = None) -> Action:
    """`github.pr.open` v1: the PR exists (and, if given, matches `base` / `head_sha`)."""
    _require(bool(_REPO.match(target)), "target must look like 'owner/repo'")
    _require(isinstance(number, int) and number > 0, "number must be a positive integer")
    if head_sha is not None:
        _require(bool(_SHA40.match(head_sha)), "head_sha must be 40 lowercase hex characters")
    params: dict[str, Any] = {"number": number}
    if base is not None:
        params["base"] = base
    if head_sha is not None:
        params["head_sha"] = head_sha
    return Action("github.pr.open", target, params)


def github_checks_pass(target: str, sha: str) -> Action:
    """`github.checks.pass` v1: every check run for `sha` concluded successfully."""
    _require(bool(_REPO.match(target)), "target must look like 'owner/repo'")
    _require(bool(_SHA40.match(sha)), "sha must be 40 lowercase hex characters")
    return Action("github.checks.pass", target, {"sha": sha})


def x_post_publish(target: str, post_id: str, text_sha256: str | None = None) -> Action:
    """`x.post.publish` v1: the post exists, written by the account `target` (an `@handle`) is bound to."""
    _require(bool(_HANDLE.match(target)), "target must be an '@handle' (1-15 of A-Za-z0-9_)")
    _require(isinstance(post_id, str) and post_id.isdigit() and 1 <= len(post_id) <= 20,
              "post_id must be a string of 1-20 digits")
    if text_sha256 is not None:
        _require(bool(_HEX64.match(text_sha256)), "text_sha256 must be 64 lowercase hex characters")
    params: dict[str, Any] = {"post_id": post_id}
    if text_sha256 is not None:
        params["text_sha256"] = text_sha256
    return Action("x.post.publish", target, params)


def slack_message_post(target: str, ts: str, text_sha256: str | None = None) -> Action:
    """`slack.message.post` v1: the message exists at `slack://<team>/<channel>` timestamp `ts`."""
    _require(bool(_SLACK_TARGET.match(target)), "target must look like 'slack://<team_id>/<channel_id>'")
    _require(bool(_SLACK_TS.match(ts)), "ts must look like '1234567890.123456'")
    if text_sha256 is not None:
        _require(bool(_HEX64.match(text_sha256)), "text_sha256 must be 64 lowercase hex characters")
    params: dict[str, Any] = {"ts": ts}
    if text_sha256 is not None:
        params["text_sha256"] = text_sha256
    return Action("slack.message.post", target, params)


def http_url_status(target: str, status: int = 200, content_fingerprint: str | None = None) -> Action:
    """`http.url.status` v1: an HTTPS URL returns `status` (and, if given, a matching content fingerprint)."""
    _require(isinstance(target, str) and target.startswith("https://"), "target must be an https:// URL")
    _require(isinstance(status, int) and 100 <= status <= 599, "status must be a valid HTTP status code")
    params: dict[str, Any] = {"status": status}
    if content_fingerprint is not None:
        params["content_fingerprint"] = content_fingerprint
    return Action("http.url.status", target, params)
