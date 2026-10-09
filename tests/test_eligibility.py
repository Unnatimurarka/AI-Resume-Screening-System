from conftest import JAVA_ONLY_RESUME, PY_AI_RESUME, make_resume

from dataclasses import replace

from screener.eligibility import check_eligibility


def test_java_react_profile_is_rejected_for_both_reasons(settings):
    result = check_eligibility(make_resume(JAVA_ONLY_RESUME), settings)
    assert not result.eligible
    assert "No evidence of Python stack" in result.rejection_reasons
    assert "No AI/agentic project evidence" in result.rejection_reasons


def test_python_plus_ai_is_eligible(settings):
    result = check_eligibility(make_resume(PY_AI_RESUME), settings)
    assert result.eligible
    assert result.python_level == "applied"
    assert result.ai_level == "strong"


def test_javascript_alongside_python_and_ai_is_not_a_rejection(settings):
    text = PY_AI_RESUME + "\nBuilt a Next.js and React frontend with Node.js for the copilot.\n"
    assert check_eligibility(make_resume(text), settings).eligible


def test_python_without_ai_is_rejected(settings):
    text = "Dev Patel\n\nEXPERIENCE\n- Built Django REST services in Python with PostgreSQL and Celery workers for billing.\n"
    result = check_eligibility(make_resume(text), settings)
    assert not result.eligible
    assert result.rejection_reasons == ["No AI/agentic project evidence"]


def test_ai_without_python_is_rejected(settings):
    text = (
        "Mia Chen\n\nEXPERIENCE\n- Built a RAG chatbot with LangChain.js, embeddings and Pinecone using TypeScript and Next.js "
        "for customer support at scale.\n"
    )
    result = check_eligibility(make_resume(text), settings)
    assert not result.eligible
    assert result.rejection_reasons == ["No evidence of Python stack"]


def test_classical_ml_only_is_not_ai_evidence(settings):
    text = "Sam Roy\n\nEXPERIENCE\n- Trained scikit-learn and PyTorch models in Python for churn prediction with 91% accuracy.\n"
    result = check_eligibility(make_resume(text), settings)
    assert not result.eligible
    assert "classical ML" in result.rejection_reasons[0]


def test_python_only_in_skills_list_passes_with_note_by_default(settings):
    text = (
        "Kiran Das\n\nEXPERIENCE\n- Built an AI resume screener in Java using Spring AI and the OpenAI API with an async upload pipeline.\n\n"
        "TECHNICAL SKILLS\n\nLanguages: Java, Python, SQL, C++\n"
    )
    result = check_eligibility(make_resume(text), settings)
    assert result.eligible and result.python_level == "listed"
    assert result.notes


def test_strict_mode_rejects_listed_only_python(settings):
    text = (
        "Kiran Das\n\nEXPERIENCE\n- Built an AI resume screener in Java using Spring AI and the OpenAI API with an async upload pipeline.\n\n"
        "TECHNICAL SKILLS\n\nLanguages: Java, Python, SQL, C++\n"
    )
    strict = replace(settings, require_applied_python=True)
    assert not check_eligibility(make_resume(text), strict).eligible


def test_python_implied_by_fastapi(settings):
    text = "Li Wei\n\nPROJECTS\n- Built a FastAPI service wrapping a LangGraph agent with tool calling and retrieval over embeddings.\n"
    assert check_eligibility(make_resume(text), settings).eligible
