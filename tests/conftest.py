from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from screener.config import Settings
from screener.extract import parse_resume
from screener.ingest import RawResume


@pytest.fixture
def settings() -> Settings:
    return Settings(github_enabled=False, max_workers=2)


def make_resume(text: str, name: str = "candidate.txt", links: list[str] | None = None):
    """Build a ParsedResume from plain text, the same way the pipeline does."""
    raw = RawResume(path=Path(name), sha256=hashlib.sha256(text.encode()).hexdigest(), text=text, links=links or [])
    return parse_resume(raw)


PY_AI_RESUME = """Asha Rao
asha@example.com | github.com/asharao

EXPERIENCE

Backend Intern, Acme
- Built a stateful LangGraph agent with tool calling and a RAG pipeline over Qdrant embeddings, reducing triage time by 40%.
- Wrote async FastAPI services on PostgreSQL with Redis caching, retries and 25 pytest tests.
- Deployed with Docker on GCP using GitHub Actions CI/CD.

PROJECTS

Support Copilot (Python, LangGraph, FastAPI)
- Orchestrated multi-step workflows with schema-validated tool outputs and an evaluation harness for hallucinations.

TECHNICAL SKILLS

Languages: Python, SQL, TypeScript
"""

JAVA_ONLY_RESUME = """Ravi Kumar
ravi@example.com

EXPERIENCE

Software Intern
- Built Spring Boot microservices with Java and Kafka serving 10k requests per minute.
- Created a React dashboard for order tracking.

TECHNICAL SKILLS

Languages: Java, JavaScript, SQL, C++
"""
