from types import SimpleNamespace

import pytest

pytest.importorskip("anthropic")

from conftest import PY_AI_RESUME, make_resume

from screener.config import Settings
from screener.eligibility import check_eligibility
from screener.llm import AnthropicReviewer, build_reviewer

GOOD = '{"project_summary":"Stateful agent","ai_depth_adjustment":2,"thin_wrapper":false,"adjustment_reason":"LangGraph + RAG","strengths":["a"],"concerns":[]}'


class FakeMessages:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def create(self, **kwargs):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=reply)])


def reviewer(replies, tmp_path=None):
    rv = AnthropicReviewer(Settings(llm_api_key="test-key"), cache_dir=tmp_path)
    rv.client = SimpleNamespace(messages=FakeMessages(replies))
    return rv


def run(rv):
    r = make_resume(PY_AI_RESUME)
    return rv.review(r, check_eligibility(r, Settings()), 30.0)


def test_valid_reply_is_parsed():
    assert run(reviewer([GOOD])).ai_depth_adjustment == 2


def test_invalid_json_is_retried_once():
    rv = reviewer(["not json", GOOD])
    assert run(rv) is not None
    assert rv.client.messages.calls == 2


def test_two_bad_replies_return_none():
    assert run(reviewer(["nope", '{"project_summary": 1}'])) is None


def test_api_error_returns_none_without_retrying():
    rv = reviewer([TimeoutError("down")])
    assert run(rv) is None
    assert rv.client.messages.calls == 1


def test_reply_is_cached_on_disk(tmp_path):
    rv = reviewer([GOOD], tmp_path)
    run(rv)
    again = reviewer([], tmp_path)  # would raise IndexError if it called the API
    assert run(again).project_summary == "Stateful agent"


def test_missing_key_disables_llm_instead_of_crashing():
    assert build_reviewer(Settings(llm_provider="anthropic", llm_api_key=None)) is None
    assert build_reviewer(Settings(llm_provider="none")) is None
