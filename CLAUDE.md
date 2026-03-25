# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

FYP research benchmarking suite comparing Python code generation across three LLMs (GPT-5.4, Claude Opus 4.6, Gemini 2.5 Pro). Evaluates functional correctness, performance, code quality, security, and structural complexity — with a focus on whether models produce over-engineered solutions.

## Commands

```bash
pip install -r requirements.txt

# Run the full pipeline (scripts use relative paths — run from scripts/)
cd scripts
python generate_code.py    # Step 1: Generate code across N runs (default 5)
python test_harness.py     # Step 2: Execute + measure (3 perf runs per script)
python analyze_results.py  # Step 3: Static analysis + aggregate across runs
python score_requirements.py           # Step 4: Requirement coverage scoring
python score_requirements.py --normalize  # Step 4 + normalised complexity metrics

# Incremental verification (one run per invocation, separate directories)
python verify_run.py               # Run one verification iteration
python verify_run.py --compare     # Run + compare against original results
python verify_run.py --compare-only   # Just compare (no new run)
python verify_run.py --aggregate-only # Just re-aggregate verify runs
python verify_run.py --run-number N   # Force specific run number
```

## Architecture

Four-stage pipeline, all in `scripts/`:

- **`generate_code.py`** — Calls OpenAI, Anthropic, and Google Generative AI APIs. Runs the full generation pipeline `NUM_RUNS` times (default 5) for statistical validity. Each prompt is sent to all 3 models; outputs saved to `outputs/run_{n}/<model>/`. After generation, each script is **executed immediately** — if it fails, the model receives the error and gets up to **3 retries** via multi-turn conversation. Only the final version is saved (failed attempts discarded). Retry data saved to `results/run_{n}/retry_log.json`. Accepts optional path/run parameters for use by `verify_run.py`.
- **`test_harness.py`** — Iterates over all `outputs/run_*/` directories. Runs each script `PERF_RUNS` times (default 3), taking the **median** runtime and peak memory. Results → `results/run_{n}/test_results.txt` and `.json`. Accepts optional path/filter parameters.
- **`analyze_results.py`** — Iterates over all `outputs/run_*/` directories. Runs 6 analysis tools on each script, saves per-run results, then **aggregates** across all runs into `results/aggregated_results.json` (mean ± std for every metric). Also provides `aggregate_all_runs()` for re-aggregating from saved JSON without re-running tools:
  1. `radon cc` — Cyclomatic complexity (branching paths per function)
  2. `radon raw` — Line counts (LOC, SLOC, comments, blanks)
  3. `radon hal` — Halstead metrics (volume, difficulty, effort, est. bugs)
  4. `radon mi` — Maintainability Index (composite 0–100 score)
  5. `pylint` — Code quality score (0–10) and issue breakdown
  6. `bandit` — Security vulnerability scan (severity: LOW/MEDIUM/HIGH)

- **`score_requirements.py`** — Requirement coverage scoring. Checks 45 formal requirements (extracted from prompts) against generated solutions via AST analysis. Produces Requirement Coverage Score (RCS) per model per script, and normalised complexity metrics (SLOC/Coverage, CC/Coverage, Effort/Coverage) that distinguish justified complexity from over-engineering. Supports `--normalize`, `--generate-template` (for manual scoring), and `--with-manual`. All 45 checks are fully automated via AST and source pattern analysis — no manual scoring is required.

- **`verify_run.py`** — Incremental verification orchestrator. Runs one pipeline iteration at a time into `outputs_verify/` and `results_verify/`, auto-detecting the next run number. After each run, re-aggregates all verify runs. Supports `--compare` to print a side-by-side table against original results and save `results_verify/comparison.json`.

**All scripts use relative paths (`../prompts`, `../outputs`, `../results`) and must be run from the `scripts/` directory.**

## Output Structure

```
outputs/run_{n}/<model>/*_solution.py   # Generated code per run
results/run_{n}/retry_log.json          # Retry data per run
results/run_{n}/test_results.json       # Runtime/memory per run
results/run_{n}/analysis_results.json   # Static analysis per run
results/run_{n}/requirement_scores.json # Requirement coverage per run
results/aggregated_results.json         # Mean ± std across all runs
results/requirement_coverage.json       # Coverage per model per script
results/normalised_results.json         # Complexity ÷ coverage
requirements/requirements.json          # 45 formal requirements definition

# Verification (same structure, separate directories)
outputs_verify/run_{n}/<model>/*_solution.py
results_verify/run_{n}/{retry_log,test_results,analysis_results}.json
results_verify/aggregated_results.json  # Re-computed after each verify run
results_verify/comparison.json          # Original vs verify comparison
```

## Prompt Structure

Prompts live in `prompts/` as `{task_domain}_iteration_{n}.txt`. Each domain has 3 iterations of increasing complexity (matching the paper's multi-prompt methodology):

- **api_client** — HTTP data collection (1: basic fetch, 2: error handling/retries, 3: concurrency at scale)
- **dynamic_programming** — TSP-style drone routing (1: basic TSP, 2: time-window constraints, 3: scalability)
- **secure_storage** — Encrypted file storage (1: basic encrypt/decrypt, 2: integrity checks, 3: enterprise-scale)

Each prompt specifies Python, includes concrete function signatures, and requires a `main()` function so outputs are runnable and comparable across models. Iterations 2–3 instruct models to build upon the previous iteration's approach.

## Key Details

- Requires API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GCP_PROJECT` (loaded from `.env` via `python-dotenv`)
- Output directories (`outputs/`, `results/`) are created automatically but not committed to the repo
- `test_harness.py` uses `python3` to execute generated scripts — ensure this points to the correct interpreter
- Models used: `gpt-5.4-2026-03-05` (OpenAI), `claude-opus-4-6` (Anthropic), `gemini-2.5-pro` (Google)
- Pylint has missing-docstring warnings disabled (`C0114`, `C0115`, `C0116`) since generated code rarely includes docstrings
- Configurable: `NUM_RUNS` in generate_code.py (default 5), `PERF_RUNS` in test_harness.py (default 3), `MAX_OUTPUT_TOKENS` (default 16384, uniform across all models)

## Rules

- **Always keep `README.md` in sync with the code.** When you change scripts, prompts, models, metrics, or any project behaviour, update the README to match. The README is the source of truth for how this project works — it must never be out of date.
