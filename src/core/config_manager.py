"""Configuration manager for loading and accessing JSON config files."""

import json
import os
from typing import Any, Dict, Optional


class ConfigManager:
    """Singleton config manager that loads and provides access to all game configurations."""

    _instance: Optional['ConfigManager'] = None

    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._configs: Dict[str, Dict] = {}
            cls._instance._config_dir: str = ""
        return cls._instance

    def initialize(self, config_dir: str) -> None:
        """Initialize the config manager with the config directory path."""
        self._config_dir = config_dir
        self._load_all_configs()

    def _load_all_configs(self) -> None:
        """Load all JSON config files from the config directory."""
        config_files = [
            "game_settings",
            "characters",
            "snacks",
            "levels",
            "ai_difficulty",
            "audio_settings",
            "controls",
            "treat_attack_settings",
            "twitch_config"
        ]

        for config_name in config_files:
            self._load_config(config_name)

    def _load_config(self, config_name: str) -> None:
        """Load a single config file."""
        file_path = os.path.join(self._config_dir, f"{config_name}.json")
        try:
            with open(file_path, 'r') as f:
                self._configs[config_name] = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Config file not found: {file_path}")
            self._configs[config_name] = {}
        except json.JSONDecodeError as e:
            print(f"Error parsing config file {file_path}: {e}")
            self._configs[config_name] = {}

    def get_config(self, config_name: str) -> Dict:
        """Get an entire config by name."""
        return self._configs.get(config_name, {})

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a config value using dot notation.
        Example: config.get("game_settings.window.width")
        """
        parts = path.split(".")
        if not parts:
            return default

        config_name = parts[0]
        config = self._configs.get(config_name, {})

        for part in parts[1:]:
            if isinstance(config, dict):
                config = config.get(part)
                if config is None:
                    return default
            else:
                return default

        return config if config is not None else default

    def reload_config(self, config_name: str) -> None:
        """Reload a specific config file (useful for hot-reloading during development)."""
        self._load_config(config_name)

    def get_character(self, character_id: str) -> Optional[Dict]:
        """Get a character configuration by ID."""
        characters = self.get("characters.characters", [])
        for char in characters:
            if char.get("id") == character_id:
                return char
        return None

    def get_all_characters(self) -> list:
        """Get all character configurations."""
        return self.get("characters.characters", [])

    def get_snack(self, snack_id: str) -> Optional[Dict]:
        """Get a snack configuration by ID."""
        snacks = self.get("snacks.snacks", [])
        for snack in snacks:
            if snack.get("id") == snack_id:
                return snack
        return None

    def get_all_snacks(self) -> list:
        """Get all snack configurations."""
        return self.get("snacks.snacks", [])

    def get_level(self, level_number: int) -> Optional[Dict]:
        """Get a level configuration by number."""
        levels = self.get("levels.levels", [])
        for level in levels:
            if level.get("level_number") == level_number:
                return level
        return None

    def get_difficulty(self, difficulty_name: str) -> Dict:
        """Get AI difficulty settings."""
        return self.get(f"ai_difficulty.difficulties.{difficulty_name}", {})

    def save_audio_settings(self) -> None:
        """Save audio settings back to file."""
        file_path = os.path.join(self._config_dir, "audio_settings.json")
        with open(file_path, 'w') as f:
            json.dump(self._configs.get("audio_settings", {}), f, indent=2)

    def update_audio_setting(self, key: str, value: Any) -> None:
        """Update an audio setting and save."""
        if "audio_settings" in self._configs:
            self._configs["audio_settings"][key] = value
            self.save_audio_settings()

    def get_twitch_config(self) -> Dict:
        """Get Twitch integration configuration."""
        return self.get_config("twitch_config")
