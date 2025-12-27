#!/usr/bin/env python3
"""Convenience script to run Whisper Dictation.

This script automatically uses the virtual environment's Python
interpreter to run the application.

Usage:
    python run.py
    # or
    ./run.py  (if executable)
"""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run the Whisper Dictation application.

    Returns:
        Exit code from the application.
    """
    project_root = Path(__file__).parent
    venv_python = project_root / "venv" / "bin" / "python"

    if not venv_python.exists():
        print("Error: Virtual environment not found at:", venv_python)
        print()
        print("Please set up the virtual environment first:")
        print()
        print("  python -m venv venv")
        print("  source venv/bin/activate")
        print("  pip install -r requirements.txt")
        print()
        return 1

    result = subprocess.run([str(venv_python), "-m", "src.main"])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
