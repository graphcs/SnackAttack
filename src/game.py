"""Main game class orchestrating the game loop with detailed retro pixel art."""

import pygame
import os
from typing import Optional

from .core.config_manager import ConfigManager
from .core.event_bus import EventBus, GameEvent
from .core.state_machine import StateMachine, GameState
from .screens.main_menu import MainMenuScreen
from .screens.character_select import CharacterSelectScreen
from .screens.gameplay import GameplayScreen
from .screens.treat_attack_gameplay import TreatAttackGameplay
from .screens.settings import SettingsScreen
from .screens.game_over import GameOverScreen
from .audio.audio_manager import AudioManager


# Default display dimensions (can be overridden via config)
DEFAULT_DISPLAY_WIDTH = 1200
DEFAULT_DISPLAY_HEIGHT = 1000


class Game:
    """Main game class that runs the game loop with detailed retro pixel art."""

    def __init__(self):
        """Initialize the game."""
        # Initialize Pygame
        pygame.init()
        pygame.font.init()

        # Get the directory where this file is located
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(self.base_dir, "config")

        # Initialize core systems
        self.config = ConfigManager()
        self.config.initialize(config_dir)

        self.event_bus = EventBus()

        # Get the target game resolution (internal rendering size)
        self.game_width = self.config.get("game_settings.window.width", DEFAULT_DISPLAY_WIDTH)
        self.game_height = self.config.get("game_settings.window.height", DEFAULT_DISPLAY_HEIGHT)

        # Get screen info to determine appropriate window size
        display_info = pygame.display.Info()
        monitor_width = display_info.current_w
        monitor_height = display_info.current_h

        # Calculate scale factor to fit window on screen with margin (90% of screen)
        margin = 0.90
        scale_x = (monitor_width * margin) / self.game_width
        scale_y = (monitor_height * margin) / self.game_height
        self.scale_factor = min(scale_x, scale_y, 1.0)  # Don't scale up, only down if needed

        # Calculate actual window size
        self.screen_width = int(self.game_width * self.scale_factor)
        self.screen_height = int(self.game_height * self.scale_factor)

        self.fps = self.config.get("game_settings.window.fps", 60)
        title = self.config.get("game_settings.window.title", "Jazzy's Snack Attack")

        # Create the display surface (actual window) - resizable
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
        pygame.display.set_caption(title)

        # Create internal game surface at full resolution
        self.game_surface = pygame.Surface((self.game_width, self.game_height))

        # Update config with internal game dimensions so screens use correct size
        # (screens read from config for their dimensions)
        self.config._configs["game_settings"]["window"]["width"] = self.game_width
        self.config._configs["game_settings"]["window"]["height"] = self.game_height

        # Initialize audio
        self.audio_manager = AudioManager(self.config, self.event_bus)
        self._load_sounds()

        # Initialize state machine
        self.state_machine = StateMachine()

        # Create screens
        self._create_screens()

        # Game state
        self.running = True
        self.clock = pygame.time.Clock()

    def _load_sounds(self) -> None:
        """Load all game sound effects."""
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sound_dir = os.path.join(base_dir, "Sound effect")

        # Load sound effects
        self.audio_manager.load_sound("dog_eat", os.path.join(sound_dir, "Dog eat.mp3"))
        self.audio_manager.load_sound("point_earned", os.path.join(sound_dir, "Point earned.mp3"))
        self.audio_manager.load_sound("broccoli", os.path.join(sound_dir, "Broccoli.mp3"))
        self.audio_manager.load_sound("red_bull", os.path.join(sound_dir, "Red bull.mp3"))
        self.audio_manager.load_sound("chilli", os.path.join(sound_dir, "chilli.mp3"))
        self.audio_manager.load_sound("countdown_2_3", os.path.join(sound_dir, "2&3.mp3"))
        self.audio_manager.load_sound("countdown_1", os.path.join(sound_dir, "1.mp3"))
        self.audio_manager.load_sound("select", os.path.join(sound_dir, "select.mp3"))
        self.audio_manager.load_sound("start", os.path.join(sound_dir, "start.mp3"))

    def _create_screens(self) -> None:
        """Create and register all game screens."""
        # Create screen instances
        main_menu = MainMenuScreen(self.state_machine, self.config, self.event_bus)
        character_select = CharacterSelectScreen(self.state_machine, self.config, self.event_bus)
        gameplay = GameplayScreen(self.state_machine, self.config, self.event_bus)
        treat_attack = TreatAttackGameplay(self.state_machine, self.config, self.event_bus)
        settings = SettingsScreen(self.state_machine, self.config, self.event_bus)
        game_over = GameOverScreen(self.state_machine, self.config, self.event_bus)

        # Register screens with state machine
        self.state_machine.register_state(GameState.MAIN_MENU, main_menu)
        self.state_machine.register_state(GameState.CHARACTER_SELECT, character_select)
        self.state_machine.register_state(GameState.GAMEPLAY, gameplay)
        self.state_machine.register_state(GameState.TREAT_ATTACK, treat_attack)
        self.state_machine.register_state(GameState.SETTINGS, settings)
        self.state_machine.register_state(GameState.GAME_OVER, game_over)

        # Start at main menu
        self.state_machine.change_state(GameState.MAIN_MENU)

    def run(self) -> None:
        """Run the main game loop."""
        while self.running:
            # Calculate delta time
            dt = self.clock.tick(self.fps) / 1000.0  # Convert to seconds

            # Handle events
            self._handle_events()

            # Process queued events
            self.event_bus.process_queue()

            # Update current screen
            current_screen = self.state_machine.get_current_screen()
            if current_screen:
                current_screen.update(dt)

            # Render to world surface, then scale to display
            self._render()

            # Update display
            pygame.display.flip()

        # Cleanup
        self._cleanup()

    def _handle_events(self) -> None:
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                # Handle window resize
                self.screen_width = event.w
                self.screen_height = event.h
                self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
                # Update scale factor based on new window size
                scale_x = self.screen_width / self.game_width
                scale_y = self.screen_height / self.game_height
                self.scale_factor = min(scale_x, scale_y)
            else:
                # Scale mouse positions back to game coordinates
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                    # Calculate offset for centered game surface
                    scaled_width = int(self.game_width * self.scale_factor)
                    scaled_height = int(self.game_height * self.scale_factor)
                    offset_x = (self.screen_width - scaled_width) // 2
                    offset_y = (self.screen_height - scaled_height) // 2

                    # Adjust for offset and scale
                    scaled_pos = (
                        int((event.pos[0] - offset_x) / self.scale_factor),
                        int((event.pos[1] - offset_y) / self.scale_factor)
                    )
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
                            'pos': scaled_pos,
                            'button': event.button
                        })
                    elif event.type == pygame.MOUSEBUTTONUP:
                        event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
                            'pos': scaled_pos,
                            'button': event.button
                        })
                    elif event.type == pygame.MOUSEMOTION:
                        event = pygame.event.Event(pygame.MOUSEMOTION, {
                            'pos': scaled_pos,
                            'rel': (int(event.rel[0] / self.scale_factor), int(event.rel[1] / self.scale_factor)),
                            'buttons': event.buttons
                        })

                # Pass event to current screen
                current_screen = self.state_machine.get_current_screen()
                if current_screen:
                    current_screen.handle_event(event)

    def _render(self) -> None:
        """Render current screen to game surface, then scale to display."""
        current_screen = self.state_machine.get_current_screen()
        if current_screen:
            # Clear display and game surface
            self.screen.fill((0, 0, 0))
            self.game_surface.fill((0, 0, 0))

            # Render screen to internal game surface at full resolution
            current_screen.render(self.game_surface)

            # Scale game surface to fit display window (maintain aspect ratio)
            scaled_width = int(self.game_width * self.scale_factor)
            scaled_height = int(self.game_height * self.scale_factor)

            # Center the scaled surface in the window
            offset_x = (self.screen_width - scaled_width) // 2
            offset_y = (self.screen_height - scaled_height) // 2

            if self.scale_factor != 1.0:
                scaled_surface = pygame.transform.smoothscale(
                    self.game_surface, (scaled_width, scaled_height)
                )
                self.screen.blit(scaled_surface, (offset_x, offset_y))
            else:
                self.screen.blit(self.game_surface, (offset_x, offset_y))

    def _cleanup(self) -> None:
        """Clean up resources."""
        self.audio_manager.cleanup()
        pygame.quit()


def main():
    """Entry point for the game."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
