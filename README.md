# Testing Suite for LLM Code Generation

## Project Overview

This project evaluates Python code generation across three LLMs — **GPT-5.4**, **Claude Opus 4.6**, and **Gemini 2.5 Pro** — using a multi-prompt iterative methodology. The core research question is whether models produce **over-engineered solutions** for tasks that could be solved with simpler code.

## Directory Structure

```
TestingSuite/
├── prompts/                       # 9 task prompts (3 domains × 3 iterations)
├── outputs/                       # Generated code (created by generate_code.py)
│   ├── run_1/                     # Each generation run is independent
│   │   ├── gpt/
│   │   │   └── *_solution.py
│   │   ├── claude/
│   │   └── gemini/
│   ├── run_2/
│   └── ...                        # NUM_RUNS total (default 5)
├── results/
│   ├── run_1/                     # Per-run results
│   │   ├── retry_log.json
│   │   ├── test_results.txt
│   │   ├── test_results.json
│   │   ├── analysis_results.txt
│   │   └── analysis_results.json
│   ├── run_2/
│   └── aggregated_results.json    # Mean ± std across all runs
├── outputs_verify/                   # Verification data (created by verify_run.py)
│   └── run_N/                        # One run per invocation
├── results_verify/
│   ├── run_N/                        # Per-run verification results
│   ├── aggregated_results.json       # Mean ± std across verify runs
│   └── comparison.json               # Original vs verify comparison
├── scripts/
│   ├── generate_code.py           # Step 1: Generate + execute + retry (N runs)
│   ├── test_harness.py            # Step 2: Execute + measure performance
│   ├── analyze_results.py         # Step 3: Static analysis + aggregation
│   └── verify_run.py              # Incremental verification runner
├── requirements.txt
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your API keys (see `.env.example` for the template):

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
```

The `.env` file is git-ignored and loaded automatically by the scripts via `python-dotenv`.

## Workflow

All scripts use relative paths and **must be run from the `scripts/` directory**:

```bash
cd scripts
python generate_code.py     # Step 1 — generates code across N runs
python test_harness.py      # Step 2 — tests all runs (3 perf runs per script)
python analyze_results.py   # Step 3 — static analysis + aggregation

# Incremental verification (one run per invocation)
python verify_run.py               # Run one verification iteration
python verify_run.py --compare     # Run + compare against original results
python verify_run.py --compare-only   # Just compare (no new run)
python verify_run.py --aggregate-only # Just re-aggregate verify runs
python verify_run.py --run-number N   # Force specific run number
```

## Statistical Methodology

To account for LLM non-determinism, the pipeline runs the full generation process **multiple times** (default: 5 runs). Each run produces independent code from each model for each prompt. Results are reported as **mean ± standard deviation** across runs.

| Stage | Repetitions | Purpose |
|---|---|---|
| Code generation (`generate_code.py`) | **5 runs** (configurable via `NUM_RUNS`) | Captures variance in model output across independent generations |
| Runtime/memory (`test_harness.py`) | **3 executions per script** (configurable via `PERF_RUNS`) | Eliminates OS scheduling noise; reports **median** per run |
| Static analysis (`analyze_results.py`) | **1 per script** | Deterministic — same code always yields the same metrics |

Final results in `results/aggregated_results.json` contain mean, std, and sample count for every metric across all runs.

---

### Step 1: `generate_code.py` — Code Generation with Retry

Reads each prompt from `prompts/`, sends it to all three LLMs with a system instruction requesting raw Python code only (no markdown or explanations). Runs the full generation pipeline `NUM_RUNS` times (default 5), saving each run to `outputs/run_{n}/`.

After generating each script, it is **immediately executed** to check for errors. If execution fails (non-zero exit code), the model receives the error message and is given up to **3 retries** to correct the issue. Each retry uses a multi-turn conversation so the model can see its previous code and the resulting error — testing its ability to diagnose and fix its own mistakes.

- Only the final passing version (or the last attempt if all retries fail) is saved as the `_solution.py` — failed intermediate attempts are not kept
- A structured retry log is written to `results/run_{n}/retry_log.json` with per-attempt exit codes, error snippets, and pass/fail status

#### Retry Conversation Flow

