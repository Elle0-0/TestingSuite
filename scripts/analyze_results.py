import os
import subprocess

# Directory paths
OUTPUTS_DIR = "../outputs"
RESULTS_FILE = "../results/analysis_results.txt"

# Function to analyze code complexity using radon
def analyze_complexity(script_path):
    try:
        result = subprocess.run(
            ["radon", "cc", "-s", script_path], capture_output=True, text=True
        )
        return result.stdout
    except Exception as e:
        return f"Error analyzing {script_path}: {e}"

# Function to analyze all generated scripts
def run_analysis():
    with open(RESULTS_FILE, "w") as results:
        for model_dir in os.listdir(OUTPUTS_DIR):
            model_path = os.path.join(OUTPUTS_DIR, model_dir)

            if os.path.isdir(model_path):
                results.write(f"Analyzing model: {model_dir}\n")

                for task_dir in os.listdir(model_path):
                    task_path = os.path.join(model_path, task_dir)

                    if os.path.isdir(task_path):
                        results.write(f"  Task: {task_dir}\n")

                        for script_file in os.listdir(task_path):
                            if script_file.endswith(".py"):
                                script_path = os.path.join(task_path, script_file)
                                results.write(f"    Script: {script_file}\n")

                                complexity = analyze_complexity(script_path)
                                results.write(f"      Complexity Analysis:\n{complexity}\n")

if __name__ == "__main__":
    run_analysis()