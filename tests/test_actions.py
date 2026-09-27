"""Local validation in the typed action helpers."""
import pytest

from qed_proof import actions


def test_github_commit_push_ok():
    a = actions.github_commit_push(target="acme/widgets", sha="a" * 40, branch="main")
    assert a.action == "github.commit.push"
    assert a.params == {"sha": "a" * 40, "branch": "main"}


@pytest.mark.parametrize("kwargs", [
    dict(target="not-a-repo", sha="a" * 40, branch="main"),
    dict(target="acme/widgets", sha="zz" * 20, branch="main"),
    dict(target="acme/widgets", sha="a" * 39, branch="main"),
])
def test_github_commit_push_rejects_bad_input(kwargs):
    with pytest.raises(ValueError):
        actions.github_commit_push(**kwargs)


def test_github_pr_open_optional_fields():
    a = actions.github_pr_open(target="acme/widgets", number=42)
    assert a.params == {"number": 42}
    a2 = actions.github_pr_open(target="acme/widgets", number=42, base="main", head_sha="b" * 40)
    assert a2.params == {"number": 42, "base": "main", "head_sha": "b" * 40}


def test_x_post_publish_requires_handle():
    with pytest.raises(ValueError):
        actions.x_post_publish(target="not-a-handle", post_id="123")
    a = actions.x_post_publish(target="@acme", post_id="123", text_sha256="a" * 64)
    assert a.action == "x.post.publish"


def test_slack_message_post_target_and_ts():
    with pytest.raises(ValueError):
        actions.slack_message_post(target="not-slack", ts="1234567890.123456")
    with pytest.raises(ValueError):
        actions.slack_message_post(target="slack://T0123456789/C0123456789", ts="bad-ts")
    a = actions.slack_message_post(target="slack://T0123456789/C0123456789", ts="1234567890.123456")
    assert a.target == "slack://T0123456789/C0123456789"


def test_http_url_status_requires_https():
    with pytest.raises(ValueError):
        actions.http_url_status(target="http://example.com")
    a = actions.http_url_status(target="https://example.com", status=204)
    assert a.params == {"status": 204}
