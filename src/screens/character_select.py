"""Character selection screen."""

import pygame
import os
from typing import Dict, Any, List, Optional
from .base_screen import BaseScreen
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent


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

        # Colors - dark blue theme like reference
        self.bg_color = (20, 30, 60)
        self.p1_color = (100, 180, 255)
        self.p2_color = (255, 120, 120)
        self.text_color = (255, 255, 255)
        self.highlight_color = (255, 220, 80)

        # Images
        self.background_image: Optional[pygame.Surface] = None
        self.title_image: Optional[pygame.Surface] = None
        self.profile_images: Dict[str, Optional[pygame.Surface]] = {}

        # Back button
        self.back_font: Optional[pygame.font.Font] = None
        self.back_button_rect: Optional[pygame.Rect] = None
        self.back_color = (77, 43, 31)  # #4D2B1F
        self.back_selected_color = (147, 76, 48)  # #934C30
        self.back_selected = False
        self.select_indicator: Optional[pygame.Surface] = None

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize character select screen."""
        self.initialize_fonts()
        self._load_custom_font()
        self._load_images()

        data = data or {}
        self.game_mode = data.get("mode", "1p")
        self.vs_ai = data.get("vs_ai", True)

        # Reset selection state
        self.p1_selection = 0
        self.p2_selection = None  # P2 not selected until P1 confirms
        self.active_player = 1
        self.p1_confirmed = False
        self.p2_confirmed = False

        # Create character cards
        self._create_character_cards()

        # Update initial selection visuals
        self._update_card_selections()

    def _create_character_cards(self) -> None:
        """Create character cards from config with 3x2 layout."""
        characters = self.config.get_all_characters()

        # Reorder characters: 1st row: jazzy, biggie, dash, 2nd row: snowy, prissy, rex
        char_order = ["jazzy", "biggie", "dash", "snowy", "prissy", "rex"]
        char_dict = {c.get("id"): c for c in characters}
        ordered_characters = [char_dict[cid] for cid in char_order if cid in char_dict]

        # 3 columns x 2 rows layout
        cards_per_row = 3
        card_width = int(self.screen_width * 0.25 * 1.1)
        card_height = int(self.screen_height * 0.28 * 1.1)
        padding_x = -25  # Cards closer together horizontally
        padding_y = -70  # Rows closer together vertically

        total_width = cards_per_row * card_width + (cards_per_row - 1) * padding_x
        start_x = (self.screen_width - total_width) // 2
        start_y = int(self.screen_height * 0.32)  # Moved down

        self.character_cards = []
        for i, char_config in enumerate(ordered_characters):
            row = i // cards_per_row
            col = i % cards_per_row

            x = start_x + col * (card_width + padding_x)
            y = start_y + row * (card_height + padding_y)

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

    def _load_custom_font(self) -> None:
        """Load custom Daydream font for back button and difficulty screen."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")
        font_path = os.path.join(ui_dir, "Daydream.ttf")

        if os.path.exists(font_path):
            self.back_font = pygame.font.Font(font_path, 32)
            # Override base fonts with Daydream for difficulty screen
            self.title_font = pygame.font.Font(font_path, 36)
            self.menu_font = pygame.font.Font(font_path, 28)
            self.small_font = pygame.font.Font(font_path, 18)

    def _load_images(self) -> None:
        """Load background and title images."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir = os.path.join(base_dir, "ui")

        # Load background image
        bg_path = os.path.join(ui_dir, "Choose your dog background.png")
        if os.path.exists(bg_path):
            self.background_image = pygame.image.load(bg_path).convert()
            self.background_image = pygame.transform.scale(
                self.background_image, (self.screen_width, self.screen_height)
            )

        # Load title image
        title_path = os.path.join(ui_dir, "Choose your dog ui.png")
        if os.path.exists(title_path):
            self.title_image = pygame.image.load(title_path).convert_alpha()
            # Scale title to fit nicely at top
            title_max_width = int(self.screen_width * 0.6)
            title_max_height = int(self.screen_height * 0.12)
            title_rect = self.title_image.get_rect()
            scale = min(title_max_width / title_rect.width, title_max_height / title_rect.height)
            scale *= 1.65  # Make title bigger
            new_width = int(title_rect.width * scale)
            new_height = int(title_rect.height * scale)
            self.title_image = pygame.transform.scale(self.title_image, (new_width, new_height))

        # Load profile images from Profile folder
        profile_dir = os.path.join(base_dir, "Profile")
        profile_files = {
            "jazzy": "Jazzy.png",
            "biggie": "Biggie.png",
            "prissy": "Prissy.png",
            "snowy": "Snowy.png",
            "rex": "Rex.png",
            "dash": "Dash.png"
        }
        for char_id, filename in profile_files.items():
            profile_path = os.path.join(profile_dir, filename)
            if os.path.exists(profile_path):
                self.profile_images[char_id] = pygame.image.load(profile_path).convert_alpha()

        # Load select indicator image (same size as main menu)
        select_path = os.path.join(ui_dir, "Select.png")
        if os.path.exists(select_path):
            self.select_indicator = pygame.image.load(select_path).convert_alpha()
            # Scale to match main menu button size
            select_scale = 0.576
            new_width = int(self.select_indicator.get_width() * select_scale)
            new_height = int(self.select_indicator.get_height() * select_scale)
            self.select_indicator = pygame.transform.scale(self.select_indicator, (new_width, new_height))

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            self._handle_selection_input(event.key)

        elif event.type == pygame.MOUSEMOTION:
            # Handle hover on back button
            if self.back_button_rect and self.back_button_rect.collidepoint(event.pos):
                self.back_selected = True
            else:
                self.back_selected = False

            # Handle hover on character cards
            for i, card in enumerate(self.character_cards):
                if card.rect.collidepoint(event.pos):
                    # Update selection based on active player
                    old_selection = self.p1_selection if self.active_player == 1 else self.p2_selection
                    if self.active_player == 1:
                        self.p1_selection = i
                    else:
                        self.p2_selection = i
                    if old_selection != i:
                        self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "select"})
                    self._update_card_selections()
                    break

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                if self.back_button_rect and self.back_button_rect.collidepoint(event.pos):
                    self.state_machine.change_state(GameState.MAIN_MENU)

                # Handle click on character cards
                for i, card in enumerate(self.character_cards):
                    if card.rect.collidepoint(event.pos):
                        # Update selection and confirm
                        if self.active_player == 1:
                            self.p1_selection = i
                        else:
                            self.p2_selection = i
                        self._update_card_selections()
                        self._confirm_selection()
                        break

    def _handle_selection_input(self, key: int) -> None:
        """Handle character selection input."""
        cards_per_row = 3  # Match _create_character_cards
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
            if self.p1_selection != new_selection:
                self.p1_selection = new_selection
                self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "select"})
        else:
            if self.p2_selection != new_selection:
                self.p2_selection = new_selection
                self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "select"})

        self._update_card_selections()

    def _confirm_selection(self) -> None:
        """Confirm current player's selection."""
        if self.active_player == 1:
            self.p1_confirmed = True
            if self.vs_ai:
                # Go directly to game with default difficulty (medium)
                self._start_game()
            else:
                # Switch to P2 selection
                self.active_player = 2
                self.p2_selection = 0  # Initialize P2 selection
                self._update_card_selections()
        else:
            self.p2_confirmed = True
            self._start_game()

    def _go_back(self) -> None:
        """Go back to previous state or screen."""
        if self.p1_confirmed and not self.vs_ai:
            self.p1_confirmed = False
            self.active_player = 1
            self.p2_selection = None  # Reset P2 selection
            self._update_card_selections()
        else:
            self.state_machine.change_state(GameState.MAIN_MENU)

    def _start_game(self) -> None:
        """Start the game with selected characters."""
        # Play start sound
        self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "start"})

        p1_char = self.character_cards[self.p1_selection].config

        if self.vs_ai:
            # AI gets a random character different from P1
            import random
            available = [c for i, c in enumerate(self.character_cards)
                         if i != self.p1_selection]
            p2_char = random.choice(available).config if available else p1_char
            difficulty = "medium"  # Default difficulty
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
        """Render the character select screen with proportional positioning."""
        # Background
        if self.background_image:
            surface.blit(self.background_image, (0, 0))
        else:
            surface.fill(self.bg_color)

        # Title image at top
        if self.title_image:
            title_rect = self.title_image.get_rect()
            title_x = (self.screen_width - title_rect.width) // 2
            title_y = int(self.screen_height * 0.08)  # Moved up
            surface.blit(self.title_image, (title_x, title_y))

        # Player indicator
        if not self.vs_ai and self.back_font:
            indicator_y = int(self.screen_height * 0.33)
            if self.active_player == 1:
                choose_text = "Player 1 Select"
                choose_color = self.p1_color
            else:
                choose_text = "Player 2 Select"
                choose_color = self.p2_color
            self.draw_text(surface, choose_text, self.back_font, choose_color,
                           (self.screen_width // 2, indicator_y))

        # Draw character cards
        for card in self.character_cards:
            self._render_card(surface, card)

        # Back button (at same position as settings screen)
        if self.back_font:
            # Calculate position similar to settings screen
            back_y = int(self.screen_height * 0.92) - 40
            back_text_color = self.back_selected_color if self.back_selected else self.back_color
            self.back_button_rect = self.draw_text(surface, "Back", self.back_font, back_text_color,
                                                    (self.screen_width // 2, back_y))

            # Draw select indicator when back is selected
            if self.back_selected and self.select_indicator and self.back_button_rect:
                select_rect = self.select_indicator.get_rect()
                select_x = self.back_button_rect.left - select_rect.width - 6
                select_y = self.back_button_rect.centery - select_rect.height // 2
                surface.blit(self.select_indicator, (select_x, select_y))

        # Instructions at bottom
        self.draw_text(surface, "Arrow Keys + Enter to Select", self.small_font, (147, 76, 48),
                       (self.screen_width // 2, self.screen_height - 40))

    def _render_card(self, surface: pygame.Surface, card: CharacterCard) -> None:
        """Render a character card with profile image."""
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

        # Get profile image for this character
        char_id = card.character_id.lower()
        profile_img = self.profile_images.get(char_id)

        if profile_img:
            # Scale profile image to fit card (80% of card size)
            img_width = (card.rect.width - 10) * 0.8
            img_height = (card.rect.height - 10) * 0.8

            # Maintain aspect ratio
            orig_rect = profile_img.get_rect()
            scale = min(img_width / orig_rect.width, img_height / orig_rect.height)
            new_width = int(orig_rect.width * scale)
            new_height = int(orig_rect.height * scale)
            scaled_img = pygame.transform.scale(profile_img, (new_width, new_height))

            # Center the image in the card
            img_x = card.rect.centerx - new_width // 2
            img_y = card.rect.centery - new_height // 2

            surface.blit(scaled_img, (img_x, img_y))

            # Draw selection border on top of image
            if card.selected_p1 or card.selected_p2:
                border_rect = pygame.Rect(img_x - 2, img_y - 2, new_width + 4, new_height + 4)
                # Use player color for selection box
                if card.selected_p1 and card.selected_p2:
                    selection_color = (200, 150, 255)  # Purple for both
                elif card.selected_p1:
                    selection_color = self.p1_color
                else:
                    selection_color = self.p2_color
                pygame.draw.rect(surface, selection_color, border_rect, 4, border_radius=20)
        else:
            # Fallback: draw card background with name
            bg_color = (30, 40, 70) if (card.selected_p1 or card.selected_p2) else (25, 35, 60)
            pygame.draw.rect(surface, bg_color, card.rect, border_radius=8)
            pygame.draw.rect(surface, border_color, card.rect, border_width, border_radius=8)

            name_color = self.highlight_color if (card.selected_p1 or card.selected_p2) else self.text_color
            self.draw_text(surface, card.name.upper(), self.menu_font, name_color,
                           (card.rect.centerx, card.rect.centery))
