import os
import glob
import subprocess
import json
import math

# Directory paths
OUTPUTS_DIR = "../outputs"
RESULTS_DIR = "../results"


# ---------------------------------------------------------------------------
# Individual analysis functions — each calls a CLI tool and returns its output
# ---------------------------------------------------------------------------

def analyze_cyclomatic_complexity(script_path):
    result = subprocess.run(
        ["radon", "cc", "-s", "-a", "-j", script_path],
        capture_output=True, text=True,
    )
    return result.stdout, result.stderr


def analyze_raw_metrics(script_path):
    result = subprocess.run(
        ["radon", "raw", "-s", "-j", script_path],
        capture_output=True, text=True,
    )
    return result.stdout, result.stderr


def analyze_halstead(script_path):
    result = subprocess.run(
        ["radon", "hal", "-j", script_path],
        capture_output=True, text=True,
    )
    return result.stdout, result.stderr


def analyze_maintainability_index(script_path):
    result = subprocess.run(
        ["radon", "mi", "-s", "-j", script_path],
        capture_output=True, text=True,
    )
    return result.stdout, result.stderr


def analyze_pylint(script_path):
    result = subprocess.run(
        ["pylint", "--output-format=json2",
         "--disable=C0114,C0115,C0116",
         script_path],
        capture_output=True, text=True,
    )
    return result.stdout, result.stderr


def analyze_bandit(script_path):
    result = subprocess.run(
        ["bandit", "-f", "json", "-q", script_path],
        capture_output=True, text=True,
    )
    return result.stdout, result.stderr


# ---------------------------------------------------------------------------
# Helpers for extracting summary numbers from JSON outputs
# ---------------------------------------------------------------------------

def parse_cc_json(raw_json):
    try:
        data = json.loads(raw_json)
        blocks = []
        for file_path, functions in data.items():
            if isinstance(functions, dict) and "error" in functions:
                return {"error": functions["error"]}
            if not isinstance(functions, list):
                continue
            for fn in functions:
                if not isinstance(fn, dict):
                    continue
                blocks.append({
                    "name": fn.get("name", "?"),
                    "type": fn.get("type", "?"),
                    "complexity": fn.get("complexity", 0),
                    "rank": fn.get("rank", "?"),
                })
        total = sum(b["complexity"] for b in blocks)
        avg = total / len(blocks) if blocks else 0
        return {"functions": blocks, "average_cc": round(avg, 2), "total_functions": len(blocks)}
    except (json.JSONDecodeError, TypeError):
        return {"error": "Could not parse CC output"}


def parse_raw_json(raw_json):
    try:
        data = json.loads(raw_json)
        for file_path, metrics in data.items():
            return {
                "loc": metrics.get("loc", 0),
                "lloc": metrics.get("lloc", 0),
                "sloc": metrics.get("sloc", 0),
                "comments": metrics.get("comments", 0),
                "multi": metrics.get("multi", 0),
                "blank": metrics.get("blank", 0),
            }
        return {}
    except (json.JSONDecodeError, TypeError):
        return {"error": "Could not parse raw metrics output"}


def parse_halstead_json(raw_json):
    try:
        data = json.loads(raw_json)
        for file_path, file_data in data.items():
            total = file_data.get("total", [{}])
            if isinstance(total, list) and len(total) > 0:
                h = total[0]
            elif isinstance(total, dict):
                h = total
            else:
                return {"error": "Unexpected Halstead format"}
            return {
                "vocabulary": h.get("vocabulary", 0),
                "length": h.get("length", 0),
                "volume": round(h.get("volume", 0), 2),
                "difficulty": round(h.get("difficulty", 0), 2),
                "effort": round(h.get("effort", 0), 2),
                "time": round(h.get("time", 0), 2),
                "bugs": round(h.get("bugs", 0), 4),
            }
        return {}
    except (json.JSONDecodeError, TypeError):
        return {"error": "Could not parse Halstead output"}


def parse_mi_json(raw_json):
    try:
        data = json.loads(raw_json)
        for file_path, score in data.items():
            if isinstance(score, dict):
                mi_val = score.get("mi", score)
                return {"maintainability_index": round(mi_val, 2) if isinstance(mi_val, (int, float)) else mi_val}
            return {"maintainability_index": round(score, 2) if isinstance(score, (int, float)) else score}
        return {}
    except (json.JSONDecodeError, TypeError):
        return {"error": "Could not parse MI output"}


