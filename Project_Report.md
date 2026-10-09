# Project Report: AI Resume Screening & Ranking System

**Author Details:**
* **Name:** Unnati Murarka
* **Email ID:** murarkaunnati@gmail.com
* **Phone Number:** +91 9142337254

---

## 1. Abstract
The recruitment process for specialized engineering roles, such as Software Development Engineer (SDE) Interns focusing on Artificial Intelligence (AI) and Python, often involves manually reviewing hundreds or thousands of applications. This manual screening is time-consuming, prone to cognitive bias, and difficult to scale. This project introduces a robust, automated AI Resume Screening and Ranking System that parses resumes, applies deterministic eligibility criteria, scores candidates across multiple technical dimensions, and augments the evaluation with external signals from GitHub and Large Language Models (LLMs). The output is a structured, explainable, and ranked report of the best candidates, significantly accelerating the hiring pipeline while maintaining evaluation consistency.

---

## 2. Introduction

### 2.1 Background
The tech industry is seeing an unprecedented volume of applications for entry-level and internship positions. For a specialized role demanding a unique intersection of skills—such as applied Python programming and modern AI/LLM engineering—recruiters and hiring managers spend an excessive amount of time verifying if candidates even meet the minimum baseline before evaluating their comparative strengths.

### 2.2 Problem Statement
Screening a massive folder of resumes to find the ideal SDE intern (Python + AI) presents several challenges:
1. **Unstructured Data:** Resumes come in various formats (PDFs, DOCX, TXT) with complex layouts (e.g., two-column designs) that confuse naive text extractors.
2. **Keyword vs. Applied Skill:** Simply matching the word "Python" or "AI" is insufficient. A candidate listing "Python" in a skills section is vastly different from one describing a complex backend system built with Python.
3. **Subjectivity:** Human reviewers may grade candidates inconsistently.
4. **Lack of External Validation:** A resume is self-reported; verifying a candidate's actual coding activity and open-source contributions manually is tedious.
5. **Scale and Latency:** Processing hundreds of resumes manually takes weeks, risking the loss of top candidates to competing offers.

### 2.3 Objectives
* Build a fast, automated pipeline to ingest and parse resumes.
* Implement a rigorous, explainable, and deterministic filtering and scoring engine.
* Enrich candidate profiles with real-world developer signals (GitHub).
* Optionally leverage LLMs for qualitative review without sacrificing the predictability of deterministic scoring.
* Produce a final JSON report ranking candidates with detailed evidence for every score.

---

## 3. Project Description & System Architecture

The AI Resume Screening System is a CLI-first application (with an optional FastAPI server) designed to process a directory of resumes and output a strictly ranked JSON report. 

### 3.1 High-Level Workflow
1. **Ingestion & Parsing:** The system reads documents (.pdf, .docx, .txt), hashes them to prevent duplicate processing, and extracts structural text blocks and hyperlinks.
2. **Extraction:** Named Entity Recognition (regex/heuristics) extracts the candidate's name, email, and GitHub profile URL. Text is categorized into 'skills' sections vs. 'body/experience' sections.
3. **Eligibility Filtering:** A fast, regex-based hard filter checks for essential criteria (Python and AI evidence). Candidates failing this step are immediately rejected to save compute and API costs.
4. **Deterministic Scoring:** Eligible candidates are evaluated on a 100-point scale across categories like AI Depth, Python/Backend, Cloud/Full Stack, GitHub activity, and Engineering Depth.
5. **Signal Enrichment:** The system queries the GitHub API to evaluate the candidate's open-source footprint.
6. **LLM Review (Optional):** An LLM evaluates the resume for nuances, adjusting the AI Depth score slightly and summarizing strengths/concerns.
7. **Report Generation:** A comprehensive JSON report is synthesized, detailing rankings, score breakdowns, penalties, and textual evidence.

---

## 4. Implementation Details (How We Built It)

### 4.1 Technology Stack
* **Language:** Python 3.10+
* **Parsing:** `PyMuPDF` for PDF parsing.
* **Concurrency:** `concurrent.futures.ThreadPoolExecutor` for parallel processing.
* **APIs & Integration:** GitHub REST API, Anthropic API (for LLM evaluation).
* **Validation:** `Pydantic` for structured data validation and LLM output parsing.
* **Web Framework:** `FastAPI` (for the optional API interface).
* **Testing:** `pytest` (comprehensive test suite covering all modules).

### 4.2 Advanced Parsing and Data Extraction
Extracting text from resumes is notoriously difficult due to creative formatting. We utilized PyMuPDF in "block mode." This approach preserves logical reading order, effectively navigating two-column layouts and keeping bullet points intact. Furthermore, many candidates hyperlink the word "GitHub" rather than pasting the raw URL. The parser explicitly extracts hyperlink annotations to ensure no GitHub profiles are missed. The text is then chunked into logical units and tagged as either `skills` (lists of technologies) or `body` (actual project/work experience).

