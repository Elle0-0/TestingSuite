#!/bin/bash
# Setup script for the LLM Testing Suite
# Creates a virtual environment and installs all dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Creating virtual environment..."
python3 -m venv "$SCRIPT_DIR/venv"

echo "Activating virtual environment..."
source "$SCRIPT_DIR/venv/bin/activate"

echo "Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "Setup complete! To activate the virtual environment, run:"
echo "  source \"$SCRIPT_DIR/venv/bin/activate\""
echo ""
echo "Then run the pipeline from the scripts/ directory:"
echo "  cd scripts"
echo "  python generate_code.py"
echo "  python test_harness.py"
echo "  python analyze_results.py"