The retry mechanism uses **multi-turn conversations** so each model can see its full history of attempts and errors. This tests contextual error correction, not just single-shot code generation.

```
Attempt 1 (initial):
  messages = [
    {role: "user", content: "<original prompt>"}
  ]
  → Model generates code → Execute it → FAILS

Attempt 2 (retry_1):
  messages = [
    {role: "user",      content: "<original prompt>"},
    {role: "assistant", content: "<the code that failed>"},       ← model sees its own code
    {role: "user",      content: "The code you provided produced  ← model sees the actual
                                  the following error:\n\n            stderr/traceback
                                  <stderr up to 1500 chars>\n\n
                                  Please provide the complete
                                  corrected Python code..."}
  ]
  → Model generates fixed code → Execute it → FAILS again

Attempt 3 (retry_2):
  messages = [
    {role: "user",      content: "<original prompt>"},
    {role: "assistant", content: "<attempt 1 code>"},
    {role: "user",      content: "<error from attempt 1>"},
    {role: "assistant", content: "<attempt 2 code>"},             ← full history preserved
    {role: "user",      content: "<error from attempt 2>"},
  ]
  → Model can see ALL previous attempts and errors

Attempt 4 (retry_3 — final):
  Same pattern, with the full conversation history from all 3 prior attempts.
```

Scripts that pass on any attempt stop immediately — retries only happen on failure. The execution timeout is 60 seconds per attempt. All models share a uniform output token cap of **16,384 tokens** (`MAX_OUTPUT_TOKENS`) to ensure no model is advantaged or truncated by differing generation limits.

**Models used:**
- `gpt-5.4-2026-03-05` (OpenAI)
- `claude-opus-4-6` (Anthropic)
- `gemini-2.5-pro` (Google)

### Step 2: `test_harness.py` — Dynamic Analysis (Performance)

Iterates over all `outputs/run_*/` directories and executes each generated `.py` file as a standalone subprocess. Each script is run **3 times** (`PERF_RUNS`) to eliminate OS scheduling noise, and the **median** runtime and peak memory are reported.

| Metric | What it measures | How |
|---|---|---|
| **Runtime** | Wall-clock execution time (median of 3) | `time.time()` around subprocess |
| **Peak Memory** | Maximum resident set size (median of 3) | `psutil` polling at 50ms intervals |
| **Exit Code** | Whether the script crashed (non-zero = failure) | `subprocess.Popen.returncode` |

Per-run results are written to `results/run_{n}/test_results.txt` and `results/run_{n}/test_results.json`.

### Step 3: `analyze_results.py` — Static Analysis (6 Tools) + Aggregation

Iterates over all `outputs/run_*/` directories and runs six analysis tools on every generated script. Per-run results are written to `results/run_{n}/analysis_results.txt` and `.json`.

After all runs are analysed, the script **aggregates** results across runs into `results/aggregated_results.json`, computing mean ± standard deviation for every metric per model per script.

### `verify_run.py` — Incremental Verification Runner

Orchestrates the full pipeline (generate → test → analyze) **one run at a time** into separate `outputs_verify/` and `results_verify/` directories. This supports reproducibility validation: accumulate verification runs incrementally (e.g. twice daily over several days), then compare against the original 5-run batch to demonstrate result consistency in the FYP paper.

Each invocation auto-detects the next run number (e.g. `run_1`, `run_2`, ...) and calls the existing pipeline scripts with overridden output paths. After each run, all existing verify runs are re-aggregated into `results_verify/aggregated_results.json`.

The existing scripts (`generate_code.py`, `test_harness.py`, `analyze_results.py`) accept optional path parameters but retain their original defaults, so standalone usage is unchanged.

#### How to Run Each Mode

All commands must be run from the `scripts/` directory:

```bash
cd scripts
```

**1. Run one verification iteration** (most common — use this to accumulate data):
```bash
python verify_run.py
```
Auto-detects the next run number (`run_1` on first use, `run_2` next time, etc.). Executes the full pipeline: generate → test → analyze → aggregate across all existing verify runs.

**2. Run + compare against original results:**
```bash
python verify_run.py --compare
```
Same as above, but after finishing prints a side-by-side table showing original vs verification metrics with % differences for every model and script. Saves `results_verify/comparison.json`.

