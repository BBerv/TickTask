#!/bin/bash
cd ffllaapp
export PORT=5000
unset PIP_USER

if [ ! -d "venv" ]; then
    echo "Creating virtual environment with system site packages..."
    python3 -m venv venv --system-site-packages
fi

source venv/bin/activate

if [ -f "requirements.txt" ]; then
    echo "Checking dependencies..."
    pip install -r requirements.txt || echo "Pip install failed, but continuing as packages might be pre-installed via system."
fi

echo "Starting application..."
python main.py