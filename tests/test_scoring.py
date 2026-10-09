from conftest import PY_AI_RESUME, make_resume

from screener.config import WEIGHTS
from screener.eligibility import check_eligibility
from screener.models import GitHubResult
from screener.scoring import score_resume

NO_GH = GitHubResult(status="no_profile")


def score(text, settings, gh=NO_GH):
    r = make_resume(text)
    return score_resume(r, check_eligibility(r, settings), gh, settings)


THIN = """Tom Hill

PROJECTS

News Checker (Python, OpenAI API)
- Built a web app that sends article text to the OpenAI GPT API and shows whether it is fake.

TECHNICAL SKILLS

Languages: Python, JavaScript
"""

STRONG = """Tom Hill

PROJECTS

News Checker (Python, LangGraph, FastAPI, Qdrant)
- Built a stateful LangGraph agent that retrieves evidence from a Qdrant vector store with embeddings, calls search tools,
  validates structured output and runs an evaluation harness on 200 labelled claims, reaching 88% accuracy.

TECHNICAL SKILLS

Languages: Python, JavaScript
"""

SKILLS_ONLY = """Tom Hill

PROJECTS

Inventory Tracker (Python, Flask)
- Built a Flask app that tracks warehouse stock levels with SQLite and a simple dashboard for managers.
- Added CSV export and email reports for the weekly stock summary sent to the operations team.

TECHNICAL SKILLS

AI: LangChain, LangGraph, RAG, vector search, OpenAI API, Python
"""


def test_weights_total_100():
    assert sum(WEIGHTS.values()) == 100


def test_category_points_never_exceed_weight(settings):
    stuffed = PY_AI_RESUME + "\n" + " ".join(["fastapi asyncio postgres redis docker gcp aws kafka pytest langgraph rag agent eval"] * 30)
    result = score(stuffed, settings)
    for key, cat in result.breakdown.items():
        assert cat.points <= WEIGHTS[key]
    assert 0 <= result.total <= 100


def test_strong_agentic_project_outranks_thin_wrapper(settings):
    assert score(STRONG, settings).total > score(THIN, settings).total + 15


def test_thin_wrapper_penalty_is_between_5_and_15(settings):
    result = score(THIN, settings)
    wrapper = [p for p in result.penalties if p["type"] == "thin_llm_wrapper"]
    assert len(wrapper) == 1
    assert -15 <= wrapper[0]["points"] <= -5


def test_strong_project_has_no_thin_wrapper_penalty(settings):
    assert not [p for p in score(STRONG, settings).penalties if p["type"] == "thin_llm_wrapper"]


def test_framework_in_skills_list_only_earns_little_ai_credit(settings):
    listed = score(SKILLS_ONLY, settings).breakdown["ai_project_depth"].points
    applied = score(STRONG, settings).breakdown["ai_project_depth"].points
    assert listed < applied / 2


def test_strong_python_without_ai_project_does_not_rank_near_top(settings):
    backend_heavy = (
        "Ann Lee\n\nEXPERIENCE\n- Built async FastAPI services on PostgreSQL with Redis caching, retries, Docker on GCP and 40 pytest tests "
        "for a payments backend.\n\nTECHNICAL SKILLS\n\nAI: OpenAI API, Python\n"
    )
    assert score(backend_heavy, settings).total < score(STRONG, settings).total


def test_every_category_carries_evidence_when_points_awarded(settings):
    result = score(PY_AI_RESUME, settings)
    for cat in result.breakdown.values():
        if cat.points > 0 and cat is not result.breakdown["github"]:
            assert cat.evidence


def test_github_points_flow_into_total(settings):
    base = score(STRONG, settings).total
    boosted = score(STRONG, settings, GitHubResult(status="ok", points=8, summary="active")).total
    assert round(boosted - base, 1) == 8.0


def test_tutorial_style_ai_project_is_penalised(settings):
    text = "Pat Kim\n\nPROJECTS\n\n- Simple chatbot using OpenAI GPT in Python for a todo app demo.\n"
    result = score(text, settings)
    assert any(p["type"] == "tutorial_style" for p in result.penalties)
