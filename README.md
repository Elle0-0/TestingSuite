# Testing Suite for LLM Code Generation

## Project Overview
This project aims to evaluate the performance of various large language models (LLMs) in generating code for structured programming tasks. The evaluation focuses on:

1. **Functional Correctness**: Does the code pass the test harness?
2. **Robustness**: Can the code handle edge cases and bad inputs?
3. **Performance & Scalability**: Runtime and memory usage.
4. **Structural Complexity**: Measured using SonarQube metrics.

## Directory Structure
```
TestingSuite/
├── prompts/                # Contains task prompts
├── outputs/                # Stores generated code outputs
│   ├── gpt/               # Outputs from GPT models
│   ├── gemini/            # Outputs from Gemini models
│   ├── claude/            # Outputs from Claude models
│   ├── deepseek/          # Outputs from DeepSeek models
├── scripts/                # Contains automation scripts
│   ├── generate_code.py   # Script to generate code using APIs
│   ├── test_harness.py    # Script to test generated code
│   ├── analyze_results.py # Script to analyze results
└── README.md               # Project documentation
```

## Workflow
1. **Generate Code**:
   - Use `generate_code.py` to submit prompts to LLMs and save outputs.

2. **Test Code**:
   - Use `test_harness.py` to evaluate correctness, robustness, and performance.

3. **Analyze Results**:
   - Use `analyze_results.py` to measure structural complexity and compare models.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the workflow:
   ```bash
   python scripts/generate_code.py
   python scripts/test_harness.py
   python scripts/analyze_results.py
   ```