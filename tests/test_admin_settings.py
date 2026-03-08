"""Unit tests for admin settings config persistence."""

import json
import os
import shutil
import tempfile
import unittest


class TestAdminSettingsPersistence(unittest.TestCase):
    """Verify that update_admin_setting() persists values correctly."""

    def setUp(self):
        """Copy the real config dir to a temp location so we can mutate freely."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        real_config = os.path.join(base_dir, "config")
        self.tmp_dir    = tempfile.mkdtemp()
        self.tmp_config = os.path.join(self.tmp_dir, "config")
        shutil.copytree(real_config, self.tmp_config)

        # Reset singleton so each test gets a fresh instance
        from src.core.config_manager import ConfigManager
        ConfigManager._instance = None
        self.config = ConfigManager()
        self.config.initialize(self.tmp_config)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        from src.core.config_manager import ConfigManager
        ConfigManager._instance = None

    def test_update_game_setting_in_memory(self):
        """In-memory value is updated immediately."""
        self.config.update_admin_setting("game_settings", "round_duration_seconds", 60)
        value = self.config.get("admin_settings.game_settings.round_duration_seconds")
        self.assertEqual(value, 60)

    def test_update_game_setting_persisted_to_disk(self):
        """Updated value is written to disk and survives a reload."""
        self.config.update_admin_setting("game_settings", "round_duration_seconds", 30)
        self.config.reload_config("admin_settings")
        value = self.config.get("admin_settings.game_settings.round_duration_seconds")
        self.assertEqual(value, 30)

    def test_get_admin_settings_returns_dict(self):
        """get_admin_settings() returns a dict with expected keys."""
        admin = self.config.get_admin_settings()
        self.assertIn("game_settings", admin)
        self.assertNotIn("sponsors", admin)

    def test_admin_settings_file_exists(self):
        """admin_settings.json is present in the config directory."""
        path = os.path.join(self.tmp_config, "admin_settings.json")
        self.assertTrue(os.path.exists(path), f"Missing {path}")

    def test_admin_settings_json_valid(self):
        """admin_settings.json is valid JSON with expected top-level keys."""
        path = os.path.join(self.tmp_config, "admin_settings.json")
        with open(path) as f:
            data = json.load(f)
        self.assertIn("game_settings", data)
        self.assertNotIn("sponsors", data)
        game_settings = data["game_settings"]
        self.assertIn("round_duration_seconds", game_settings)
        self.assertIn("treat_attack_round_duration_seconds", game_settings)
        self.assertIn("powerup_duration_seconds", game_settings)
        self.assertIn("powerup_speed_boost_multiplier", game_settings)
        self.assertIn("custom_power_treat_image", game_settings)
        self.assertIn("custom_power_treat_name", game_settings)

    def test_all_four_params_present(self):
        """All four tunable game params exist in config."""
        gs = self.config.get("admin_settings.game_settings", {})
        for key in ("round_duration_seconds",
                    "treat_attack_round_duration_seconds",
                    "powerup_duration_seconds",
                    "powerup_speed_boost_multiplier"):
            self.assertIn(key, gs, f"Missing key: {key}")


if __name__ == "__main__":
    unittest.main()
