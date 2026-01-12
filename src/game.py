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


# Display dimensions - 1:1 aspect ratio, sized to fill monitor height
DISPLAY_WIDTH = 1000
DISPLAY_HEIGHT = 1000


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

        # Set up display - direct rendering at full resolution
        self.screen_width = DISPLAY_WIDTH
        self.screen_height = DISPLAY_HEIGHT

        self.fps = self.config.get("game_settings.window.fps", 60)
        title = self.config.get("game_settings.window.title", "Jazzy's Snack Attack")

        # Create the display surface
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption(title)

        # Initialize audio
        self.audio_manager = AudioManager(self.config, self.event_bus)

        # Initialize state machine
        self.state_machine = StateMachine()

        # Create screens
        self._create_screens()

        # Game state
        self.running = True
        self.clock = pygame.time.Clock()

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
            else:
                # Pass event to current screen
                current_screen = self.state_machine.get_current_screen()
                if current_screen:
                    current_screen.handle_event(event)

    def _render(self) -> None:
        """Render current screen directly to display."""
        current_screen = self.state_machine.get_current_screen()
        if current_screen:
            # Clear screen
            self.screen.fill((0, 0, 0))

            # Render screen directly to display
            current_screen.render(self.screen)

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
