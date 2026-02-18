"""Environment variable loader for secrets and configuration."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


_missing_env_warned = False


def _resolve_env_path(env_path: Optional[Path] = None) -> Path:
    """Resolve the .env file path."""
    if env_path is None:
        return Path(__file__).parent.parent.parent / ".env"
    return env_path


def _parse_env_file(env_path: Path) -> Dict[str, str]:
    """Parse .env file into key/value pairs."""
    parsed: Dict[str, str] = {}

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
                parsed[key] = value

    return parsed


def load_env(env_path: Optional[Path] = None) -> bool:
    """Load environment variables from a .env file.

    Args:
        env_path: Optional path to .env file. If not provided, looks for
                  .env in the project root (parent of src directory).

    Returns:
        True if .env was found and loaded, False otherwise.
    """
    global _missing_env_warned

    env_path = _resolve_env_path(env_path)

    if not env_path.exists():
        if not _missing_env_warned:
            print(f"Warning: .env file not found at {env_path}. Create it from .env.example if needed.")
            _missing_env_warned = True
        return False

    parsed = _parse_env_file(env_path)
    for key, value in parsed.items():
        os.environ[key] = value

    return True


def validate_required_env(required_keys: Sequence[str], env_path: Optional[Path] = None) -> Tuple[bool, List[str], bool]:
    """Validate that .env exists and contains non-empty required keys.

    Args:
        required_keys: Required .env variable names.
        env_path: Optional explicit .env path.

    Returns:
        Tuple of (is_valid, missing_keys, env_exists).
    """
    resolved_env_path = _resolve_env_path(env_path)

    if not resolved_env_path.exists():
        load_env(resolved_env_path)
        return False, list(required_keys), False

    parsed = _parse_env_file(resolved_env_path)
    for key, value in parsed.items():
        os.environ[key] = value

    missing_keys = [key for key in required_keys if not parsed.get(key, "").strip()]
    return len(missing_keys) == 0, missing_keys, True


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


def get_openrouter_key() -> Optional[str]:
    """Get the OpenRouter API key from environment.

    Returns:
        The API key string, or None if not set.
    """
    return os.environ.get('OPENROUTER_API_KEY')

def get_rembg_key() -> Optional[str]:
    """Get the rembg API key from environment.

    Returns:
        The API key string, or None if not set.
    """
    return os.environ.get('REMBG_API_KEY')
