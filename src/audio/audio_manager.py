"""Audio manager for music and sound effects."""

import pygame
from typing import Dict, Optional
from ..core.config_manager import ConfigManager
from ..core.event_bus import EventBus, GameEvent, EventData


class AudioManager:
    """Manages all game audio - music and sound effects."""

    def __init__(self, config: ConfigManager, event_bus: EventBus):
        """
        Initialize the audio manager.

        Args:
            config: Configuration manager
            event_bus: Event bus for audio events
        """
        self.config = config
        self.event_bus = event_bus

        # Audio settings
        self.master_volume = config.get("audio_settings.master_volume", 0.8)
        self.music_volume = config.get("audio_settings.music_volume", 0.6)
        self.sfx_volume = config.get("audio_settings.sfx_volume", 0.8)
        self.music_enabled = config.get("audio_settings.music_enabled", True)
        self.sfx_enabled = config.get("audio_settings.sfx_enabled", True)

        # Sound cache
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.current_music: Optional[str] = None

        # Initialize pygame mixer
        self._init_mixer()

        # Subscribe to audio events
        self._subscribe_events()

    def _init_mixer(self) -> None:
        """Initialize pygame mixer."""
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except pygame.error as e:
            print(f"Warning: Could not initialize audio mixer: {e}")

    def _subscribe_events(self) -> None:
        """Subscribe to audio-related events."""
        self.event_bus.subscribe(GameEvent.PLAY_SOUND, self._on_play_sound)
        self.event_bus.subscribe(GameEvent.PLAY_MUSIC, self._on_play_music)
        self.event_bus.subscribe(GameEvent.STOP_MUSIC, self._on_stop_music)
        self.event_bus.subscribe(GameEvent.SETTINGS_CHANGED, self._on_settings_changed)
        self.event_bus.subscribe(GameEvent.SNACK_COLLECTED, self._on_snack_collected)
        self.event_bus.subscribe(GameEvent.POWERUP_ACTIVATED, self._on_powerup)
        self.event_bus.subscribe(GameEvent.ROUND_START, self._on_round_start)
        self.event_bus.subscribe(GameEvent.GAME_OVER, self._on_game_over)

    def _on_play_sound(self, event: EventData) -> None:
        """Handle play sound event."""
        sound_name = event.payload.get("sound")
        if sound_name:
            self.play_sound(sound_name)

    def _on_play_music(self, event: EventData) -> None:
        """Handle play music event."""
        music_name = event.payload.get("music")
        loop = event.payload.get("loop", True)
        if music_name:
            self.play_music(music_name, loop)

    def _on_stop_music(self, event: EventData) -> None:
        """Handle stop music event."""
        self.stop_music()

    def _on_settings_changed(self, event: EventData) -> None:
        """Handle settings changed event."""
        self.reload_settings()

    def _on_snack_collected(self, event: EventData) -> None:
        """Play sound when snack is collected."""
        snack_id = event.payload.get("snack_id", "")
        if snack_id == "broccoli":
            self.play_sound("yuck")
        elif snack_id in ("bone", "steak"):
            self.play_sound("powerup")
        elif snack_id == "spicy_pepper":
            self.play_sound("spicy")
        else:
            self.play_sound("chomp")

    def _on_powerup(self, event: EventData) -> None:
        """Play sound when powerup activates."""
        self.play_sound("powerup")

    def _on_round_start(self, event: EventData) -> None:
        """Play sound and music when round starts."""
        self.play_sound("go")
        self.play_music("gameplay")

    def _on_game_over(self, event: EventData) -> None:
        """Play game over music."""
        self.play_music("gameover")

    def reload_settings(self) -> None:
        """Reload audio settings from config."""
        self.master_volume = self.config.get("audio_settings.master_volume", 0.8)
        self.music_volume = self.config.get("audio_settings.music_volume", 0.6)
        self.sfx_volume = self.config.get("audio_settings.sfx_volume", 0.8)
        self.music_enabled = self.config.get("audio_settings.music_enabled", True)
        self.sfx_enabled = self.config.get("audio_settings.sfx_enabled", True)

        # Update music volume if playing
        if pygame.mixer.music.get_busy():
            effective_volume = self.master_volume * self.music_volume
            pygame.mixer.music.set_volume(effective_volume if self.music_enabled else 0)

    def load_sound(self, name: str, path: str) -> bool:
        """
        Load a sound effect.

        Args:
            name: Name to reference the sound
            path: File path to the sound

        Returns:
            True if loaded successfully
        """
        try:
            sound = pygame.mixer.Sound(path)
            self.sounds[name] = sound
            return True
        except pygame.error as e:
            print(f"Warning: Could not load sound {path}: {e}")
            return False

    def play_sound(self, name: str) -> None:
        """
        Play a sound effect.

        Args:
            name: Name of the sound to play
        """
        if not self.sfx_enabled:
            return

        if name in self.sounds:
            sound = self.sounds[name]
            effective_volume = self.master_volume * self.sfx_volume
            sound.set_volume(effective_volume)
            sound.play()
        # Silently ignore missing sounds (no audio files yet)

    def play_music(self, name: str, loop: bool = True) -> None:
        """
        Play background music.

        Args:
            name: Name/path of the music to play
            loop: Whether to loop the music
        """
        if not self.music_enabled:
            return

        # For now, just track what should be playing
        # Actual music files would need to be loaded
        self.current_music = name
        # pygame.mixer.music.load(path)
        # pygame.mixer.music.set_volume(self.master_volume * self.music_volume)
        # pygame.mixer.music.play(-1 if loop else 0)

    def stop_music(self, fadeout_ms: int = 500) -> None:
        """
        Stop the current music.

        Args:
            fadeout_ms: Fadeout duration in milliseconds
        """
        if pygame.mixer.get_init():
            pygame.mixer.music.fadeout(fadeout_ms)
        self.current_music = None

    def pause_music(self) -> None:
        """Pause the current music."""
        if pygame.mixer.get_init():
            pygame.mixer.music.pause()

    def resume_music(self) -> None:
        """Resume paused music."""
        if pygame.mixer.get_init() and self.music_enabled:
            pygame.mixer.music.unpause()

    def set_music_volume(self, volume: float) -> None:
        """Set music volume (0.0 to 1.0)."""
        self.music_volume = max(0.0, min(1.0, volume))
        if pygame.mixer.get_init():
            effective_volume = self.master_volume * self.music_volume
            pygame.mixer.music.set_volume(effective_volume)

    def set_sfx_volume(self, volume: float) -> None:
        """Set sound effects volume (0.0 to 1.0)."""
        self.sfx_volume = max(0.0, min(1.0, volume))

    def set_master_volume(self, volume: float) -> None:
        """Set master volume (0.0 to 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        # Update music volume
        if pygame.mixer.get_init():
            effective_volume = self.master_volume * self.music_volume
            pygame.mixer.music.set_volume(effective_volume)

    def toggle_music(self) -> bool:
        """Toggle music on/off. Returns new state."""
        self.music_enabled = not self.music_enabled
        if not self.music_enabled:
            self.stop_music(0)
        return self.music_enabled

    def toggle_sfx(self) -> bool:
        """Toggle sound effects on/off. Returns new state."""
        self.sfx_enabled = not self.sfx_enabled
        return self.sfx_enabled

    def cleanup(self) -> None:
        """Clean up audio resources."""
        self.stop_music(0)
        self.sounds.clear()
        if pygame.mixer.get_init():
            pygame.mixer.quit()
