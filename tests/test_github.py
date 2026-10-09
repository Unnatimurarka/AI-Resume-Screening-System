from datetime import datetime, timedelta, timezone

import requests

from screener.config import Settings
from screener.github import GitHubClient, score_github

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def repo(name, days, language="Python", fork=False, archived=False, desc=""):
    return {"name": name, "pushed_at": iso(days), "language": language, "fork": fork, "archived": archived, "description": desc, "topics": []}


def test_active_user_scores_high():
    repos = [repo(f"r{i}", 5 + i) for i in range(6)]
    events = [{"type": "PushEvent", "created_at": iso(2 + i)} for i in range(12)]
    result = score_github("u", repos, events, Settings(), now=NOW)
    assert result.status == "ok" and result.points == 10


def test_stale_user_scores_low():
    repos = [repo("old", 700)]
    result = score_github("u", repos, [], Settings(), now=NOW)
    assert result.points == 0


def test_forks_and_archived_repos_do_not_count():
    repos = [repo("f", 3, fork=True), repo("a", 3, archived=True)]
    result = score_github("u", repos, [], Settings(), now=NOW)
    assert result.detail["maintained_repos"] == 0


def test_relevance_uses_language_or_ai_keywords():
    repos = [repo("web", 10, language="JavaScript"), repo("rag-bot", 10, language="TypeScript", desc="RAG chatbot"), repo("ml", 10)]
    result = score_github("u", repos, [], Settings(), now=NOW)
    assert result.detail["relevant_repos"] == 2


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code, self._payload, self.headers = status, payload if payload is not None else [], headers or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responder):
        self.responder, self.calls, self.last_headers = responder, 0, None

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls += 1
        self.last_headers = headers
        return self.responder(url)


def test_missing_username_is_not_a_failure():
    client = GitHubClient(Settings(), session=FakeSession(lambda u: FakeResponse()))
    assert client.enrich(None).status == "no_profile"


def test_unknown_user_returns_not_found():
    client = GitHubClient(Settings(), session=FakeSession(lambda u: FakeResponse(404)))
    assert client.enrich("ghost").status == "not_found"


def test_rate_limit_is_recorded_and_stops_further_calls():
    limited = FakeResponse(403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"})
    session = FakeSession(lambda u: limited)
    client = GitHubClient(Settings(), session=session)
    assert client.enrich("a").status == "rate_limited"
    calls = session.calls
    assert client.enrich("b").status == "rate_limited"
    assert session.calls == calls  # circuit breaker: no more requests this run


def test_network_error_does_not_raise():
    def boom(url):
        raise requests.ConnectionError("down")

    assert GitHubClient(Settings(), session=FakeSession(boom)).enrich("a").status == "error"


def test_same_username_is_fetched_once():
    session = FakeSession(lambda u: FakeResponse(200, [repo("r", 3)]))
    client = GitHubClient(Settings(), session=session)
    client.enrich("Same")
    first = session.calls
    client.enrich("same")
    assert session.calls == first


def test_token_is_sent_only_from_settings():
    session = FakeSession(lambda u: FakeResponse(200, []))
    GitHubClient(Settings(github_token="tkn"), session=session).enrich("a")
    assert session.last_headers["Authorization"] == "Bearer tkn"
    session2 = FakeSession(lambda u: FakeResponse(200, []))
    GitHubClient(Settings(), session=session2).enrich("a")
    assert "Authorization" not in session2.last_headers
