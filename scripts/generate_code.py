import os
import openai
import anthropic
from google.cloud import aiplatform

# Configure API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Ensure API keys are set
if not OPENAI_API_KEY or not ANTHROPIC_API_KEY or not GOOGLE_API_KEY:
    raise EnvironmentError("Please set the API keys for OpenAI, Anthropic, and Google Cloud.")

# Define models and their respective APIs
MODELS = {
    "gpt": {
        "api": "openai",
        "function": lambda prompt: openai.Completion.create(
            engine="gpt-4", prompt=prompt, max_tokens=1000
        ).choices[0].text,
    },
    "gemini": {
        "api": "google",
        "function": lambda prompt: aiplatform.generation.TextGenerationClient().generate(
            model="gemini", prompt=prompt
        ).text,
    },
    "claude": {
        "api": "anthropic",
        "function": lambda prompt: anthropic.Client(ANTHROPIC_API_KEY).complete(
            prompt=prompt, model="claude-v1"
        ).completion,
    },
    "deepseek": {
        "api": "custom",
        "function": lambda prompt: "DeepSeek API integration pending",
    },
}

# Directory paths
PROMPTS_DIR = "../prompts"
OUTPUTS_DIR = "../outputs"

# Generate code for each model and prompt
def generate_code():
    for model_name, model_info in MODELS.items():
        model_output_dir = os.path.join(OUTPUTS_DIR, model_name)
        os.makedirs(model_output_dir, exist_ok=True)

        for prompt_file in os.listdir(PROMPTS_DIR):
            prompt_path = os.path.join(PROMPTS_DIR, prompt_file)
            with open(prompt_path, "r") as f:
                prompt = f.read()

            try:
                print(f"Generating code for {model_name} using prompt {prompt_file}...")
                solution = model_info["function"](prompt)

                output_file = os.path.join(
                    model_output_dir, f"{os.path.splitext(prompt_file)[0]}_solution.py"
                )
                with open(output_file, "w") as out_f:
                    out_f.write(solution)

                print(f"Saved solution to {output_file}")
            except Exception as e:
                print(f"Error generating code for {model_name} with prompt {prompt_file}: {e}")

if __name__ == "__main__":
    generate_code()