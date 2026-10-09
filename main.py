#!/usr/bin/env python3
"""CLI: python main.py --input ./resumes --output ./output/results.json"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from screener.config import Settings  # noqa: E402
from screener.github import GitHubClient  # noqa: E402
from screener.llm import build_reviewer  # noqa: E402
from screener.pipeline import Pipeline, build_report  # noqa: E402
from screener.report import render_terminal  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Screen and rank resumes for an SDE intern role (Python + AI).")
    ap.add_argument("--input", required=True, type=Path, help="folder containing resumes (.pdf, .docx, .txt)")
    ap.add_argument("--output", type=Path, default=Path("output/results.json"))
    ap.add_argument("--no-github", action="store_true", help="skip GitHub enrichment")
    ap.add_argument("--llm", choices=["none", "anthropic"], help="override LLM_PROVIDER from the environment")
    ap.add_argument("--require-applied-python", action="store_true", help="reject Python that only appears in a skills list")
    ap.add_argument("--workers", type=int, help="max concurrent resumes (default from MAX_WORKERS)")
    ap.add_argument("--cache-dir", type=Path, default=Path(".cache"), help="cache for GitHub/LLM results; use --no-cache to disable")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings.from_env()
    overrides = {}
    if args.llm:
        overrides["llm_provider"] = args.llm
    if args.require_applied_python:
        overrides["require_applied_python"] = True
    if args.workers:
        overrides["max_workers"] = max(1, args.workers)
    if args.no_github:
        overrides["github_enabled"] = False
    settings = replace(settings, **overrides)

    cache_dir = None if args.no_cache else args.cache_dir
    github = GitHubClient(settings, cache_dir=(cache_dir / "github") if cache_dir else None)
    reviewer = build_reviewer(settings, cache_dir=(cache_dir / "llm") if cache_dir else None)
    try:
        batch = Pipeline(settings, github, reviewer).run(args.input)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = build_report(batch, settings, {"llm_provider": reviewer.name if reviewer else "none", "github_api_calls": github.api_calls})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(render_terminal(report))
    print(f"\nFull results: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