**3. Compare without running anything new:**
```bash
python verify_run.py --compare-only
```
Loads existing `results/aggregated_results.json` and `results_verify/aggregated_results.json`, prints the comparison table, and saves `results_verify/comparison.json`. No code is generated, tested, or analysed.

**4. Re-aggregate existing verify runs:**
```bash
python verify_run.py --aggregate-only
```
Recomputes `results_verify/aggregated_results.json` from all existing per-run JSON files. Useful if you manually deleted a bad run directory and want to recalculate statistics.

**5. Force a specific run number:**
```bash
python verify_run.py --run-number N
```
Overrides auto-detection and uses run number `N`. Useful to re-do a specific run (e.g. if `run_3` had an API outage). Can be combined with `--compare`:
```bash
python verify_run.py --run-number 3 --compare
```

#### Typical Verification Workflow

```bash
# Day 1 — morning & evening
python verify_run.py                  # creates outputs_verify/run_1/
python verify_run.py                  # creates outputs_verify/run_2/

# Day 2 — continue accumulating
python verify_run.py                  # creates run_3
python verify_run.py                  # creates run_4

# ... repeat until enough data collected ...

# Final check — compare all verify runs against original 5-run batch
python verify_run.py --compare-only
```

#### Statistical Tests in Comparison Output

The `--compare` and `--compare-only` modes run **Welch's t-test** (two-sided, unequal variance) on the per-run raw values from both batches. For each model × script × metric combination, the output includes:

| Column | Meaning |
|---|---|
| **Orig Mean** | Mean across original runs |
| **Ver Mean** | Mean across verification runs |
| **Diff %** | Percentage difference between means |
| **p-value** | Welch's t-test p-value. p > 0.05 = no significant difference |
| **Cohen d** | Effect size (how large the difference is in practice) |
| **Effect** | Plain-language interpretation: negligible / small / medium / large |

**Cohen's d interpretation:**
| d | Effect Size | Meaning |
|---|---|---|
| < 0.2 | Negligible | No meaningful difference |
| 0.2–0.5 | Small | Minor difference |
| 0.5–0.8 | Medium | Moderate difference |
| > 0.8 | Large | Substantial difference |

A summary line reports how many metrics showed significant differences (p < 0.05). If this count is 0 or within the expected false-positive rate (~5%), results are considered reproducible. The full comparison data (including t-statistics, p-values, and effect sizes) is saved to `results_verify/comparison.json`.

---

#### Tool 1: Cyclomatic Complexity — `radon cc`

**What it measures:** The number of independent execution paths through the code. Every `if`, `elif`, `for`, `while`, `except`, `and`, `or` adds a path.

**Output:** A score and letter grade per function:
| Grade | CC Score | Meaning |
|---|---|---|
| A | 1–5 | Simple, low risk |
| B | 6–10 | Moderate complexity |
| C | 11–15 | Complex, higher risk |
| D | 16–20 | Too complex |
| E | 21–30 | Unstable |
| F | 31+ | Error-prone, untestable |

**Why it matters for your research:** A function with CC of 25 that could be written with CC of 5 is a direct signal of over-engineering — unnecessary branching and edge-case handling that wasn't asked for.

---

#### Tool 2: Raw Metrics — `radon raw`

**What it measures:** Line-level counts for each file:
| Metric | Meaning |
|---|---|
| **LOC** | Total lines (including blanks and comments) |
| **LLOC** | Logical lines of code |
| **SLOC** | Source lines (non-blank, non-comment) |
| **Comments** | Number of comment lines |
| **Multi** | Multi-line string lines |
| **Blank** | Blank lines |

**Why it matters:** High SLOC with low CC = lots of code that doesn't actually do much branching logic. This is the clearest indicator of over-engineering — the model generated verbose abstractions (extra classes, wrapper functions, excessive error handling) for something simple.

---

#### Tool 3: Halstead Metrics — `radon hal`