def parse_pylint_json(raw_json):
    try:
        data = json.loads(raw_json)
        statistics = data.get("statistics", {})
        score = statistics.get("score", None)
        messages = data.get("messages", [])
        by_type = {}
        for msg in messages:
            msg_type = msg.get("type", "unknown")
            by_type[msg_type] = by_type.get(msg_type, 0) + 1
        return {"score": score, "issue_counts": by_type, "total_issues": len(messages)}
    except (json.JSONDecodeError, TypeError):
        return {"error": "Could not parse pylint output"}


def parse_bandit_json(raw_json):
    try:
        data = json.loads(raw_json)
        results = data.get("results", [])
        metrics = data.get("metrics", {}).get("_totals", {})
        by_severity = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for r in results:
            sev = r.get("issue_severity", "LOW")
            by_severity[sev] = by_severity.get(sev, 0) + 1
        return {
            "total_issues": len(results),
            "by_severity": by_severity,
            "confidence_high": metrics.get("CONFIDENCE.HIGH", 0),
        }
    except (json.JSONDecodeError, TypeError):
        return {"error": "Could not parse bandit output"}


# ---------------------------------------------------------------------------
# Per-run analysis
# ---------------------------------------------------------------------------

def analyze_single_run(run_dir, run_results_dir):
    """Run all 6 analysis tools on every script in a single run directory."""
    os.makedirs(run_results_dir, exist_ok=True)
    results_txt = os.path.join(run_results_dir, "analysis_results.txt")
    results_json_path = os.path.join(run_results_dir, "analysis_results.json")
    all_results = {}

    with open(results_txt, "w") as out:
        for model_dir in sorted(os.listdir(run_dir)):
            model_path = os.path.join(run_dir, model_dir)
            if not os.path.isdir(model_path):
                continue

            out.write(f"Model: {model_dir}\n")
            out.write("=" * 60 + "\n")
            all_results[model_dir] = {}

            for script_file in sorted(os.listdir(model_path)):
                if not script_file.endswith(".py") or script_file.startswith("."):
                    continue

                script_path = os.path.join(model_path, script_file)
                out.write(f"\n  Script: {script_file}\n")
                out.write(f"  {'-' * 56}\n")

                script_data = {}

                # 1. Cyclomatic Complexity
                cc_raw, _ = analyze_cyclomatic_complexity(script_path)
                cc_data = parse_cc_json(cc_raw)
                script_data["cyclomatic_complexity"] = cc_data
                out.write(f"    [CC] Average Complexity: {cc_data.get('average_cc', 'N/A')}\n")
                out.write(f"    [CC] Total Functions: {cc_data.get('total_functions', 'N/A')}\n")
                for fn in cc_data.get("functions", []):
                    out.write(f"         {fn['type']} {fn['name']}: {fn['complexity']} ({fn['rank']})\n")

                # 2. Raw Metrics
                raw_raw, _ = analyze_raw_metrics(script_path)
                raw_data = parse_raw_json(raw_raw)
                script_data["raw_metrics"] = raw_data
                out.write(f"    [RAW] LOC: {raw_data.get('loc', 'N/A')}  "
                          f"SLOC: {raw_data.get('sloc', 'N/A')}  "
                          f"Comments: {raw_data.get('comments', 'N/A')}  "
                          f"Blanks: {raw_data.get('blank', 'N/A')}\n")

                # 3. Halstead Metrics
                hal_raw, _ = analyze_halstead(script_path)
                hal_data = parse_halstead_json(hal_raw)
                script_data["halstead"] = hal_data
                out.write(f"    [HAL] Volume: {hal_data.get('volume', 'N/A')}  "
                          f"Difficulty: {hal_data.get('difficulty', 'N/A')}  "
                          f"Effort: {hal_data.get('effort', 'N/A')}\n")
                out.write(f"    [HAL] Est. Time: {hal_data.get('time', 'N/A')}s  "
                          f"Est. Bugs: {hal_data.get('bugs', 'N/A')}\n")

                # 4. Maintainability Index
                mi_raw, _ = analyze_maintainability_index(script_path)
                mi_data = parse_mi_json(mi_raw)
                script_data["maintainability_index"] = mi_data
                mi_score = mi_data.get("maintainability_index", "N/A")
                out.write(f"    [MI]  Score: {mi_score}\n")

                # 5. Pylint
                pl_raw, _ = analyze_pylint(script_path)
                pl_data = parse_pylint_json(pl_raw)
                script_data["pylint"] = pl_data
                out.write(f"    [PL]  Score: {pl_data.get('score', 'N/A')}/10  "
                          f"Issues: {pl_data.get('total_issues', 'N/A')}\n")
                for issue_type, count in pl_data.get("issue_counts", {}).items():
                    out.write(f"          {issue_type}: {count}\n")

                # 6. Bandit
                bd_raw, _ = analyze_bandit(script_path)
                bd_data = parse_bandit_json(bd_raw)
                script_data["bandit"] = bd_data
                out.write(f"    [SEC] Total Findings: {bd_data.get('total_issues', 'N/A')}\n")
                for sev, count in bd_data.get("by_severity", {}).items():
                    if count > 0:
                        out.write(f"          {sev}: {count}\n")

                all_results[model_dir][script_file] = script_data

            out.write("\n\n")

    with open(results_json_path, "w") as jf:
        json.dump(all_results, jf, indent=2)

    return all_results


