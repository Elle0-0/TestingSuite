import os
import subprocess
import json
from dotenv import load_dotenv
import openai
import anthropic
from google import genai

# Load API keys from .env file (looks in parent directory and current directory)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GCP_PROJECT = os.getenv("GCP_PROJECT")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

if not OPENAI_API_KEY or not ANTHROPIC_API_KEY:
    raise EnvironmentError(
        "Missing API keys. Create a .env file in the project root with:\n"
        "  OPENAI_API_KEY=your-key\n"
        "  ANTHROPIC_API_KEY=your-key\n"
        "  GCP_PROJECT=your-gcp-project-id"
    )

if not GCP_PROJECT:
    raise EnvironmentError(
        "Missing GCP_PROJECT in .env file. Set it to your Google Cloud project ID.\n"
        "Also run: gcloud auth application-default login"
    )

# Initialise clients
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
gemini_client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)

SYSTEM_INSTRUCTION = "You are a Python programming assistant. Respond ONLY with valid Python code. Do not include explanations, markdown fences, or commentary."

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NUM_RUNS = 5           # Number of generation runs for statistical validity
MAX_RETRIES = 3        # Max retry attempts per script on failure
EXECUTION_TIMEOUT = 60  # Seconds before a script execution is killed
MAX_OUTPUT_TOKENS = 16384  # Uniform token cap across all models

RETRY_PROMPT = (
    "The code you provided produced the following error when executed:\n\n"
    "{error}\n\n"
    "Please provide the complete corrected Python code that fixes this error."
)


# ---------------------------------------------------------------------------
# Model call functions — accept a multi-turn messages list
# Each message is {"role": "user"|"assistant", "content": str}
# ---------------------------------------------------------------------------

def call_gpt(messages):
    api_messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    for msg in messages:
        api_messages.append({"role": msg["role"], "content": msg["content"]})
    response = openai_client.chat.completions.create(
        model="gpt-5.4-2026-03-05",
        messages=api_messages,
        max_completion_tokens=MAX_OUTPUT_TOKENS,
    )
    return response.choices[0].message.content


def call_claude(messages):
    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    response = anthropic_client.messages.create(
        model="claude-opus-4-6",
        max_tokens=MAX_OUTPUT_TOKENS,
        system=SYSTEM_INSTRUCTION,
        messages=api_messages,
    )
    return response.content[0].text


def call_gemini(messages):
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        text = msg["content"]
        # Prepend system instruction to the first user message
        if role == "user" and not contents:
            text = f"{SYSTEM_INSTRUCTION}\n\n{text}"
        contents.append({"role": role, "parts": [{"text": text}]})
    response = gemini_client.models.generate_content(
        model="gemini-2.5-pro",
        contents=contents,
        config={"max_output_tokens": MAX_OUTPUT_TOKENS},
    )
    return response.text


def strip_markdown_fences(code):
    """Remove markdown code fences (```python ... ```) from LLM output."""
    lines = code.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def execute_script(script_path, timeout=EXECUTION_TIMEOUT):
    """Execute a Python script and return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Script timed out after {timeout} seconds"


MODELS = {
    "gpt": call_gpt,
    "claude": call_claude,
    "gemini": call_gemini,
}

# Directory paths
PROMPTS_DIR = "../prompts"
OUTPUTS_DIR = "../outputs"
RESULTS_DIR = "../results"


def generate_code(prompts_dir=PROMPTS_DIR, outputs_dir=OUTPUTS_DIR,
                  results_dir=RESULTS_DIR, num_runs=NUM_RUNS, single_run=None):
    runs = [single_run] if single_run is not None else range(1, num_runs + 1)
    total = 1 if single_run is not None else num_runs
    for run in runs:
        print(f"\n{'='*60}")
        print(f"  RUN {run}/{total}")
        print(f"{'='*60}")

        run_output_dir = os.path.join(outputs_dir, f"run_{run}")
        run_results_dir = os.path.join(results_dir, f"run_{run}")
        retry_log = {}

        for model_name, model_fn in MODELS.items():
            model_output_dir = os.path.join(run_output_dir, model_name)
            os.makedirs(model_output_dir, exist_ok=True)
            retry_log[model_name] = {}

            for prompt_file in sorted(os.listdir(prompts_dir)):
                if not prompt_file.endswith(".txt"):
                    continue

                prompt_path = os.path.join(prompts_dir, prompt_file)
                with open(prompt_path, "r") as f:
                    prompt = f.read()

                base_name = os.path.splitext(prompt_file)[0]
                output_file = os.path.join(
                    model_output_dir, f"{base_name}_solution.py"
                )

                script_log = {"attempts": [], "final_status": "unknown", "total_attempts": 0}
                messages = [{"role": "user", "content": prompt}]

                try:
                    for attempt in range(1, MAX_RETRIES + 2):
                        label = "initial" if attempt == 1 else f"retry_{attempt - 1}"
                        print(f"  [{model_name}] {prompt_file} — {label}...")

                        raw_response = model_fn(messages)
                        code = strip_markdown_fences(raw_response)

                        temp_file = os.path.join(model_output_dir, f".{base_name}_pending.py")
                        with open(temp_file, "w") as f:
                            f.write(code)

                        exit_code, stdout, stderr = execute_script(temp_file)

                        attempt_data = {
                            "attempt": attempt,
                            "label": label,
                            "exit_code": exit_code,
                            "stdout_snippet": stdout.strip()[:300] if stdout else "",
                            "stderr_snippet": stderr.strip()[:500] if stderr else "",
                            "success": exit_code == 0,
                        }
                        script_log["attempts"].append(attempt_data)

                        if exit_code == 0:
                            os.replace(temp_file, output_file)
                            print(f"  [{model_name}] {prompt_file} — PASSED on {label}")
                            script_log["final_status"] = "pass"
                            script_log["total_attempts"] = attempt
                            break

                        error_snippet = stderr.strip()[:200] if stderr else "unknown error"
                        print(f"  [{model_name}] {prompt_file} — FAILED on {label}: {error_snippet}")

                        if os.path.exists(temp_file):
                            os.remove(temp_file)

                        if attempt <= MAX_RETRIES:
                            messages.append({"role": "assistant", "content": raw_response})
                            messages.append({
                                "role": "user",
                                "content": RETRY_PROMPT.format(error=stderr.strip()[:1500]),
                            })
                        else:
                            with open(output_file, "w") as f:
                                f.write(code)
                            print(f"  [{model_name}] {prompt_file} — EXHAUSTED all {MAX_RETRIES} retries")
                            script_log["final_status"] = "fail"
                            script_log["total_attempts"] = attempt

                except Exception as e:
                    print(f"  [{model_name}] {prompt_file} — API ERROR: {e}")
                    script_log["final_status"] = "api_error"
                    script_log["error"] = str(e)

                retry_log[model_name][prompt_file] = script_log

        # Save retry log for this run
        os.makedirs(run_results_dir, exist_ok=True)
        log_path = os.path.join(run_results_dir, "retry_log.json")
        with open(log_path, "w") as f:
            json.dump(retry_log, f, indent=2)
        print(f"  Run {run} retry log saved to {log_path}")

    print(f"\nAll {total} run(s) complete.")


if __name__ == "__main__":
    generate_code()