**What it measures:** Cognitive complexity based on the operators and operands in the code:
| Metric | Formula / Meaning |
|---|---|
| **Vocabulary** | Distinct operators + distinct operands |
| **Length** | Total operators + total operands |
| **Volume** | Length × log2(Vocabulary) — "size" of the algorithm |
| **Difficulty** | (distinct operators / 2) × (total operands / distinct operands) |
| **Effort** | Difficulty × Volume — total mental effort to understand |
| **Time** | Effort / 18 — estimated seconds to understand the code |
| **Bugs** | Volume / 3000 — estimated number of delivered bugs |

**Why it matters:** Two scripts can have the same CC but very different Halstead effort. If a model uses 50 unique operators where 15 would suffice, the *effort* to understand that code is measurably higher — even if it technically works. The "estimated bugs" metric is also useful: more complexity = more places for bugs.

---

#### Tool 4: Maintainability Index — `radon mi`

**What it measures:** A single composite score (0–100) combining Cyclomatic Complexity, Halstead Volume, and Lines of Code:
| Grade | Score | Meaning |
|---|---|---|
| A | 20–100 | Very maintainable |
| B | 10–19 | Moderately maintainable |
| C | 0–9 | Difficult to maintain |

**Why it matters:** This is your best single-number comparison metric across models. If GPT produces MI=75 and Claude produces MI=45 for the same task, that's a quantifiable difference in maintainability regardless of whether both solutions are functionally correct.

---

#### Tool 5: Pylint Score — `pylint`

**What it measures:** Code quality and PEP 8 conformance on a scale of 0.00 to 10.00. Checks for:
- Convention violations (naming, spacing)
- Refactoring opportunities (duplicated code, too many arguments)
- Warnings (unused variables, unreachable code)
- Errors (undefined variables, wrong types)

Missing docstring warnings (`C0114`, `C0115`, `C0116`) are disabled since generated code rarely includes docstrings and these would dominate the results.

**Why it matters:** Measures readability and adherence to Python conventions. A working script with a pylint score of 3.0 is harder to maintain than one scoring 8.5, even if both pass tests.

---

#### Tool 6: Bandit — Security Scan

**What it measures:** Python-specific security vulnerabilities:
- Hard-coded passwords and secrets
- Use of `eval()`, `exec()`, `pickle` (code injection risk)
- Insecure `subprocess` usage (shell injection)
- Weak cryptographic choices (MD5, SHA1 for hashing passwords)
- SQL injection patterns
- Path traversal vulnerabilities

Each finding is classified by severity (**LOW** / **MEDIUM** / **HIGH**) and confidence level.

**Why it matters:** Directly maps to your paper's security evaluation criterion. Models that generate code using `os.system()` or hard-coded keys produce functionally correct but insecure code.

---

## Evaluation Metrics Summary

| Criterion (Paper §3.2) | Tool | Key Output |
|---|---|---|
| Correctness | test_harness.py | Exit code (0 = pass), pass rate across runs |
| Resilience | generate_code.py | Retry attempts, error correction rate (retry_log.json) |
| Performance | test_harness.py | Runtime (seconds), Peak Memory (MB) — median of 3 |
| Over-engineering | radon cc | Average cyclomatic complexity per function |
| Over-engineering | radon raw | SLOC, LOC, function/class count |
| Over-engineering | radon hal | Halstead effort, difficulty, est. bugs |
| Over-engineering | radon mi | Maintainability Index (0–100) |
| Readability | pylint | Score (0–10), issue counts by type |
| Security | bandit | Findings by severity (LOW/MEDIUM/HIGH) |

All metrics are reported as **mean ± std** across runs in `results/aggregated_results.json`.

## Prompt Design

Each prompt explicitly specifies Python, includes concrete function signatures, and requires a `main()` function so every generated script is directly runnable and comparable across models.

Each task domain has 3 iterations that mirror a real developer workflow:

1. **Iteration 1** — Build the base functionality (correctness focus)
2. **Iteration 2** — Handle errors, edge cases, constraints (robustness focus). Instructs the model to build upon the previous iteration.
3. **Iteration 3** — Scale up and optimize (performance focus). Instructs the model to build upon the previous iteration.

### Task Domains

