#!/usr/bin/env python3
"""
Jazzy's Treat Storm - Main Game Entry Point
A retro 2D arcade game where dogs collect snacks!

Run this file to start the game:
    python main.py
"""

from pathlib import Path
import sys
from src.core.env_loader import validate_required_env

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    env_path = project_root / ".env"

    is_valid, missing_keys, env_exists = validate_required_env(
        ["REMBG_API_KEY", "OPENROUTER_API_KEY"],
        env_path=env_path
    )

    if not is_valid:
        print("ERROR: Cannot start game due to missing required environment configuration.")
        if not env_exists:
            print(f"- Missing file: {env_path}")
        if missing_keys:
            print(f"- Missing keys in .env: {', '.join(missing_keys)}")
        print("- Create/update .env (use .env.example as a template), then run again.")
        sys.exit(1)

    from src.game import main
    main()
