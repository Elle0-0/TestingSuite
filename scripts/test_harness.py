import os
import glob
import subprocess
import time
import json
import psutil

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PERF_RUNS = 3          # Number of executions per script (take the median)
EXECUTION_TIMEOUT = 120  # Seconds before killing a script

# Directory paths
OUTPUTS_DIR = "../outputs"
RESULTS_DIR = "../results"


def measure_performance(script_path, timeout=EXECUTION_TIMEOUT):
    """Execute a Python script and measure its runtime and peak memory usage."""
    start_time = time.time()
    process = subprocess.Popen(
        ["python3", script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    peak_memory = 0

    try:
        ps = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                mem = ps.memory_info().rss / (1024 * 1024)  # MB
                peak_memory = max(peak_memory, mem)
            except psutil.NoSuchProcess:
                break
            time.sleep(0.05)
        runtime = time.time() - start_time
    except psutil.NoSuchProcess:
        runtime = time.time() - start_time

    stdout, stderr = process.communicate()
    return runtime, peak_memory, stdout.decode(), stderr.decode(), process.returncode


def median(values):
    """Return the median of a list of numbers."""
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def run_tests():
    run_dirs = sorted(glob.glob(os.path.join(OUTPUTS_DIR, "run_*")))
    if not run_dirs:
        print("No run directories found in outputs/. Run generate_code.py first.")
        return

    for run_dir in run_dirs:
        run_name = os.path.basename(run_dir)
        run_results_dir = os.path.join(RESULTS_DIR, run_name)
        os.makedirs(run_results_dir, exist_ok=True)

        results_txt = os.path.join(run_results_dir, "test_results.txt")
        results_json_path = os.path.join(run_results_dir, "test_results.json")
        all_results = {}

        print(f"\n{'='*60}")
        print(f"  Testing {run_name} ({PERF_RUNS} perf runs per script)")
        print(f"{'='*60}")

        with open(results_txt, "w") as out:
            for model_dir in sorted(os.listdir(run_dir)):
                model_path = os.path.join(run_dir, model_dir)
                if not os.path.isdir(model_path):
                    continue

                out.write(f"Model: {model_dir}\n")
                out.write("=" * 50 + "\n")
                all_results[model_dir] = {}

                for script_file in sorted(os.listdir(model_path)):
                    if not script_file.endswith(".py") or script_file.startswith("."):
                        continue

                    script_path = os.path.join(model_path, script_file)
                    out.write(f"  Script: {script_file}\n")
                    print(f"    {model_dir}/{script_file}...", end=" ", flush=True)

                    # Run PERF_RUNS times and collect metrics
                    runtimes = []
                    memories = []
                    last_stdout = ""
                    last_stderr = ""
                    last_returncode = 0

                    for perf_run in range(PERF_RUNS):
                        runtime, memory, stdout, stderr, returncode = measure_performance(script_path)
                        runtimes.append(runtime)
                        memories.append(memory)
                        last_stdout = stdout
                        last_stderr = stderr
                        last_returncode = returncode

                    med_runtime = median(runtimes)
                    med_memory = median(memories)

                    out.write(f"    Exit code: {last_returncode}\n")
                    out.write(f"    Runtime (median of {PERF_RUNS}): {med_runtime:.4f} seconds\n")
                    out.write(f"    Peak Memory (median of {PERF_RUNS}): {med_memory:.2f} MB\n")
                    if last_stdout.strip():
                        out.write(f"    Stdout: {last_stdout.strip()}\n")
                    if last_stderr.strip():
                        out.write(f"    Stderr: {last_stderr.strip()}\n")
                    out.write("\n")

                    all_results[model_dir][script_file] = {
                        "exit_code": last_returncode,
                        "runtime_median": round(med_runtime, 4),
                        "runtime_all": [round(r, 4) for r in runtimes],
                        "memory_median": round(med_memory, 2),
                        "memory_all": [round(m, 2) for m in memories],
                    }

                    status = "PASS" if last_returncode == 0 else "FAIL"
                    print(f"{status} ({med_runtime:.2f}s, {med_memory:.1f}MB)")

                out.write("\n")

        with open(results_json_path, "w") as jf:
            json.dump(all_results, jf, indent=2)

        print(f"  Results: {results_txt}")

    print(f"\nAll runs tested.")


if __name__ == "__main__":
    run_tests()
