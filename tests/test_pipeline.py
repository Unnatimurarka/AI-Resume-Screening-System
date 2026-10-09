import json
from pathlib import Path

import pytest

from conftest import JAVA_ONLY_RESUME, PY_AI_RESUME, make_resume

from screener.eligibility import check_eligibility
from screener.github import GitHubClient
from screener.llm import parse_review_json
from screener.models import GitHubResult, LLMReview
from screener.pipeline import Pipeline, apply_llm_review, build_report
from screener.scoring import score_resume


def run_batch(tmp_path, settings, reviewer=None):
    return Pipeline(settings, GitHubClient(settings), reviewer).run(tmp_path)


def test_bad_files_do_not_crash_the_batch(tmp_path, settings):
    (tmp_path / "good.txt").write_text(PY_AI_RESUME)
    (tmp_path / "java.txt").write_text(JAVA_ONLY_RESUME)
    (tmp_path / "corrupt.pdf").write_bytes(b"%PDF-1.4 this is not a real pdf \x00\x01\x02")
    (tmp_path / "empty.txt").write_text("")
    (tmp_path / "dup.txt").write_text(PY_AI_RESUME)  # same bytes as good.txt
    (tmp_path / "ignored.png").write_bytes(b"\x89PNG")

    batch = run_batch(tmp_path, settings)
    report = build_report(batch, settings)
    s = report["batch_summary"]

    assert s["total_resumes"] == 5  # png ignored
    assert s["successfully_parsed"] == 2
    assert s["eligible"] == 1 and s["rejected"] == 1
    assert s["failed_or_unreadable"] == 2
    assert s["duplicates_skipped"] == 1
    assert {f["file"] for f in report["failed_files"]} == {"corrupt.pdf", "empty.txt"}
    assert report["rejected_candidates"][0]["rejection_reasons"]
    json.dumps(report)  # must be serialisable


def test_missing_input_dir_raises_clear_error(tmp_path, settings):
    with pytest.raises(FileNotFoundError):
        Pipeline(settings, GitHubClient(settings)).run(tmp_path / "nope")


def test_ranking_is_sorted_by_score_descending(tmp_path, settings):
    (tmp_path / "a.txt").write_text(PY_AI_RESUME)
    (tmp_path / "b.txt").write_text(
        "Bo Zed\nbo@example.com\n\nPROJECTS\n\n- Built a chatbot in Python that calls the OpenAI GPT API and prints the reply for the user.\n"
        + "- Wrote documentation, a README and a demo script for the course project and presented it to the class.\n" * 2
    )
    report = build_report(run_batch(tmp_path, settings), settings)
    totals = [c["total_score"] for c in report["ranked_candidates"]]
    assert totals == sorted(totals, reverse=True) and len(totals) == 2
    assert [c["rank"] for c in report["ranked_candidates"]] == [1, 2]


class DownReviewer:
    name = "down"

    def review(self, resume, elig, pts):
        raise TimeoutError("model unavailable")


class NoneReviewer(DownReviewer):
    def review(self, resume, elig, pts):
        return None


@pytest.mark.parametrize("reviewer_cls", [DownReviewer, NoneReviewer])
def test_llm_failure_falls_back_to_deterministic_score(tmp_path, settings, reviewer_cls):
    (tmp_path / "good.txt").write_text(PY_AI_RESUME)
    with_llm = build_report(run_batch(tmp_path, settings, reviewer_cls()), settings)
    without = build_report(run_batch(tmp_path, settings), settings)
    cand = with_llm["ranked_candidates"][0]
    assert cand["llm_review"]["status"] == "failed"
    assert cand["total_score"] == without["ranked_candidates"][0]["total_score"]
    assert with_llm["batch_summary"]["llm_failures"] == 1


def _score(settings):
    r = make_resume(PY_AI_RESUME)
    return score_resume(r, check_eligibility(r, settings), GitHubResult(status="no_profile"), settings)


def test_llm_adjustment_is_bounded_by_config(settings):
    base = _score(settings)
    before = base.breakdown["ai_project_depth"].points
    review = LLMReview(project_summary="s", ai_depth_adjustment=-10, thin_wrapper=False, adjustment_reason="weak")
    adjusted, _ = apply_llm_review(_score(settings), review, settings)
    assert adjusted.breakdown["ai_project_depth"].points == max(0.0, before - settings.llm_max_adjustment)


def test_llm_thin_wrapper_flag_adds_minimum_penalty(settings):
    review = LLMReview(project_summary="s", ai_depth_adjustment=0, thin_wrapper=True, adjustment_reason="just a wrapper")
    before = _score(settings).total
    adjusted, _ = apply_llm_review(_score(settings), review, settings)
    assert adjusted.total == round(before - settings.thin_wrapper_penalty_min, 1)


def test_parse_review_json_accepts_fenced_json_and_rejects_bad_schema():
    good = '```json\n{"project_summary":"x","ai_depth_adjustment":3,"thin_wrapper":false,"adjustment_reason":"r","strengths":[],"concerns":[]}\n```'
    assert parse_review_json(good).ai_depth_adjustment == 3
    with pytest.raises(Exception):
        parse_review_json('{"project_summary":"x","ai_depth_adjustment":99,"thin_wrapper":false,"adjustment_reason":"r"}')
    with pytest.raises(ValueError):
        parse_review_json("no json here")


SAMPLES = Path(__file__).resolve().parent.parent / "resumes"


@pytest.mark.skipif(not (SAMPLES / "candidate_13.pdf").exists(), reason="sample resumes not present")
def test_sample_pdfs_end_to_end(settings):
    report = build_report(Pipeline(settings, GitHubClient(settings)).run(SAMPLES), settings)
    names = {c["candidate_name"]: c for c in report["ranked_candidates"]}
    assert len(report["ranked_candidates"]) > 0
    assert "Yash Maini" in names or "Prathameshpatil " in names
