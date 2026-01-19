"""Environment variable loader for secrets and configuration."""

import os
from pathlib import Path
from typing import Optional


def load_env(env_path: Optional[Path] = None) -> None:
    """Load environment variables from a .env file.

    Args:
        env_path: Optional path to .env file. If not provided, looks for
                  .env in the project root (parent of src directory).
    """
    if env_path is None:
        # Default to project root
        env_path = Path(__file__).parent.parent.parent / ".env"

    if not env_path.exists():
        return

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Parse key=value
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                os.environ[key] = value


def get_twitch_token() -> Optional[str]:
    """Get the Twitch access token from environment.

    Returns:
        The token string, or None if not set.
    """
    return os.environ.get('TWITCH_ACCESS_TOKEN')


def get_twitch_client_id() -> Optional[str]:
    """Get the Twitch client ID from environment.

    Returns:
        The client ID string, or None if not set.
    """
    return os.environ.get('TWITCH_CLIENT_ID')