# ---------------------------------------------------------------------------
# Aggregation across runs — compute mean ± std for every metric
# ---------------------------------------------------------------------------

def _safe_float(val):
    """Extract a numeric value, returning None if not possible."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict) and "mi" in val:
        return float(val["mi"])
    return None


def _stats(values):
    """Compute mean and std for a list of numbers (skipping None)."""
    nums = [v for v in values if v is not None]
    if not nums:
        return {"mean": None, "std": None, "n": 0}
    mean = sum(nums) / len(nums)
    if len(nums) > 1:
        variance = sum((x - mean) ** 2 for x in nums) / (len(nums) - 1)
        std = math.sqrt(variance)
    else:
        std = 0.0
    return {"mean": round(mean, 4), "std": round(std, 4), "n": len(nums)}


def aggregate_results(all_run_data, all_test_data, all_retry_data):
    """Aggregate analysis, test, and retry data across all runs."""
    aggregated = {}

    # Collect all model names and script names from the first run
    models = set()
    scripts = set()
    for run_data in all_run_data:
        for model in run_data:
            models.add(model)
            for script in run_data[model]:
                scripts.add(script)

    for model in sorted(models):
        aggregated[model] = {}
        for script in sorted(scripts):
            # Collect per-run values for this model+script
            cc_vals = []
            sloc_vals = []
            loc_vals = []
            hal_volume_vals = []
            hal_effort_vals = []
            hal_bugs_vals = []
            mi_vals = []
            pylint_vals = []
            bandit_vals = []
            runtime_vals = []
            memory_vals = []
            retry_counts = []
            pass_count = 0
            total_runs = 0

            for i, run_data in enumerate(all_run_data):
                if model not in run_data or script not in run_data[model]:
                    continue
                total_runs += 1
                sd = run_data[model][script]

                cc_vals.append(_safe_float(sd.get("cyclomatic_complexity", {}).get("average_cc")))
                raw = sd.get("raw_metrics", {})
                sloc_vals.append(_safe_float(raw.get("sloc")))
                loc_vals.append(_safe_float(raw.get("loc")))
                hal = sd.get("halstead", {})
                hal_volume_vals.append(_safe_float(hal.get("volume")))
                hal_effort_vals.append(_safe_float(hal.get("effort")))
                hal_bugs_vals.append(_safe_float(hal.get("bugs")))
                mi_vals.append(_safe_float(sd.get("maintainability_index", {}).get("maintainability_index")))
                pylint_vals.append(_safe_float(sd.get("pylint", {}).get("score")))
                bandit_vals.append(_safe_float(sd.get("bandit", {}).get("total_issues")))

            # Test results (runtime/memory)
            for test_data in all_test_data:
                if model not in test_data or script not in test_data[model]:
                    continue
                td = test_data[model][script]
                runtime_vals.append(_safe_float(td.get("runtime_median")))
                memory_vals.append(_safe_float(td.get("memory_median")))

            # Retry data
            # Prompt file name = script name with _solution.py → .txt
            prompt_file = script.replace("_solution.py", ".txt")
            for retry_data in all_retry_data:
                if model not in retry_data or prompt_file not in retry_data[model]:
                    continue
                rd = retry_data[model][prompt_file]
                retry_counts.append(rd.get("total_attempts", 0))
                if rd.get("final_status") == "pass":
                    pass_count += 1

            aggregated[model][script] = {
                "runs": total_runs,
                "pass_rate": round(pass_count / total_runs, 2) if total_runs else 0,
                "retries": _stats(retry_counts),
                "runtime": _stats(runtime_vals),
                "memory": _stats(memory_vals),
                "cyclomatic_complexity": _stats(cc_vals),
                "sloc": _stats(sloc_vals),
                "loc": _stats(loc_vals),
                "halstead_volume": _stats(hal_volume_vals),
                "halstead_effort": _stats(hal_effort_vals),
                "halstead_bugs": _stats(hal_bugs_vals),
                "maintainability_index": _stats(mi_vals),
                "pylint_score": _stats(pylint_vals),
                "bandit_findings": _stats(bandit_vals),
            }

    return aggregated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def aggregate_all_runs(outputs_dir=OUTPUTS_DIR, results_dir=RESULTS_DIR):
    """Re-aggregate across all existing runs by loading saved per-run JSON files.

    Unlike run_analysis(), this does NOT re-run the analysis tools — it just
    loads the previously saved JSON results and computes mean ± std.
    """
    run_dirs = sorted(glob.glob(os.path.join(outputs_dir, "run_*")))
    if not run_dirs:
        print("No run directories found for aggregation.")
        return

    all_run_analysis = []
    all_test_data = []
    all_retry_data = []

    for run_dir in run_dirs:
        run_name = os.path.basename(run_dir)
        run_results_dir = os.path.join(results_dir, run_name)

        analysis_json = os.path.join(run_results_dir, "analysis_results.json")
        if os.path.exists(analysis_json):
            with open(analysis_json) as f:
                all_run_analysis.append(json.load(f))

        test_json = os.path.join(run_results_dir, "test_results.json")
        if os.path.exists(test_json):
            with open(test_json) as f:
                all_test_data.append(json.load(f))

        retry_json = os.path.join(run_results_dir, "retry_log.json")
        if os.path.exists(retry_json):
            with open(retry_json) as f:
                all_retry_data.append(json.load(f))

    if not all_run_analysis:
        print("No analysis results found to aggregate.")
        return

    print(f"Aggregating across {len(all_run_analysis)} runs...")
    aggregated = aggregate_results(all_run_analysis, all_test_data, all_retry_data)
    agg_path = os.path.join(results_dir, "aggregated_results.json")
    os.makedirs(results_dir, exist_ok=True)
    with open(agg_path, "w") as f:
        json.dump(aggregated, f, indent=2)
    print(f"Aggregated results saved to {agg_path}")
    return aggregated


def run_analysis(outputs_dir=OUTPUTS_DIR, results_dir=RESULTS_DIR, run_filter=None):
    run_dirs = sorted(glob.glob(os.path.join(outputs_dir, "run_*")))
    if run_filter:
        run_dirs = [d for d in run_dirs if os.path.basename(d) == run_filter]
    if not run_dirs:
        print("No run directories found. Run generate_code.py first.")
        return

    all_run_analysis = []
    all_test_data = []
    all_retry_data = []

    for run_dir in run_dirs:
        run_name = os.path.basename(run_dir)
        run_results_dir = os.path.join(results_dir, run_name)

        print(f"\nAnalysing {run_name}...")
        analysis = analyze_single_run(run_dir, run_results_dir)
        all_run_analysis.append(analysis)

        # Load test results for this run (if available)
        test_json = os.path.join(run_results_dir, "test_results.json")
        if os.path.exists(test_json):
            with open(test_json) as f:
                all_test_data.append(json.load(f))

        # Load retry log for this run (if available)
        retry_json = os.path.join(run_results_dir, "retry_log.json")
        if os.path.exists(retry_json):
            with open(retry_json) as f:
                all_retry_data.append(json.load(f))

        print(f"  Saved to {run_results_dir}/")

    # Aggregate across all runs
    if len(all_run_analysis) > 0:
        print(f"\nAggregating across {len(all_run_analysis)} runs...")
        aggregated = aggregate_results(all_run_analysis, all_test_data, all_retry_data)
        agg_path = os.path.join(results_dir, "aggregated_results.json")
        with open(agg_path, "w") as f:
            json.dump(aggregated, f, indent=2)
        print(f"Aggregated results saved to {agg_path}")

    print("\nAnalysis complete.")


if __name__ == "__main__":
    run_analysis()
