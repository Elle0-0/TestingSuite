#!/usr/bin/env python3
"""Score generated solutions against formal requirements extracted from prompts.

Produces a Requirement Coverage Score (RCS) per model per prompt, enabling
normalised complexity metrics that distinguish justified complexity from
over-engineering.

Usage (run from scripts/):
    python score_requirements.py                    # Auto-score all runs
    python score_requirements.py --run run_1        # Score a specific run
    python score_requirements.py --generate-template # Create manual scoring template
    python score_requirements.py --with-manual PATH  # Merge manual scores
    python score_requirements.py --normalize         # Compute normalised metrics
"""

import ast
import argparse
import glob
import json
import math
import os
import re
import sys

REQUIREMENTS_PATH = "../requirements/requirements.json"
OUTPUTS_DIR = "../outputs"
RESULTS_DIR = "../results"


# ---------------------------------------------------------------------------
# AST-based checker — analyses Python source without executing it
# ---------------------------------------------------------------------------

class ASTChecker:
    """Analyses a Python source file via its AST and raw text."""

    def __init__(self, filepath):
        with open(filepath, encoding="utf-8", errors="replace") as f:
            self.source = f.read()
        self.tree = ast.parse(self.source)
        self.filepath = filepath

    def has_function(self, name):
        """Check if a function (or async function) with the given name exists."""
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == name:
                    return True
        return False

    def has_function_params(self, func_name, params):
        """Check if the named function accepts all listed parameter names."""
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name != func_name:
                    continue
                arg_names = [a.arg for a in node.args.args]
                arg_names += [a.arg for a in node.args.kwonlyargs]
                # Also check *args/**kwargs names and defaults aren't hiding params
                if all(p in arg_names for p in params):
                    return True
        return False

    def has_class(self, name):
        """Check if a class with the given name exists."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == name:
                return True
        return False

    def has_method(self, class_name, method_name):
        """Check if a class defines a method (including async) with the given name."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in ast.walk(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == method_name:
                            return True
        return False

    def has_import(self, module_name):
        """Check if a module is imported (import X or from X import ...)."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if module_name in alias.name:
                        return True
            if isinstance(node, ast.ImportFrom):
                if node.module and module_name in node.module:
                    return True
        return False

    def has_any_import(self, module_names):
        return any(self.has_import(m) for m in module_names)

    def has_try_except(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Try):
                return True
        return False

    def has_raise(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Raise):
                return True
        return False

    def source_contains(self, pattern):
        return bool(re.search(pattern, self.source))

    def source_contains_any(self, patterns):
        return any(re.search(p, self.source) for p in patterns)


# ---------------------------------------------------------------------------
# Check dispatcher — maps check specs from requirements.json to checker calls
# ---------------------------------------------------------------------------

def run_check(checker, spec):
    """Evaluate a single check specification against a checker instance."""
    kind = spec["check"]

    if kind == "function_exists":
        return checker.has_function(spec["name"])
    elif kind == "function_params":
        return checker.has_function_params(spec["name"], spec["params"])
    elif kind == "class_exists":
        return checker.has_class(spec["name"])
    elif kind == "class_method":
        return checker.has_method(spec["class"], spec["method"])
    elif kind == "has_import":
        return checker.has_import(spec["module"])
    elif kind == "has_any_import":
        return checker.has_any_import(spec["modules"])
    elif kind == "has_try_except":
        return checker.has_try_except()
    elif kind == "has_raise":
        return checker.has_raise()
    elif kind == "source_contains":
        return checker.source_contains(spec["pattern"])
    elif kind == "source_contains_any":
        return checker.source_contains_any(spec["patterns"])
    elif kind == "compound_and":
        return all(run_check(checker, sub) for sub in spec["checks"])
    elif kind == "compound_or":
        return any(run_check(checker, sub) for sub in spec["checks"])
    else:
        print(f"  WARNING: Unknown check type '{kind}'")
        return None


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------

def score_solution(script_path, requirements, manual_scores=None):
    """Score a single solution file against its requirements list.

    Returns a dict mapping requirement IDs to their results.
    manual_scores: optional dict of {req_id: "pass"|"fail"|"partial"} for manual items.
    """
    try:
        checker = ASTChecker(script_path)
    except SyntaxError as e:
        return {
            r["id"]: {"status": "error", "detail": f"SyntaxError: {e}",
                       "description": r["description"], "auto": r["test_type"] == "auto"}
            for r in requirements
        }
    except FileNotFoundError:
        return {
            r["id"]: {"status": "missing", "detail": "Solution file not found",
                       "description": r["description"], "auto": r["test_type"] == "auto"}
            for r in requirements
        }

    results = {}
    for req in requirements:
        rid = req["id"]

        if req["test_type"] == "auto":
            passed = run_check(checker, req["check"])
            results[rid] = {
                "status": "pass" if passed else "fail",
                "description": req["description"],
                "auto": True,
            }
        else:
            # Manual requirement — check if we have a manual score
            if manual_scores and rid in manual_scores:
                results[rid] = {
                    "status": manual_scores[rid],
                    "description": req["description"],
                    "auto": False,
                }
            else:
                results[rid] = {
                    "status": "unscored",
                    "description": req["description"],
                    "auto": False,
                    "guidance": req.get("guidance", ""),
                }

    return results


def compute_coverage(results):
    """Compute coverage stats from a scored results dict."""
    total = len(results)
    auto_pass = sum(1 for r in results.values() if r["auto"] and r["status"] == "pass")
    auto_fail = sum(1 for r in results.values() if r["auto"] and r["status"] == "fail")
    manual_pass = sum(1 for r in results.values() if not r["auto"] and r["status"] == "pass")
    manual_fail = sum(1 for r in results.values() if not r["auto"] and r["status"] == "fail")
    manual_partial = sum(1 for r in results.values() if not r["auto"] and r["status"] == "partial")
    unscored = sum(1 for r in results.values() if r["status"] == "unscored")
    errors = sum(1 for r in results.values() if r["status"] in ("error", "missing"))

    scored_total = total - unscored - errors
    passed = auto_pass + manual_pass + (manual_partial * 0.5)
    coverage = round(passed / scored_total, 4) if scored_total > 0 else None

    return {
        "total_requirements": total,
        "auto_pass": auto_pass,
        "auto_fail": auto_fail,
        "manual_pass": manual_pass,
        "manual_fail": manual_fail,
        "manual_partial": manual_partial,
        "unscored": unscored,
        "errors": errors,
        "scored_total": scored_total,
        "passed": passed,
        "coverage": coverage,
    }


# ---------------------------------------------------------------------------
# Run scoring across all models/scripts in a run directory
# ---------------------------------------------------------------------------

def score_run(run_dir, requirements_data, manual_scores=None):
    """Score all solutions in a single run directory.

    Returns {model: {solution_file: {coverage: ..., requirements: {...}}}}
    """
    run_results = {}

    for model_dir in sorted(os.listdir(run_dir)):
        model_path = os.path.join(run_dir, model_dir)
        if not os.path.isdir(model_path):
            continue

        run_results[model_dir] = {}

        for prompt_key, prompt_info in requirements_data["prompts"].items():
            solution_file = prompt_info["solution_file"]
            script_path = os.path.join(model_path, solution_file)
            reqs = prompt_info["requirements"]

            # Get manual scores for this model + solution if available
            ms = None
            if manual_scores and model_dir in manual_scores:
                ms = manual_scores[model_dir].get(solution_file, {})

            results = score_solution(script_path, reqs, ms)
            coverage = compute_coverage(results)

            run_results[model_dir][solution_file] = {
                "prompt": prompt_key,
                "coverage": coverage,
                "requirements": results,
            }

    return run_results


def score_all_runs(outputs_dir, requirements_data, manual_scores=None, run_filter=None):
    """Score all runs and aggregate coverage across runs."""
    run_dirs = sorted(glob.glob(os.path.join(outputs_dir, "run_*")))
    if run_filter:
        run_dirs = [d for d in run_dirs if os.path.basename(d) == run_filter]

    if not run_dirs:
        print("No run directories found.")
        return None, None

    all_run_scores = {}
    for run_dir in run_dirs:
        run_name = os.path.basename(run_dir)
        print(f"Scoring {run_name}...")
        scores = score_run(run_dir, requirements_data, manual_scores)
        all_run_scores[run_name] = scores

        # Save per-run scores
        results_dir = os.path.join(RESULTS_DIR, run_name)
        os.makedirs(results_dir, exist_ok=True)
        out_path = os.path.join(results_dir, "requirement_scores.json")
        with open(out_path, "w") as f:
            json.dump(scores, f, indent=2)

    # Aggregate across runs
    aggregated = aggregate_coverage(all_run_scores)
    return all_run_scores, aggregated


def aggregate_coverage(all_run_scores):
    """Aggregate coverage scores across runs (mean ± std per model per script)."""
    from collections import defaultdict

    # Collect coverage values per model per script
    coverage_vals = defaultdict(lambda: defaultdict(list))

    for run_name, run_data in all_run_scores.items():
        for model, scripts in run_data.items():
            for script, data in scripts.items():
                cov = data["coverage"]["coverage"]
                if cov is not None:
                    coverage_vals[model][script].append(cov)

    aggregated = {}
    for model in sorted(coverage_vals):
        aggregated[model] = {}
        model_coverages = []
        for script in sorted(coverage_vals[model]):
            vals = coverage_vals[model][script]
            mean = sum(vals) / len(vals) if vals else 0
            std = 0.0
            if len(vals) > 1:
                std = math.sqrt(sum((x - mean) ** 2 for x in vals) / (len(vals) - 1))
            aggregated[model][script] = {
                "coverage_mean": round(mean, 4),
                "coverage_std": round(std, 4),
                "n": len(vals),
            }
            model_coverages.extend(vals)

        # Model-level summary
        if model_coverages:
            overall_mean = sum(model_coverages) / len(model_coverages)
            overall_std = 0.0
            if len(model_coverages) > 1:
                overall_std = math.sqrt(
                    sum((x - overall_mean) ** 2 for x in model_coverages)
                    / (len(model_coverages) - 1)
                )
            aggregated[model]["_overall"] = {
                "coverage_mean": round(overall_mean, 4),
                "coverage_std": round(overall_std, 4),
                "n": len(model_coverages),
            }

    return aggregated


# ---------------------------------------------------------------------------
# Manual scoring template generation
# ---------------------------------------------------------------------------

def generate_manual_template(requirements_data, outputs_dir, run_name="run_1"):
    """Generate a JSON template for manual scoring of manual-type requirements."""
    run_dir = os.path.join(outputs_dir, run_name)
    if not os.path.isdir(run_dir):
        print(f"Run directory not found: {run_dir}")
        return None

    template = {}
    manual_count = 0

    for model_dir in sorted(os.listdir(run_dir)):
        model_path = os.path.join(run_dir, model_dir)
        if not os.path.isdir(model_path):
            continue

        template[model_dir] = {}

        for prompt_key, prompt_info in requirements_data["prompts"].items():
            solution_file = prompt_info["solution_file"]
            manual_reqs = [r for r in prompt_info["requirements"] if r["test_type"] == "manual"]
            if not manual_reqs:
                continue

            template[model_dir][solution_file] = {}
            for req in manual_reqs:
                template[model_dir][solution_file][req["id"]] = {
                    "status": "FILL_IN: pass / fail / partial",
                    "description": req["description"],
                    "guidance": req.get("guidance", ""),
                }
                manual_count += 1

    print(f"Template has {manual_count} manual checks to score "
          f"({manual_count // 3} per model across {len(template)} models).")
    return template


# ---------------------------------------------------------------------------
# Normalised complexity metrics
# ---------------------------------------------------------------------------

def compute_normalised_metrics(aggregated_coverage, results_dir):
    """Load aggregated_results.json and divide complexity metrics by coverage."""
    agg_path = os.path.join(results_dir, "aggregated_results.json")
    if not os.path.exists(agg_path):
        print(f"Aggregated results not found: {agg_path}")
        return None

    with open(agg_path) as f:
        agg_results = json.load(f)

    normalised = {}

    for model in agg_results:
        normalised[model] = {}
        for script in agg_results[model]:
            metrics = agg_results[model][script]

            # Get coverage for this model+script
            cov_data = aggregated_coverage.get(model, {}).get(script, {})
            coverage = cov_data.get("coverage_mean")

            if coverage is None or coverage == 0:
                normalised[model][script] = {
                    "coverage": None,
                    "note": "No coverage data — cannot normalise",
                }
                continue

            # Raw metrics
            sloc_mean = metrics.get("sloc", {}).get("mean")
            cc_mean = metrics.get("cyclomatic_complexity", {}).get("mean")
            hal_effort_mean = metrics.get("halstead_effort", {}).get("mean")
            hal_volume_mean = metrics.get("halstead_volume", {}).get("mean")

            normalised[model][script] = {
                "coverage": coverage,
                "raw_sloc": sloc_mean,
                "raw_cc": cc_mean,
                "raw_halstead_effort": hal_effort_mean,
                "sloc_per_coverage": round(sloc_mean / coverage, 2) if sloc_mean else None,
                "cc_per_coverage": round(cc_mean / coverage, 2) if cc_mean else None,
                "halstead_effort_per_coverage": round(hal_effort_mean / coverage, 2) if hal_effort_mean else None,
            }

    # Model-level summaries
    for model in normalised:
        total_sloc_norm = []
        total_cc_norm = []
        total_effort_norm = []
        coverages = []

        for script, data in normalised[model].items():
            if script.startswith("_"):
                continue
            if data.get("coverage") is None:
                continue
            coverages.append(data["coverage"])
            if data.get("sloc_per_coverage") is not None:
                total_sloc_norm.append(data["sloc_per_coverage"])
            if data.get("cc_per_coverage") is not None:
                total_cc_norm.append(data["cc_per_coverage"])
            if data.get("halstead_effort_per_coverage") is not None:
                total_effort_norm.append(data["halstead_effort_per_coverage"])

        normalised[model]["_summary"] = {
            "avg_coverage": round(sum(coverages) / len(coverages), 4) if coverages else None,
            "avg_sloc_per_coverage": round(sum(total_sloc_norm) / len(total_sloc_norm), 2) if total_sloc_norm else None,
            "avg_cc_per_coverage": round(sum(total_cc_norm) / len(total_cc_norm), 2) if total_cc_norm else None,
            "avg_halstead_effort_per_coverage": round(sum(total_effort_norm) / len(total_effort_norm), 2) if total_effort_norm else None,
        }

    return normalised


# ---------------------------------------------------------------------------
# Pretty-printed summary table
# ---------------------------------------------------------------------------

def print_summary(aggregated_coverage, normalised=None):
    """Print a summary table of coverage per model."""
    print("\n" + "=" * 72)
    print("REQUIREMENT COVERAGE SUMMARY")
    print("=" * 72)

    # Model-level overview
    print(f"\n{'Model':<20} {'Avg Coverage':>14} {'Std':>8} {'N':>5}")
    print("-" * 50)

    for model in sorted(aggregated_coverage):
        overall = aggregated_coverage[model].get("_overall", {})
        mean = overall.get("coverage_mean")
        std = overall.get("coverage_std")
        n = overall.get("n")
        if mean is not None:
            print(f"{model:<20} {mean*100:>13.1f}% {std*100:>7.1f}% {n:>5}")

    # Per-script breakdown
    print(f"\n{'Script':<45} ", end="")
    models = sorted(m for m in aggregated_coverage if not m.startswith("_"))
    for m in models:
        print(f"{m:>12}", end="")
    print()
    print("-" * (45 + 12 * len(models)))

    all_scripts = set()
    for model in models:
        for script in aggregated_coverage[model]:
            if not script.startswith("_"):
                all_scripts.add(script)

    for script in sorted(all_scripts):
        print(f"{script:<45} ", end="")
        for model in models:
            cov = aggregated_coverage[model].get(script, {}).get("coverage_mean")
            if cov is not None:
                print(f"{cov*100:>11.1f}%", end="")
            else:
                print(f"{'N/A':>12}", end="")
        print()

    # Normalised metrics (if available)
    if normalised:
        print(f"\n{'=' * 72}")
        print("NORMALISED COMPLEXITY (per unit coverage)")
        print("=" * 72)
        print(f"\n{'Model':<20} {'Coverage':>10} {'SLOC/Cov':>10} {'CC/Cov':>10} {'Effort/Cov':>12}")
        print("-" * 65)

        for model in sorted(normalised):
            summary = normalised[model].get("_summary", {})
            cov = summary.get("avg_coverage")
            sloc = summary.get("avg_sloc_per_coverage")
            cc = summary.get("avg_cc_per_coverage")
            effort = summary.get("avg_halstead_effort_per_coverage")

            if cov is not None:
                print(f"{model:<20} {cov*100:>9.1f}% "
                      f"{sloc if sloc else 'N/A':>10} "
                      f"{cc if cc else 'N/A':>10} "
                      f"{effort if effort else 'N/A':>12}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Score solutions against formal requirements")
    parser.add_argument("--run", type=str, default=None,
                        help="Score only this run (e.g., run_1)")
    parser.add_argument("--generate-template", action="store_true",
                        help="Generate manual scoring template for run_1")
    parser.add_argument("--template-run", type=str, default="run_1",
                        help="Which run to use for the template (default: run_1)")
    parser.add_argument("--with-manual", type=str, default=None,
                        help="Path to filled manual_scores.json")
    parser.add_argument("--normalize", action="store_true",
                        help="Compute normalised complexity metrics")
    parser.add_argument("--outputs-dir", type=str, default=OUTPUTS_DIR)
    parser.add_argument("--results-dir", type=str, default=RESULTS_DIR)
    args = parser.parse_args()

    # Load requirements
    with open(REQUIREMENTS_PATH) as f:
        requirements_data = json.load(f)

    total_reqs = sum(
        len(p["requirements"])
        for p in requirements_data["prompts"].values()
    )
    auto_reqs = sum(
        sum(1 for r in p["requirements"] if r["test_type"] == "auto")
        for p in requirements_data["prompts"].values()
    )
    manual_reqs = total_reqs - auto_reqs
    print(f"Loaded {total_reqs} requirements ({auto_reqs} auto, {manual_reqs} manual)")

    # Generate manual template
    if args.generate_template:
        template = generate_manual_template(
            requirements_data, args.outputs_dir, args.template_run)
        if template:
            out_path = os.path.join(args.results_dir, "manual_scores_template.json")
            os.makedirs(args.results_dir, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(template, f, indent=2)
            print(f"Template saved to {out_path}")
            print("Fill in 'status' fields with: pass / fail / partial")
            print("Then re-run with: python score_requirements.py --with-manual "
                  f"{out_path}")
        return

    # Load manual scores if provided
    manual_scores = None
    if args.with_manual:
        with open(args.with_manual) as f:
            raw = json.load(f)
        # Flatten: strip guidance/description, keep only status
        manual_scores = {}
        for model, scripts in raw.items():
            manual_scores[model] = {}
            for script, reqs in scripts.items():
                manual_scores[model][script] = {}
                for rid, data in reqs.items():
                    status = data if isinstance(data, str) else data.get("status", "unscored")
                    if status not in ("pass", "fail", "partial"):
                        continue
                    manual_scores[model][script][rid] = status
        print(f"Loaded manual scores from {args.with_manual}")

    # Score runs
    all_run_scores, aggregated = score_all_runs(
        args.outputs_dir, requirements_data, manual_scores, args.run)

    if aggregated is None:
        return

    # Save aggregated coverage
    agg_path = os.path.join(args.results_dir, "requirement_coverage.json")
    os.makedirs(args.results_dir, exist_ok=True)
    with open(agg_path, "w") as f:
        json.dump(aggregated, f, indent=2)
    print(f"\nAggregated coverage saved to {agg_path}")

    # Normalised metrics
    normalised = None
    if args.normalize:
        normalised = compute_normalised_metrics(aggregated, args.results_dir)
        if normalised:
            norm_path = os.path.join(args.results_dir, "normalised_results.json")
            with open(norm_path, "w") as f:
                json.dump(normalised, f, indent=2)
            print(f"Normalised results saved to {norm_path}")

    # Print summary
    print_summary(aggregated, normalised)


if __name__ == "__main__":
    main()