### 4.3 Deterministic Filtering
To ensure repeatability and fairness, the initial eligibility filter relies purely on regex rules. 
* **Python Requirement:** Passes if the word "Python" or a Python-exclusive library (FastAPI, Django, pandas, PyTorch) appears. 
* **AI Requirement:** Passes if there is mention of LLM frameworks, RAG (Retrieval-Augmented Generation), vector databases, or tool-calling agents. Classical ML alone (e.g., scikit-learn without deep learning/LLM context) does not pass.
This filter acts as a massive cost-saver, ensuring external APIs are only called for viable candidates.

### 4.4 Explainable Scoring Engine
The system uses a transparent 100-point scoring matrix:
* **AI Depth (40 points):** Evaluates the complexity of AI projects.
* **Python & Backend (30 points):** Rewards evidence of building scalable backends and APIs.
* **Cloud & Full Stack (15 points):** Looks for AWS, GCP, Docker, Kubernetes, etc.
* **GitHub (10 points):** Activity and repository quality.
* **Engineering Depth (5 points):** CI/CD, testing, system design.

**Nuanced Keyword Scoring:** A keyword found in a project description earns 100% credit, whereas the same keyword found only in a comma-separated skills list earns only 40% credit. 
**Penalties:** Candidates who only demonstrate "thin wrapper" AI work (e.g., just making basic API calls to OpenAI without complex orchestration) are penalized 5-15 points.

### 4.5 GitHub Signal Enrichment
The GitHub module resolves the user's profile and makes two API calls: one for public repositories and one for recent events. It scores the candidate based on:
* **Recency & Volume:** Pushes within the last 30, 90, and 180 days.
* **Repo Quality:** Number of maintained, non-forked repositories, prioritizing those tagged with Python or AI topics.
The module is heavily cached (in-memory and on-disk) to optimize rate limits.

### 4.6 LLM Integration
The system integrates an optional LLM (Anthropic) for qualitative assessment. Instead of letting the LLM dictate the final verdict (which can lead to hallucinations and unexplainable rejections), the LLM is constrained:
* It is forced to reply using a strict JSON schema via Pydantic.
* It can only adjust the deterministic AI score by a maximum of ±8 points.
* It must provide a concrete written reason for the adjustment, along with strengths and concerns.

---

## 5. Challenges and How We Solved Them

### Challenge 1: Parsing Complex Resume Layouts
**Problem:** Standard PDF parsers read text left-to-right, completely scrambling two-column resumes (mixing contact info with work experience on the same line).
**Solution:** By leveraging PyMuPDF's block-level extraction, we successfully isolated columns and maintained the structural integrity of paragraphs and bullet points. We also built heuristics to detect "Skills" sections to differentiate applied experience from keyword stuffing.

### Challenge 2: LLM Unpredictability and Cost
**Problem:** Relying entirely on an LLM to read and rank resumes is slow, expensive, and non-deterministic (a candidate might be ranked #1 today and #3 tomorrow).
**Solution:** We architected the system to be *LLM-augmented* rather than *LLM-dependent*. The primary engine is 100% deterministic (Regex + Scoring weights). The LLM is only invoked for candidates who pass the hard filter, and its power is restricted to a small score adjustment (±8 points) and generating qualitative summaries. This ensures the pipeline is fast, cost-effective, and mathematically explainable.

### Challenge 3: GitHub API Rate Limiting
**Problem:** The unauthenticated GitHub API allows only 60 requests per hour, which is easily exhausted when processing batches of resumes.
**Solution:** We implemented an aggressive two-tier caching strategy (in-memory dictionary + disk-based JSON cache). We also designed the pipeline to group requests by username, ensuring duplicate profiles (e.g., processing the same resume twice) do not consume extra quota. Finally, graceful degradation was built in: if the rate limit is hit, the system logs a warning, assigns 0 GitHub points for remaining users, and continues processing without crashing.

---

## 6. System Output and Results

When the pipeline executes, it outputs a highly detailed `results.json` file. This report contains:
* **Batch Summary:** High-level metrics (total parsed, eligible, rejected, API failures).
* **Ranked Candidates:** A sorted array of the best fits. Each entry provides a 360-degree view of the candidate, including total score, score breakdown per category, applied penalties, GitHub summary, LLM-generated strengths/concerns, and explicitly extracted text snippets proving why they earned those scores.
* **Rejected Candidates:** A list of individuals who failed the filter, complete with the specific reasons (e.g., "Missing required AI/LLM evidence").

The output is designed to be directly consumed by an Applicant Tracking System (ATS) or reviewed manually by a hiring manager via a terminal UI.

---

## 7. Future Work

While the system is robust, future iterations could include:
1. **Per-Project Scoring:** Segmenting the resume into individual projects and scoring them independently, rather than scoring the document as a whole.
2. **OCR Integration:** Adding Optical Character Recognition (e.g., Tesseract) to handle scanned (image-only) PDFs that currently fail parsing.
3. **Repository Deep-Dive:** Extending the GitHub enrichment to pull `README.md` files from a candidate's top repositories to cross-reference claims made on the resume.

---

## 8. Conclusion

The AI Resume Screening System successfully bridges the gap between traditional applicant tracking systems and modern engineering requirements. By combining resilient parsing, strict deterministic evaluation, and intelligent LLM and GitHub augmentations, the system provides hiring teams with a scalable, explainable, and highly accurate tool to identify top-tier SDE intern talent. It transforms days of subjective manual screening into seconds of automated, data-driven analysis.
