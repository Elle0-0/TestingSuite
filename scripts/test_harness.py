import os
import subprocess
import time
import psutil

# Directory paths
OUTPUTS_DIR = "../outputs"
RESULTS_FILE = "../results/test_results.txt"

# Function to measure runtime and memory usage
def measure_performance(script_path):
    start_time = time.time()
    process = subprocess.Popen(
        ["python", script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    pid = process.pid
    process_memory = psutil.Process(pid)

    try:
        while process.poll() is None:
            time.sleep(0.1)
        runtime = time.time() - start_time
        memory_usage = process_memory.memory_info().rss / (1024 * 1024)  # MB
    except psutil.NoSuchProcess:
        runtime = None
        memory_usage = None

    stdout, stderr = process.communicate()
    return runtime, memory_usage, stdout.decode(), stderr.decode()

# Function to test all generated scripts
def run_tests():
    with open(RESULTS_FILE, "w") as results:
        for model_dir in os.listdir(OUTPUTS_DIR):
            model_path = os.path.join(OUTPUTS_DIR, model_dir)

            if os.path.isdir(model_path):
                results.write(f"Testing model: {model_dir}\n")

                for task_dir in os.listdir(model_path):
                    task_path = os.path.join(model_path, task_dir)

                    if os.path.isdir(task_path):
                        results.write(f"  Task: {task_dir}\n")

                        for script_file in os.listdir(task_path):
                            if script_file.endswith(".py"):
                                script_path = os.path.join(task_path, script_file)
                                results.write(f"    Script: {script_file}\n")

                                runtime, memory, stdout, stderr = measure_performance(script_path)

                                results.write(f"      Runtime: {runtime:.2f} seconds\n")
                                results.write(f"      Memory Usage: {memory:.2f} MB\n")
                                results.write(f"      Stdout: {stdout}\n")
                                results.write(f"      Stderr: {stderr}\n")
                                results.write("\n")

if __name__ == "__main__":
    run_tests()