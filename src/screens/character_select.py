"""Character selection screen."""

import pygame
from typing import Dict, Any, List, Optional
from .base_screen import BaseScreen
from ..core.state_machine import GameState


class CharacterCard:
    """A character selection card."""

    def __init__(self, character_config: Dict[str, Any], x: int, y: int,
                 width: int = 180, height: int = 200):
        """Card sized for 960x720 display."""
        self.config = character_config
        self.character_id = character_config.get("id", "unknown")
        self.name = character_config.get("name", "Unknown")
        self.breed = character_config.get("breed", "")
        self.color = tuple(character_config.get("color", [200, 200, 200]))
        self.speed = character_config.get("base_speed", 1.0)

        self.rect = pygame.Rect(x, y, width, height)
        self.selected_p1 = False
        self.selected_p2 = False
        self.hovered = False


class CharacterSelectScreen(BaseScreen):
    """Character selection screen for 1P and 2P modes."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        self.character_cards: List[CharacterCard] = []
        self.game_mode = "1p"
        self.vs_ai = True

        # Selection state
        self.p1_selection: Optional[int] = 0
        self.p2_selection: Optional[int] = 1
        self.active_player = 1  # Which player is currently selecting
        self.p1_confirmed = False
        self.p2_confirmed = False

        # AI difficulty selection (for 1P mode)
        self.difficulties = ["easy", "medium", "hard"]
        self.selected_difficulty = 1  # Medium by default
        self.selecting_difficulty = False

        # Colors - dark blue theme like reference
        self.bg_color = (20, 30, 60)
        self.p1_color = (100, 180, 255)
        self.p2_color = (255, 120, 120)
        self.text_color = (255, 255, 255)
        self.highlight_color = (255, 220, 80)

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize character select screen."""
        self.initialize_fonts()

        data = data or {}
        self.game_mode = data.get("mode", "1p")
        self.vs_ai = data.get("vs_ai", True)

        # Reset selection state
        self.p1_selection = 0
        self.p2_selection = 1 if not self.vs_ai else None
        self.active_player = 1
        self.p1_confirmed = False
        self.p2_confirmed = False
        self.selecting_difficulty = False
        self.selected_difficulty = 1

        # Create character cards
        self._create_character_cards()

        # Update initial selection visuals
        self._update_card_selections()

    def _create_character_cards(self) -> None:
        """Create character cards from config - 4 columns for 960x720."""
        characters = self.config.get_all_characters()

        # 4 column layout for 960x720 display
        cards_per_row = 4
        card_width = 180
        card_height = 200
        padding = 24

        total_width = cards_per_row * card_width + (cards_per_row - 1) * padding
        start_x = (self.screen_width - total_width) // 2
        start_y = 140

        self.character_cards = []
        for i, char_config in enumerate(characters):
            row = i // cards_per_row
            col = i % cards_per_row

            x = start_x + col * (card_width + padding)
            y = start_y + row * (card_height + padding)

            card = CharacterCard(char_config, x, y, card_width, card_height)
            self.character_cards.append(card)

    def _update_card_selections(self) -> None:
        """Update which cards are selected."""
        for i, card in enumerate(self.character_cards):
            card.selected_p1 = (i == self.p1_selection)
            card.selected_p2 = (i == self.p2_selection) if not self.vs_ai else False

    def on_exit(self) -> None:
        """Clean up when leaving screen."""
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if self.selecting_difficulty:
                self._handle_difficulty_input(event.key)
            else:
                self._handle_selection_input(event.key)

    def _handle_selection_input(self, key: int) -> None:
        """Handle character selection input."""
        cards_per_row = 4  # Match _create_character_cards
        num_cards = len(self.character_cards)

        # Get current selection based on active player
        if self.active_player == 1:
            current = self.p1_selection
        else:
            current = self.p2_selection

        new_selection = current

        if key == pygame.K_LEFT:
            new_selection = max(0, current - 1)
        elif key == pygame.K_RIGHT:
            new_selection = min(num_cards - 1, current + 1)
        elif key == pygame.K_UP:
            new_selection = max(0, current - cards_per_row)
        elif key == pygame.K_DOWN:
            new_selection = min(num_cards - 1, current + cards_per_row)
        elif key == pygame.K_RETURN:
            self._confirm_selection()
            return
        elif key == pygame.K_ESCAPE:
            self._go_back()
            return

        # For 2P mode with WASD for P1
        if not self.vs_ai and self.active_player == 1:
            if key == pygame.K_a:
                new_selection = max(0, current - 1)
            elif key == pygame.K_d:
                new_selection = min(num_cards - 1, current + 1)
            elif key == pygame.K_w:
                new_selection = max(0, current - cards_per_row)
            elif key == pygame.K_s:
                new_selection = min(num_cards - 1, current + cards_per_row)
            elif key == pygame.K_SPACE:
                self._confirm_selection()
                return

        # Update selection
        if self.active_player == 1:
            self.p1_selection = new_selection
        else:
            self.p2_selection = new_selection

        self._update_card_selections()

    def _handle_difficulty_input(self, key: int) -> None:
        """Handle difficulty selection input."""
        if key == pygame.K_LEFT:
            self.selected_difficulty = max(0, self.selected_difficulty - 1)
        elif key == pygame.K_RIGHT:
            self.selected_difficulty = min(2, self.selected_difficulty + 1)
        elif key == pygame.K_RETURN:
            self._start_game()
        elif key == pygame.K_ESCAPE:
            self.selecting_difficulty = False
            self.p1_confirmed = False

    def _confirm_selection(self) -> None:
        """Confirm current player's selection."""
        if self.active_player == 1:
            self.p1_confirmed = True
            if self.vs_ai:
                # Go to difficulty selection
                self.selecting_difficulty = True
            else:
                # Switch to P2 selection
                self.active_player = 2
        else:
            self.p2_confirmed = True
            self._start_game()

    def _go_back(self) -> None:
        """Go back to previous state or screen."""
        if self.selecting_difficulty:
            self.selecting_difficulty = False
            self.p1_confirmed = False
        elif self.p1_confirmed and not self.vs_ai:
            self.p1_confirmed = False
            self.active_player = 1
        else:
            self.state_machine.change_state(GameState.MAIN_MENU)

    def _start_game(self) -> None:
        """Start the game with selected characters."""
        p1_char = self.character_cards[self.p1_selection].config

        if self.vs_ai:
            # AI gets a random character different from P1
            import random
            available = [c for i, c in enumerate(self.character_cards)
                         if i != self.p1_selection]
            p2_char = random.choice(available).config if available else p1_char
            difficulty = self.difficulties[self.selected_difficulty]
        else:
            p2_char = self.character_cards[self.p2_selection].config
            difficulty = None

        self.state_machine.change_state(GameState.GAMEPLAY, {
            "mode": self.game_mode,
            "vs_ai": self.vs_ai,
            "p1_character": p1_char,
            "p2_character": p2_char,
            "difficulty": difficulty
        })

    def update(self, dt: float) -> None:
        """Update screen state."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render the character select screen to 960x720 display."""
        surface.fill(self.bg_color)

        # Title at top
        self.draw_text(surface, "CHOOSE YOUR DOG!", self.title_font, self.highlight_color,
                       (self.screen_width // 2, 60))

        # Player indicator
        if not self.vs_ai:
            if self.active_player == 1:
                choose_text = "P1 SELECT"
                choose_color = self.p1_color
            else:
                choose_text = "P2 SELECT"
                choose_color = self.p2_color
            self.draw_text(surface, choose_text, self.menu_font, choose_color,
                           (self.screen_width // 2, 100))

        # Draw character cards
        for card in self.character_cards:
            self._render_card(surface, card)

        # Difficulty selection overlay
        if self.selecting_difficulty:
            self._render_difficulty_selection(surface)

        # Instructions at bottom
        if not self.selecting_difficulty:
            instructions = "Arrow Keys + Enter to Select"
            if not self.vs_ai:
                instructions = "WASD/Arrow Keys + Enter to Select"
            self.draw_text(surface, instructions, self.small_font, (120, 130, 150),
                           (self.screen_width // 2, self.screen_height - 30))

    def _render_card(self, surface: pygame.Surface, card: CharacterCard) -> None:
        """Render a character card (180x200) for 960x720 display."""
        from ..sprites.pixel_art import SpriteCache

        # Selection state determines border
        if card.selected_p1 and card.selected_p2:
            border_color = (200, 150, 255)  # Purple for both
            border_width = 4
        elif card.selected_p1:
            border_color = self.p1_color
            border_width = 4
        elif card.selected_p2:
            border_color = self.p2_color
            border_width = 4
        else:
            border_color = (60, 70, 100)
            border_width = 2

        # Card background
        bg_color = (30, 40, 70) if (card.selected_p1 or card.selected_p2) else (25, 35, 60)
        pygame.draw.rect(surface, bg_color, card.rect, border_radius=8)
        pygame.draw.rect(surface, border_color, card.rect, border_width, border_radius=8)

        # Get the pixel art portrait and scale to 128x128 for card
        cache = SpriteCache()
        portrait = cache.get_dog_portrait(card.character_id)
        # Scale portrait to fit card (128x128)
        scaled_portrait = pygame.transform.scale(portrait, (128, 128))

        # Center the portrait in the card
        portrait_x = card.rect.centerx - 64
        portrait_y = card.rect.y + 20

        # Draw the portrait
        surface.blit(scaled_portrait, (portrait_x, portrait_y))

        # Draw name below portrait
        name_y = card.rect.y + 160
        name_color = self.highlight_color if (card.selected_p1 or card.selected_p2) else self.text_color
        self.draw_text(surface, card.name.upper(), self.menu_font, name_color,
                       (card.rect.centerx, name_y))

        # Draw breed below name
        breed_y = card.rect.y + 185
        self.draw_text(surface, card.breed, self.small_font, (150, 150, 170),
                       (card.rect.centerx, breed_y))

        # Draw player indicator badges
        if card.selected_p1:
            badge_rect = pygame.Rect(card.rect.left + 8, card.rect.top + 8, 32, 24)
            pygame.draw.rect(surface, self.p1_color, badge_rect, border_radius=4)
            self.draw_text(surface, "P1", self.small_font, (255, 255, 255),
                           (badge_rect.centerx, badge_rect.centery))

        if card.selected_p2:
            badge_rect = pygame.Rect(card.rect.right - 40, card.rect.top + 8, 32, 24)
            pygame.draw.rect(surface, self.p2_color, badge_rect, border_radius=4)
            self.draw_text(surface, "P2", self.small_font, (255, 255, 255),
                           (badge_rect.centerx, badge_rect.centery))

    def _render_difficulty_selection(self, surface: pygame.Surface) -> None:
        """Render difficulty selection overlay for 960x720."""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(200)
        surface.blit(overlay, (0, 0))

        # Title
        self.draw_text(surface, "SELECT DIFFICULTY", self.title_font,
                       self.highlight_color, (self.screen_width // 2, 280))

        # Difficulty options - horizontal layout
        option_y = 380
        option_spacing = 200
        start_x = self.screen_width // 2 - option_spacing

        for i, diff in enumerate(self.difficulties):
            x = start_x + i * option_spacing
            color = self.highlight_color if i == self.selected_difficulty else (150, 150, 150)

            # Draw box around selected
            if i == self.selected_difficulty:
                box_rect = pygame.Rect(x - 80, option_y - 25, 160, 50)
                pygame.draw.rect(surface, (60, 70, 40), box_rect, border_radius=8)
                pygame.draw.rect(surface, self.highlight_color, box_rect, 3, border_radius=8)

            self.draw_text(surface, diff.upper(), self.menu_font,
                           color, (x, option_y))

        # Instructions
        self.draw_text(surface, "Left/Right Arrow Keys + Enter to Confirm",
                       self.small_font, (150, 150, 150),
                       (self.screen_width // 2, self.screen_height - 60))
