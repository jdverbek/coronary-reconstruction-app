#!/usr/bin/env python3
"""
WSGI entry point for Gunicorn deployment
"""

import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.main import app

if __name__ == "__main__":
    app.run()

