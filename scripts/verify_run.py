"""Incremental verification runner.

Runs the full pipeline (generate -> test -> analyze) one run at a time into
separate outputs_verify/ and results_verify/ directories. Accumulate runs
over days, then compare against original results to demonstrate consistency.

Usage:
    python verify_run.py               # Run one verification iteration
    python verify_run.py --compare     # Run + compare against original
    python verify_run.py --compare-only   # Just compare existing data
    python verify_run.py --aggregate-only # Just re-aggregate verify runs
    python verify_run.py --run-number N   # Force specific run number
"""

import argparse
import glob
import json
import math
import os

from scipy import stats as scipy_stats

from generate_code import generate_code
from test_harness import run_tests
from analyze_results import run_analysis, aggregate_all_runs

# Paths (relative — run from scripts/)
PROMPTS_DIR = "../prompts"
OUTPUTS_VERIFY = "../outputs_verify"
RESULTS_VERIFY = "../results_verify"
ORIGINAL_RESULTS = "../results"
ORIGINAL_OUTPUTS = "../outputs"


def detect_next_run(outputs_dir):
    """Scan existing run directories and return the next run number."""
    existing = glob.glob(os.path.join(outputs_dir, "run_*"))
    if not existing:
        return 1
    numbers = []
    for d in existing:
        name = os.path.basename(d)
        try:
            numbers.append(int(name.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return max(numbers) + 1 if numbers else 1


# ---------------------------------------------------------------------------
# Metric extraction — pull per-run raw values from JSON files
# ---------------------------------------------------------------------------

METRIC_EXTRACTORS = {
    "pass_rate": lambda a, t, r, model, script: _retry_val(r, model, script, "pass"),
    "retries": lambda a, t, r, model, script: _retry_val(r, model, script, "attempts"),
    "runtime": lambda a, t, r, model, script: _test_val(t, model, script, "runtime_median"),
    "memory": lambda a, t, r, model, script: _test_val(t, model, script, "memory_median"),
    "cyclomatic_complexity": lambda a, t, r, model, script: _analysis_val(a, model, script,
                                                                           ["cyclomatic_complexity", "average_cc"]),
    "sloc": lambda a, t, r, model, script: _analysis_val(a, model, script, ["raw_metrics", "sloc"]),
    "loc": lambda a, t, r, model, script: _analysis_val(a, model, script, ["raw_metrics", "loc"]),
    "halstead_volume": lambda a, t, r, model, script: _analysis_val(a, model, script, ["halstead", "volume"]),
    "halstead_effort": lambda a, t, r, model, script: _analysis_val(a, model, script, ["halstead", "effort"]),
    "halstead_bugs": lambda a, t, r, model, script: _analysis_val(a, model, script, ["halstead", "bugs"]),
    "maintainability_index": lambda a, t, r, model, script: _analysis_val(
        a, model, script, ["maintainability_index", "maintainability_index"]),
    "pylint_score": lambda a, t, r, model, script: _analysis_val(a, model, script, ["pylint", "score"]),
    "bandit_findings": lambda a, t, r, model, script: _analysis_val(a, model, script, ["bandit", "total_issues"]),
}


def _analysis_val(analysis_data, model, script, keys):
    """Extract a nested value from analysis JSON."""
    d = analysis_data.get(model, {}).get(script, {})
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return None
    if isinstance(d, (int, float)):
        return float(d)
    return None


def _test_val(test_data, model, script, key):
    """Extract a value from test results JSON."""
    val = test_data.get(model, {}).get(script, {}).get(key)
    return float(val) if isinstance(val, (int, float)) else None


def _retry_val(retry_data, model, script, what):
    """Extract retry info. Script name -> prompt file name mapping."""
    prompt_file = script.replace("_solution.py", ".txt")
    entry = retry_data.get(model, {}).get(prompt_file, {})
    if what == "pass":
        return 1.0 if entry.get("final_status") == "pass" else 0.0
    if what == "attempts":
        val = entry.get("total_attempts", 0)
        return float(val) if isinstance(val, (int, float)) else None
    return None


def _load_per_run_data(outputs_dir, results_dir):
    """Load all per-run JSON files and return lists of (analysis, test, retry) dicts."""
    run_dirs = sorted(glob.glob(os.path.join(outputs_dir, "run_*")))
    all_analysis = []
    all_test = []
    all_retry = []
    for run_dir in run_dirs:
        run_name = os.path.basename(run_dir)
        run_results = os.path.join(results_dir, run_name)

        for filename, target in [("analysis_results.json", all_analysis),
                                  ("test_results.json", all_test),
                                  ("retry_log.json", all_retry)]:
            path = os.path.join(run_results, filename)
            if os.path.exists(path):
                with open(path) as f:
                    target.append(json.load(f))
            else:
                target.append({})
    return all_analysis, all_test, all_retry


def _collect_per_run_values(all_analysis, all_test, all_retry, model, script, metric_key):
    """Collect raw values for a metric across all runs."""
    extractor = METRIC_EXTRACTORS.get(metric_key)
    if not extractor:
        return []
    values = []
    for i in range(len(all_analysis)):
        a = all_analysis[i] if i < len(all_analysis) else {}
        t = all_test[i] if i < len(all_test) else {}
        r = all_retry[i] if i < len(all_retry) else {}
        val = extractor(a, t, r, model, script)
        if val is not None:
            values.append(val)
    return values


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

def welch_t_test(orig_values, verify_values):
    """Run Welch's t-test (unequal variance) and return t-stat, p-value, Cohen's d."""
    n1, n2 = len(orig_values), len(verify_values)
    if n1 < 2 or n2 < 2:
        return None, None, None

    t_stat, p_value = scipy_stats.ttest_ind(orig_values, verify_values, equal_var=False)

    # Cohen's d (pooled std)
    mean1 = sum(orig_values) / n1
    mean2 = sum(verify_values) / n2
    var1 = sum((x - mean1) ** 2 for x in orig_values) / (n1 - 1)
    var2 = sum((x - mean2) ** 2 for x in verify_values) / (n2 - 1)
    pooled_std = math.sqrt((var1 + var2) / 2)
    cohens_d = abs(mean1 - mean2) / pooled_std if pooled_std > 0 else 0.0

    return float(t_stat), float(p_value), round(cohens_d, 4)


def interpret_cohens_d(d):
    """Return a plain-language interpretation of Cohen's d."""
    if d is None:
        return "N/A"
    if d < 0.2:
        return "negligible"
    if d < 0.5:
        return "small"
    if d < 0.8:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

METRICS = [
    ("pass_rate", "Pass Rate"),
    ("retries", "Retries"),
    ("runtime", "Runtime (s)"),
    ("memory", "Memory (MB)"),
    ("cyclomatic_complexity", "Cyclomatic Cmplx"),
    ("sloc", "SLOC"),
    ("loc", "LOC"),
    ("halstead_volume", "Halstead Vol"),
    ("halstead_effort", "Halstead Effort"),
    ("halstead_bugs", "Halstead Bugs"),
    ("maintainability_index", "Maint. Index"),
    ("pylint_score", "Pylint Score"),
    ("bandit_findings", "Bandit Findings"),
]


def compare_results(original_outputs, original_results, verify_outputs, verify_results):
    """Load per-run data from both batches, run t-tests, print comparison."""
    if not os.path.exists(original_outputs) or not os.path.exists(verify_outputs):
        print("Missing output directories. Ensure both batches have been run.")
        return None

    # Load per-run data
    orig_analysis, orig_test, orig_retry = _load_per_run_data(original_outputs, original_results)
    ver_analysis, ver_test, ver_retry = _load_per_run_data(verify_outputs, verify_results)

    n_orig = len(orig_analysis)
    n_ver = len(ver_analysis)
    print(f"\n  Original runs: {n_orig}    Verification runs: {n_ver}")

    if n_orig < 2 or n_ver < 2:
        print("  Need at least 2 runs in each batch for statistical tests.")
        print("  Showing means only.\n")

    # Discover all models and scripts
    models = set()
    scripts = set()
    for data_list in [orig_analysis, ver_analysis]:
        for data in data_list:
            for model in data:
                models.add(model)
                for script in data[model]:
                    scripts.add(script)

    comparison = {}
    all_p_values = []

    # Print header
    header = (f"{'Model':<8} {'Script':<35} {'Metric':<18} "
              f"{'Orig Mean':>10} {'Ver Mean':>10} {'Diff %':>8} "
              f"{'p-value':>8} {'Cohen d':>8} {'Effect':>11}")
    print(f"\n{'='*130}")
    print("  REPRODUCIBILITY COMPARISON: Original vs Verification")
    print(f"{'='*130}")
    print(header)
    print("-" * 130)

    for model in sorted(models):
        comparison[model] = {}
        for script in sorted(scripts):
            comparison[model][script] = {}

            for metric_key, metric_label in METRICS:
                orig_vals = _collect_per_run_values(orig_analysis, orig_test, orig_retry,
                                                     model, script, metric_key)
                ver_vals = _collect_per_run_values(ver_analysis, ver_test, ver_retry,
                                                    model, script, metric_key)

                orig_mean = sum(orig_vals) / len(orig_vals) if orig_vals else None
                ver_mean = sum(ver_vals) / len(ver_vals) if ver_vals else None

                # % difference
                if orig_mean is not None and ver_mean is not None and orig_mean != 0:
                    diff_pct = ((ver_mean - orig_mean) / abs(orig_mean)) * 100
                    diff_str = f"{diff_pct:+.1f}"
                elif orig_mean == 0 and ver_mean == 0:
                    diff_pct = 0.0
                    diff_str = "0.0"
                else:
                    diff_pct = None
                    diff_str = "N/A"

                # Statistical test
                t_stat, p_val, cohens_d = welch_t_test(orig_vals, ver_vals)
                effect = interpret_cohens_d(cohens_d)

                if p_val is not None:
                    all_p_values.append(p_val)

                p_str = f"{p_val:.4f}" if p_val is not None else "N/A"
                d_str = f"{cohens_d:.4f}" if cohens_d is not None else "N/A"
                orig_str = f"{orig_mean:.4f}" if orig_mean is not None else "N/A"
                ver_str = f"{ver_mean:.4f}" if ver_mean is not None else "N/A"

                sig_marker = ""
                if p_val is not None and p_val < 0.05:
                    sig_marker = " *"

                print(f"{model:<8} {script:<35} {metric_label:<18} "
                      f"{orig_str:>10} {ver_str:>10} {diff_str:>8} "
                      f"{p_str:>8} {d_str:>8} {effect:>11}{sig_marker}")

                comparison[model][script][metric_key] = {
                    "original_mean": orig_mean,
                    "verify_mean": ver_mean,
                    "diff_pct": round(diff_pct, 2) if diff_pct is not None else None,
                    "t_statistic": round(t_stat, 4) if t_stat is not None else None,
                    "p_value": round(p_val, 4) if p_val is not None else None,
                    "cohens_d": cohens_d,
                    "effect_size": effect,
                    "original_n": len(orig_vals),
                    "verify_n": len(ver_vals),
                }

    print(f"{'='*130}")
    print("  * = statistically significant (p < 0.05)")

    # Summary statistics
    if all_p_values:
        sig_count = sum(1 for p in all_p_values if p < 0.05)
        total_tests = len(all_p_values)
        print(f"\n  Summary: {sig_count}/{total_tests} metrics showed significant differences (p < 0.05)")
        if sig_count == 0:
            print("  Conclusion: No statistically significant differences found — results are reproducible.")
        elif sig_count <= total_tests * 0.05:
            print(f"  Conclusion: {sig_count} significant result(s) out of {total_tests} is within the expected "
                  f"false-positive rate (5%). Results are likely reproducible.")
        else:
            print(f"  Conclusion: {sig_count} significant differences detected. Investigate flagged metrics.")

    # Save comparison
    comp_path = os.path.join(verify_results, "comparison.json")
    os.makedirs(verify_results, exist_ok=True)
    summary = {
        "meta": {
            "original_runs": n_orig,
            "verify_runs": n_ver,
            "total_tests": len(all_p_values),
            "significant_at_005": sum(1 for p in all_p_values if p < 0.05),
            "test_method": "Welch's t-test (two-sided, unequal variance)",
            "effect_size_method": "Cohen's d (pooled standard deviation)",
        },
        "results": comparison,
    }
    with open(comp_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Full comparison saved to {comp_path}")
    return comparison


def main():
    parser = argparse.ArgumentParser(description="Incremental verification runner")
    parser.add_argument("--compare", action="store_true",
                        help="Run one verification iteration then compare against original")
    parser.add_argument("--compare-only", action="store_true",
                        help="Just compare existing verify data against original (no new run)")
    parser.add_argument("--aggregate-only", action="store_true",
                        help="Just re-aggregate existing verify runs (no new run)")
    parser.add_argument("--run-number", type=int, default=None,
                        help="Force a specific run number instead of auto-detecting")
    args = parser.parse_args()

    # Compare-only mode
    if args.compare_only:
        compare_results(ORIGINAL_OUTPUTS, ORIGINAL_RESULTS,
                        OUTPUTS_VERIFY, RESULTS_VERIFY)
        return

    # Aggregate-only mode
    if args.aggregate_only:
        aggregate_all_runs(outputs_dir=OUTPUTS_VERIFY, results_dir=RESULTS_VERIFY)
        return

    # Determine run number
    run_number = args.run_number if args.run_number is not None else detect_next_run(OUTPUTS_VERIFY)
    run_filter = f"run_{run_number}"

    print(f"\n{'#'*60}")
    print(f"  VERIFICATION RUN {run_number}")
    print(f"  Output: {OUTPUTS_VERIFY}/{run_filter}/")
    print(f"  Results: {RESULTS_VERIFY}/{run_filter}/")
    print(f"{'#'*60}")

    # Step 1: Generate code (single run)
    print("\n--- Step 1/4: Generating code ---")
    generate_code(
        prompts_dir=PROMPTS_DIR,
        outputs_dir=OUTPUTS_VERIFY,
        results_dir=RESULTS_VERIFY,
        single_run=run_number,
    )

    # Step 2: Test the generated code
    print("\n--- Step 2/4: Running tests ---")
    run_tests(
        outputs_dir=OUTPUTS_VERIFY,
        results_dir=RESULTS_VERIFY,
        run_filter=run_filter,
    )

    # Step 3: Analyse the generated code
    print("\n--- Step 3/4: Running analysis ---")
    run_analysis(
        outputs_dir=OUTPUTS_VERIFY,
        results_dir=RESULTS_VERIFY,
        run_filter=run_filter,
    )

    # Step 4: Aggregate across ALL existing verify runs
    print("\n--- Step 4/4: Aggregating all verify runs ---")
    aggregate_all_runs(outputs_dir=OUTPUTS_VERIFY, results_dir=RESULTS_VERIFY)

    print(f"\nVerification run {run_number} complete.")

    # Optional comparison
    if args.compare:
        compare_results(ORIGINAL_OUTPUTS, ORIGINAL_RESULTS,
                        OUTPUTS_VERIFY, RESULTS_VERIFY)


if __name__ == "__main__":
    main()
