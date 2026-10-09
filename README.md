# AI Resume Screening & Ranking

Reads a folder of resumes (PDF required, DOCX and TXT as a bonus), rejects anyone without Python and AI/LLM evidence, scores the rest out of 100, adds a GitHub signal and writes a ranked, explainable JSON report.

## Setup

Python 3.10 or newer.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional, see below
```

Nothing in `.env` is required. Without keys the pipeline is fully deterministic and calls GitHub unauthenticated (60 requests per hour).

| Variable | Purpose |
|---|---|
| `GITHUB_TOKEN` | Raises the GitHub limit to 5,000 per hour. Read from the environment only. |
| `LLM_PROVIDER` | `none` (default) or `anthropic`. |
| `ANTHROPIC_API_KEY`, `LLM_MODEL` | Used only when `LLM_PROVIDER=anthropic`. |
| `LLM_MAX_ADJUSTMENT` | Largest change (points) the LLM may make to the AI depth score. Default 8. |
| `MAX_WORKERS` | Resumes processed concurrently. Default 4. |

## Run

```bash
python main.py --input ./resumes --output ./output/results.json
```

Useful flags: `--no-github`, `--llm anthropic`, `--require-applied-python`, `--workers N`, `--no-cache`, `-v`.

Optional API:

```bash
uvicorn screener.api:app --app-dir src
curl -X POST localhost:8000/screen -H 'content-type: application/json' -d '{"input_dir": "./resumes"}'
curl localhost:8000/results
```

Tests: `pytest` (49 tests, no network or API key needed).

## Output

`results.json` contains:

- `batch_summary`: total, parsed, eligible, rejected, failed, duplicates skipped, GitHub and LLM failure counts.
- `ranked_candidates`: rank, name, email, total, `score_breakdown`, `penalties`, `matched_skills`, `project_summary`, `github_summary`, `strengths`, `concerns`, per-category `evidence` (resume snippets) and the eligibility evidence.
- `rejected_candidates`: `rejection_reasons` and `matched_skills`.
- `failed_files`, `duplicate_files`.

## Layout

```
main.py                 CLI
src/screener/
  config.py             weights, thresholds, env settings
  signals.py            keyword vocabulary (regex), separate from logic
  ingest.py             file discovery, PDF/DOCX/TXT text + hyperlinks, hashing
  extract.py            name, email, GitHub user, skills, text "units"
  eligibility.py        hard filter (no LLM)
  scoring.py            100-point scorer, penalties, evidence
  github.py             GitHub client, scoring, cache, rate-limit handling
  llm.py                provider adapter + structured output schema
  pipeline.py           orchestration, bounded concurrency, report builder
  api.py                optional FastAPI wrapper
tests/                  eligibility, scoring, GitHub, LLM, pipeline, extraction
resumes/                the five sample PDFs supplied (candidate_09 to 13)
```

## Design Decisions

**Parsing.** PDFs are read with PyMuPDF in block mode, which keeps bullets together and reads two-column layouts column by column. Hyperlink annotations are read too, because many resumes show only the word 'GitHub' and keep the URL in the link. Text is split into units (a bullet, or a line), and each unit is tagged `skills` (inside a skills section or a `Label: a, b, c, d` list) or `body` (experience, projects, summary). That tag drives most of the scoring logic.

**Filtering.** Eligibility is regex rules only, so the verdict is repeatable and testable. Python counts if the word appears, or a Python-only library does (FastAPI, Flask, Django, pandas, PyTorch and similar). AI counts if any of these appear: an agent/LLM framework, retrieval/RAG/vector search, agents or tool calling, evals, or LLM API usage. Classical ML alone (scikit-learn, PyTorch) does not pass. JavaScript, Java or React alongside Python and AI is never a rejection reason. Python that appears only in a skills list passes with a note, because the brief says 'genuine skill'; `--require-applied-python` makes that stricter. Rejected resumes are never scored or sent to GitHub or the LLM.

**Scoring.** Deterministic and explainable: 40 AI depth, 30 Python and backend, 15 cloud and full stack, 10 GitHub, 5 engineering depth. A keyword in a project or work line earns full credit. The same keyword seen only in a skills list earns 40 per cent (`listed_only_multiplier`). AI depth also rewards concrete build detail (state, orchestration, validation, data processing, deployment) and reported outcomes. Penalties: 5 to 15 points when every AI line shows only LLM API use (thin wrapper, scaled down as more build detail appears), and 3 points for tutorial-style or very briefly described AI work. A strong Python profile with no AI work cannot pass the filter, and AI-light profiles lose most of the 40 points.

**LLM usage.** Optional, behind `LLMReviewer` (`llm.py`). It only reviews candidates who already passed the filter. The reply must validate against the `LLMReview` Pydantic schema (summary, adjustment from -10 to 10, thin-wrapper flag, reason, strengths, concerns). The adjustment is clamped to `LLM_MAX_ADJUSTMENT` and the reason is stored as evidence. A malformed reply is retried once. Any failure (timeout, auth, bad JSON) leaves the deterministic score untouched and records `llm_review.status = "failed"`. Replies are cached on disk by file hash and model. Swapping provider means writing one class with a `review()` method.

**GitHub.** The username is taken from link annotations first, then from text; profile links outweigh repo links, so a resume linking to a collaborator's repo does not hijack the profile. Two calls per user (repos, public events), cached in memory and on disk for six hours, with one fetch per username even under concurrency. Activity (0 to 5): recency of last push (30, 90 and 180-day bands) plus volume in the last 90 days. Repos (0 to 5): count of maintained non-fork repos pushed within a year, plus how many are Python or AI-related by language, name, description or topics. A missing, private, unknown or rate-limited profile scores 0 for this category and never fails screening; the status and reason are recorded. After a rate-limit response no further requests are made in that run.

**Concurrency.** A thread pool of `MAX_WORKERS` handles per-resume work. Parsing and dedupe (by file hash, then by extracted text) are sequential and cheap.

## Known limits

- Scanned (image-only) PDFs have no text and are reported under `failed_files`; OCR is not included.
- The scorer reads wording, not truth. It cannot tell whether a described project is real, and a candidate who writes in terse bullets may score lower than one who writes more.
- Regex rules miss unusual phrasing. The LLM review exists to soften that, but it only adjusts AI depth.
- AI depth is capped at 40, so several strong candidates can tie on that category.
- Summary lines can still earn keyword credit, but they are excluded when choosing the 'strongest AI work' line.
- The bundled `output/results.json` was produced in a sandbox that blocks GitHub's user API, so every candidate shows `github.status = "error"` and 0 GitHub points. Re-run locally (ideally with `GITHUB_TOKEN`) to get real GitHub scores.

## If I Had More Time

1. Score per project instead of per resume: segment projects explicitly, then apply the thin-wrapper and tutorial penalties to each one and report the best.
2. Build a small labelled set of resumes (including odd layouts and scans) and use it to tune weights and the eligibility vocabulary, with OCR for scanned files.
3. Fetch repository READMEs and file trees for the top candidates to check that the resume's projects exist and match what is claimed.
4. Add a calibration pass for the LLM adjustment (compare against reviewer rankings) and run the model concurrently with a token budget per batch.