| Domain | Iteration 1 | Iteration 2 | Iteration 3 |
|---|---|---|---|
| **api_client** | Fetch readings from weather station endpoints → `fetch_all_stations(urls) -> list[dict]` | Add retry logic, rate limiting, error reporting → returns `{"readings": [...], "errors": [...]}` | Concurrent fetching with `max_concurrent` parameter |
| **dynamic_programming** | TSP-style drone routing via cost matrix → `find_optimal_route(cost_matrix) -> (route, energy)` | Add time-window constraints per station → returns feasibility, arrival times | Optimise for up to 20 stations within reasonable time |
| **secure_storage** | Encrypt/decrypt files with passphrase → `store_file()` / `retrieve_file()` | Add integrity checks, wrong-passphrase detection, corruption handling | `SecureStorage` class with multi-user, multi-file support at scale |

---

## Results & Observations

All results below are aggregated across **5 independent generation runs** (mean ± std) to account for LLM non-determinism. Each run generates 27 scripts (9 prompts × 3 models), tested 3 times each for performance, and analysed with all 6 static analysis tools. All models used a uniform output token cap of 16,384 tokens.

### 1. Functional Correctness & Reliability

| Model | Pass Rate | Avg Retries per Script | Total Retries (across 5 runs) |
|-------|-----------|------------------------|-------------------------------|
| GPT-5.4 | **100%** | 1.09 | 4 |
| Claude Opus 4.6 | **100%** | 1.09 | 4 |
| Gemini 2.5 Pro | **100%** | 1.22 | 10 |

- **All three models achieved 100% pass rates** across all 5 runs. Every script ultimately ran successfully (exit code 0), though some required retries.
- **GPT and Claude are nearly identical in reliability** — both averaging 1.09 retries per script with just 4 total retries across 45 scripts each.
- **Gemini required the most error correction** — 10 total retries across 5 runs (2.5× more than GPT or Claude). This suggests Gemini's initial code generation is less robust, particularly for complex prompts, though it always recovers within the retry budget.
- The retry mechanism itself is a useful research signal: models that need retries are generating code they cannot verify internally before outputting.

### 2. Code Size (SLOC — Source Lines of Code)

| Model | Total SLOC (mean) | Avg SLOC Std per Script |
|-------|-------------------|-------------------------|
| Claude Opus 4.6 | **1,154** | 11.5 |
| GPT-5.4 | 1,050 | 19.1 |
| Gemini 2.5 Pro | 834 | 18.1 |

- **Claude consistently produces the most code** — 38% more than Gemini and 10% more than GPT for identical prompts. This is the strongest signal for over-engineering: more code to achieve the same functional outcome.
- **Claude's output is the most consistent across runs** (lowest std of 11.5 per script), meaning its verbosity is systematic, not random. GPT shows the most variation (std 19.1), suggesting it sometimes generates compact solutions and sometimes more elaborate ones.
- Gemini is the **most concise**, producing the least code overall.

### 3. Cyclomatic Complexity

| Model | Avg CC per Script | Avg Std |
|-------|-------------------|---------|
| Claude Opus 4.6 | **8.26** | 1.52 |
| Gemini 2.5 Pro | 5.92 | 1.71 |
| GPT-5.4 | 5.43 | 1.18 |

- **Claude has the highest branching complexity** — averaging 8.26 per function, which falls in the "moderate complexity" range (B grade). This aligns with the SLOC finding: Claude is not just writing more lines, it is adding more decision paths (if/else, error handling, edge cases).
- **GPT produces the simplest control flow** at 5.43 — well within the "simple" range (A grade). Combined with its moderate SLOC, this suggests GPT tends toward straightforward, linear code rather than deeply nested branching.
- Claude's dynamic_programming iteration 3 showed the highest individual CC across all models (mean 22.27 ± 6.63), placing it in the "unstable" E range — more than double GPT's 9.35 for the same prompt.

### 4. Code Quality (Pylint Score, out of 10)

| Model | Avg Pylint Score |
|-------|-----------------|
| GPT-5.4 | **9.37** |
| Gemini 2.5 Pro | 8.40 |
| Claude Opus 4.6 | 7.29 |

- **GPT produces the cleanest, most PEP-8-compliant code** by a wide margin (9.37 vs Claude's 7.29). GPT's scores are consistently high across all scripts with low variance.
- **Claude scores lowest in code quality** despite writing the most code. The additional code Claude generates introduces more style violations, naming convention issues, and refactoring opportunities flagged by pylint.
- This creates an interesting tension: Claude writes more code (potential over-engineering) that is also less clean. A human developer would likely need to refactor Claude's output more than GPT's.

### 5. Maintainability Index (0–100, higher = better)

| Model | Avg MI |
|-------|--------|
| Claude Opus 4.6 | **58.45** |
| Gemini 2.5 Pro | 55.57 |
| GPT-5.4 | 36.78 |

- **Claude has the highest maintainability** — this is the paradox of the results. Claude writes the most code with the highest complexity, yet scores best on maintainability. This is because the MI formula rewards **modularity**: many small functions, comments, and lower complexity *per function*. Claude's approach of breaking tasks into many small pieces inflates the MI even though total code volume is high.
- **Gemini is close behind** at 55.57, benefiting from its concise code and moderate modularity.
- **GPT has the lowest maintainability** (36.78) despite the highest pylint score. GPT tends to pack logic into fewer, denser functions. Each function is well-formatted (high pylint) but individually harder to maintain (lower MI).
- This distinction is important for the over-engineering argument: Claude's code is easier to modify in isolation (high MI) but requires reading more total code. GPT's code is compact but denser to understand per function.

### 6. Halstead Metrics (Cognitive Effort)

| Model | Total Effort | Avg Effort per Script |
|-------|-------------|----------------------|
| Claude Opus 4.6 | **57,780** | 6,420 |
| GPT-5.4 | 47,285 | 5,254 |
| Gemini 2.5 Pro | 32,664 | 3,629 |

- **Claude requires the most cognitive effort** to understand (57,780 total) — 22% more than GPT and 77% more than Gemini. This is the clearest quantitative measure of over-engineering: Claude's code demands significantly more mental effort to comprehend for the same set of tasks.
- **Gemini requires the least mental effort** (32,664 total) — 43% less than Claude. This aligns with its minimal code size and suggests Gemini produces the most straightforward implementations.
- Claude's dynamic_programming iteration 3 alone averages 21,013 Halstead effort — more than Gemini's entire secure_storage domain combined.

### 7. Security (Bandit Findings)

| Model | Total Findings (mean) |
|-------|-----------------------|
| Gemini 2.5 Pro | **11.2** |
| Claude Opus 4.6 | 14.8 |
| GPT-5.4 | 15.2 |

- **Gemini produces the most secure code** with the fewest Bandit findings (11.2 total). Its concise implementations have less surface area for security issues.
- **GPT has the most security findings** (15.2), with dynamic_programming iteration 3 alone averaging 5.6 findings per run — the highest single-script security count in the dataset.
- Claude and GPT are close (14.8 vs 15.2). Claude's secure_storage iteration 2 is a notable outlier at 5.4 findings — the most in the secure_storage domain across all models.
- The secure_storage domain produces the most security findings across all models, which is expected — encryption code inherently triggers Bandit rules around cryptographic operations (e.g., use of `os.urandom`, `hashlib`, `subprocess` for key derivation).

### 8. Domain-Specific Observations

**API Client domain:**
- Claude's api_client iteration 2 shows the longest runtimes (mean 18.50s) — it tends to implement real HTTP requests with retry logic that actually executes against live endpoints, leading to variable runtimes. Gemini's iteration 2 is even more extreme at 20.87s mean.
- GPT's api_client implementations are more conservative with simulated/mocked data, resulting in faster execution (3.08s mean for iteration 2).
- Gemini's api_client SLOC has the highest variance (std 35.0 for iteration 2), indicating highly inconsistent approaches across runs.

**Dynamic Programming domain:**
- All three models produce the most complex code here (highest CC across the board), as expected for algorithmically demanding TSP-style problems.
- Claude's DP iteration 3 reaches CC of 22.27 ± 6.63 — the highest single-script complexity in the entire dataset — suggesting it adds extensive optimisation heuristics beyond what was requested. The high std (6.63) also means Claude's approach varies dramatically between runs.
- Gemini's DP iteration 3 has the highest SLOC variance in the entire dataset (std 44.9), meaning it sometimes generates compact algorithms (~35 lines) and sometimes elaborate multi-heuristic solutions (~125 lines).
- GPT's DP iteration 3 is notable for generating the most Bandit findings of any script (5.6 mean), despite not being a security-focused domain.

**Secure Storage domain:**
- All models are 100% reliable here (no failures across any run), but this domain produces the most Bandit findings across all models, which is inherent to cryptographic code.
- Claude's secure_storage code is the most consistent (low SLOC std of 4.2 for iteration 1) — it has a reliable template for encryption/decryption that it applies each run.
- Claude's secure_storage iteration 2 generates the most security findings (5.4 mean) — its additional abstractions (wrapper classes, key management utilities) introduce more flagged patterns.

### 9. Over-Engineering Verdict

Based on the aggregated data across 5 runs with uniform generation parameters:

**Claude Opus 4.6 is the most over-engineered.** It consistently produces 38% more code than Gemini, has the highest cyclomatic complexity (8.26 avg), and the highest Halstead effort (57,780 total — 77% more than Gemini). Its code is modular (high MI of 58.45) but at the cost of unnecessary abstraction — extra classes, wrapper functions, and defensive error handling that was not requested in the prompts. Claude's DP iteration 3 exemplifies this: CC of 22.27 with Halstead effort of 21,013 for a problem the other models solve with far less complexity.

**GPT-5.4 over-engineers differently.** It writes less code than Claude but packs it more densely (total Halstead effort of 47,285). GPT's approach is fewer but more complex functions, resulting in the lowest maintainability (36.78) despite the best code quality (pylint 9.37). This is "dense over-engineering" rather than "verbose over-engineering."

**Gemini 2.5 Pro is the most minimal.** It produces the least code (834 SLOC), lowest cognitive effort (32,664 Halstead), fewest security findings (11.2), and the most concise implementations. However, this comes at a reliability cost (10 retries vs 4 for the other models), suggesting Gemini sometimes cuts corners that require correction. Gemini demonstrates that minimalism and reliability exist in tension: its concise code is easier to understand but more likely to contain initial errors.

### 10. Reproducibility Verification

To validate that the above results are not artefacts of a single testing session, an independent verification batch of **5 runs** was conducted across separate sessions using `verify_run.py`. This produced a second complete dataset in `outputs_verify/` and `results_verify/`, which was compared against the original 5-run batch using Welch's t-test (two-sided, unequal variance) and Cohen's d (pooled standard deviation).

**Summary of verification runs:**

| Run | GPT Retries | Claude Issues | Gemini Retries | Notes |
|-----|-------------|---------------|----------------|-------|
| 1 | 0 | 0 | 0 | All 27 scripts passed first attempt |
| 2 | 0 | 1 (api_client_2 timeout) | 1 (secure_storage_2) | 2 retries total |
| 3 | 0 | 0 | 0 | All 27 scripts passed first attempt |
| 4 | 1 (dp_iter_2) | 1 API 500 error (dp_iter_1 skipped) | 0 | Anthropic API outage lost 1 script |
| 5 | 1 (secure_storage_1) | 0 | 0 | 1 retry total |

**Statistical comparison results:**

| Statistic | Value |
|-----------|-------|
| Total tests conducted | 351 (3 models × 9 scripts × 13 metrics) |
| Significant at p < 0.05 | 12 (3.4%) |
| Expected false positives at 5% | ~17.5 |
| Metrics with negligible effect size (d < 0.2) | Majority |

**12 out of 351 metrics showed statistically significant differences (p < 0.05) — 3.4%.** This is below the expected 5% false-positive rate for this many independent tests, meaning the number of "significant" results is consistent with random chance alone. No systematic differences were detected between the original and verification batches.

The few metrics that showed large Cohen's d values (e.g., memory usage on individual scripts, some bandit findings) all had p-values above 0.05 — the effect sizes were large in magnitude but not statistically significant given the sample variance, indicating run-to-run variability rather than genuine batch-level differences.

**Conclusion:** The Welch's t-test comparison confirms that the reported results are reproducible. The original 5-run batch and the verification 5-run batch produced statistically indistinguishable outcomes across all models, scripts, and metrics. Full comparison data (t-statistics, p-values, effect sizes) is saved in `results_verify/comparison.json`.
