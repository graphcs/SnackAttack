"""Upload avatar screen - allows users to upload a dog photo and generate a custom character."""

import pygame
import os
import threading
from typing import Dict, Any, Optional

from .base_screen import BaseScreen
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent
from ..generators.avatar_generator import AvatarGenerator, GenerationProgress, AvatarGenerationResult


class UploadAvatarScreen(BaseScreen):
    """Screen for uploading a dog photo and generating a custom avatar."""

    # Screen states
    STATE_INPUT = "input"           # Entering name and selecting photo
    STATE_GENERATING = "generating" # Generation in progress
    STATE_COMPLETE = "complete"     # Generation finished successfully
    STATE_ERROR = "error"           # Generation failed
    STATE_API_KEY = "api_key"       # Entering API key

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        # UI state
        self.screen_state = self.STATE_INPUT
        self.dog_name = ""
        self.photo_path = ""
        self.api_key = ""
        self.name_active = True  # Name input is active
        self.api_key_active = False

        # Generation
        self.progress: Optional[GenerationProgress] = None
        self.result: Optional[AvatarGenerationResult] = None
        self.gen_thread: Optional[threading.Thread] = None

        # Error display
        self.error_message = ""
        self.error_timer = 0.0

        # Colors
        self.bg_color = (20, 30, 60)
        self.text_color = (255, 255, 255)
        self.accent_color = (255, 200, 80)
        self.input_bg = (40, 50, 80)
        self.input_active = (60, 80, 130)
        self.button_color = (80, 140, 80)
        self.button_hover = (100, 180, 100)
        self.error_color = (255, 100, 100)
        self.success_color = (100, 255, 100)
        self.progress_bg = (40, 50, 80)
        self.progress_fill = (100, 180, 255)

        # Fonts
        self.custom_title_font: Optional[pygame.font.Font] = None
        self.custom_font: Optional[pygame.font.Font] = None
        self.custom_small_font: Optional[pygame.font.Font] = None

        # Buttons
        self.browse_button_rect: Optional[pygame.Rect] = None
        self.generate_button_rect: Optional[pygame.Rect] = None
        self.back_button_rect: Optional[pygame.Rect] = None
        self.done_button_rect: Optional[pygame.Rect] = None
        self.retry_button_rect: Optional[pygame.Rect] = None

        # Hover states
        self.browse_hovered = False
        self.generate_hovered = False
        self.back_hovered = False
        self.done_hovered = False
        self.retry_hovered = False

        # Preview image
        self.preview_image: Optional[pygame.Surface] = None
        self.generated_preview: Optional[pygame.Surface] = None

        # Game mode data to pass through
        self.passthrough_data: Dict[str, Any] = {}

        # Thread safety for progress updates
        self._progress_lock = threading.Lock()
        self._pending_progress: Optional[GenerationProgress] = None

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        """Initialize the upload screen."""
        self.initialize_fonts()
        self._load_custom_fonts()

        data = data or {}
        self.passthrough_data = {
            "mode": data.get("mode", "1p"),
            "vs_ai": data.get("vs_ai", True),
        }

        # Reset state
        self.screen_state = self.STATE_INPUT
        self.dog_name = ""
        self.photo_path = ""
        self.name_active = True
        self.api_key_active = False
        self.preview_image = None
        self.generated_preview = None
        self.progress = None
        self.result = None
        self.error_message = ""

        # Load saved API key from environment
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not self.api_key:
            self.screen_state = self.STATE_API_KEY

    def _load_custom_fonts(self) -> None:
        """Load custom Daydream font."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        font_path = os.path.join(base_dir, "ui", "Daydream.ttf")

        if os.path.exists(font_path):
            self.custom_title_font = pygame.font.Font(font_path, 28)
            self.custom_font = pygame.font.Font(font_path, 18)
            self.custom_small_font = pygame.font.Font(font_path, 14)
        else:
            self.custom_title_font = pygame.font.Font(None, 48)
            self.custom_font = pygame.font.Font(None, 32)
            self.custom_small_font = pygame.font.Font(None, 24)

    def on_exit(self) -> None:
        """Clean up when leaving."""
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle input events."""
        if self.screen_state == self.STATE_API_KEY:
            self._handle_api_key_events(event)
        elif self.screen_state == self.STATE_INPUT:
            self._handle_input_events(event)
        elif self.screen_state == self.STATE_COMPLETE:
            self._handle_complete_events(event)
        elif self.screen_state == self.STATE_ERROR:
            self._handle_error_events(event)

        # Common events
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.screen_state != self.STATE_GENERATING:
                self._go_back()

    def _handle_api_key_events(self, event: pygame.event.Event) -> None:
        """Handle events in API key entry mode."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.api_key.strip():
                    os.environ["OPENROUTER_API_KEY"] = self.api_key.strip()
                    # Save to .env file
                    self._save_api_key(self.api_key.strip())
                    self.screen_state = self.STATE_INPUT
                    self.name_active = True
            elif event.key == pygame.K_BACKSPACE:
                self.api_key = self.api_key[:-1]
            elif event.key == pygame.K_v and (event.mod & pygame.KMOD_META or event.mod & pygame.KMOD_CTRL):
                # Paste from clipboard using subprocess (pygame.scrap crashes on some macOS)
                try:
                    import subprocess, sys
                    if sys.platform == 'darwin':
                        result = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=2)
                        if result.returncode == 0 and result.stdout:
                            self.api_key += result.stdout.strip()
                    else:
                        result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'],
                                                capture_output=True, text=True, timeout=2)
                        if result.returncode == 0 and result.stdout:
                            self.api_key += result.stdout.strip()
                except Exception:
                    pass
            elif len(event.unicode) == 1 and event.unicode.isprintable():
                self.api_key += event.unicode

    def _handle_input_events(self, event: pygame.event.Event) -> None:
        """Handle events in input mode."""
        if event.type == pygame.KEYDOWN:
            if self.name_active:
                if event.key == pygame.K_RETURN:
                    if self.dog_name.strip() and self.photo_path:
                        self._start_generation()
                    elif not self.photo_path:
                        self._open_file_dialog()
                elif event.key == pygame.K_BACKSPACE:
                    self.dog_name = self.dog_name[:-1]
                elif event.key == pygame.K_TAB:
                    self.name_active = False
                elif len(event.unicode) == 1 and event.unicode.isprintable():
                    if len(self.dog_name) < 20:
                        self.dog_name += event.unicode

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.browse_button_rect and self.browse_button_rect.collidepoint(event.pos):
                self._open_file_dialog()
            elif self.generate_button_rect and self.generate_button_rect.collidepoint(event.pos):
                if self.dog_name.strip() and self.photo_path:
                    self._start_generation()
            elif self.back_button_rect and self.back_button_rect.collidepoint(event.pos):
                self._go_back()

        elif event.type == pygame.MOUSEMOTION:
            self.browse_hovered = bool(self.browse_button_rect and
                                       self.browse_button_rect.collidepoint(event.pos))
            self.generate_hovered = bool(self.generate_button_rect and
                                         self.generate_button_rect.collidepoint(event.pos))
            self.back_hovered = bool(self.back_button_rect and
                                     self.back_button_rect.collidepoint(event.pos))

    def _handle_complete_events(self, event: pygame.event.Event) -> None:
        """Handle events when generation is complete."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.done_button_rect and self.done_button_rect.collidepoint(event.pos):
                self._go_to_character_select()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._go_to_character_select()
        elif event.type == pygame.MOUSEMOTION:
            self.done_hovered = bool(self.done_button_rect and
                                     self.done_button_rect.collidepoint(event.pos))

    def _handle_error_events(self, event: pygame.event.Event) -> None:
        """Handle events when generation failed."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.retry_button_rect and self.retry_button_rect.collidepoint(event.pos):
                self.screen_state = self.STATE_INPUT
            elif self.back_button_rect and self.back_button_rect.collidepoint(event.pos):
                self._go_back()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.screen_state = self.STATE_INPUT
        elif event.type == pygame.MOUSEMOTION:
            self.retry_hovered = bool(self.retry_button_rect and
                                      self.retry_button_rect.collidepoint(event.pos))
            self.back_hovered = bool(self.back_button_rect and
                                     self.back_button_rect.collidepoint(event.pos))

    def _open_file_dialog(self) -> None:
        """Open a file dialog to select a dog photo."""
        import sys
        if sys.platform == 'darwin':
            self._open_file_dialog_macos()
        else:
            self._open_file_dialog_tkinter()

    def _open_file_dialog_macos(self) -> None:
        """Use osascript (AppleScript) for native macOS file picker — avoids pygame/tkinter conflicts."""
        try:
            import subprocess
            script = (
                'set theFile to choose file with prompt "Select a photo of your dog" '
                'of type {"public.png", "public.jpeg", "com.microsoft.bmp", "public.image"}\n'
                'return POSIX path of theFile'
            )
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0 and result.stdout.strip():
                file_path = result.stdout.strip()
                self.photo_path = file_path
                self._load_preview(file_path)
                if not self.dog_name:
                    self.name_active = True
        except Exception as e:
            # Fallback to tkinter
            self._open_file_dialog_tkinter()

    def _open_file_dialog_tkinter(self) -> None:
        """Fallback file dialog using tkinter."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.lift()
            root.attributes("-topmost", True)

            file_path = filedialog.askopenfilename(
                title="Select a photo of your dog",
                filetypes=[
                    ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                    ("PNG files", "*.png"),
                    ("JPEG files", "*.jpg *.jpeg"),
                    ("All files", "*.*"),
                ],
            )
            root.destroy()

            if file_path:
                self.photo_path = file_path
                self._load_preview(file_path)
                # Auto-focus name input if empty
                if not self.dog_name:
                    self.name_active = True

        except ImportError:
            self.error_message = "File dialog not available. Please install tkinter."
            self.error_timer = 3.0

    def _load_preview(self, path: str) -> None:
        """Load and scale a preview of the selected photo."""
        try:
            image = pygame.image.load(path).convert_alpha()
            # Scale to fit preview area (max 200x200)
            max_size = 200
            w, h = image.get_size()
            scale = min(max_size / w, max_size / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            self.preview_image = pygame.transform.smoothscale(image, (new_w, new_h))
        except (pygame.error, FileNotFoundError):
            self.preview_image = None

    def _start_generation(self) -> None:
        """Start the avatar generation process."""
        if not self.api_key:
            self.screen_state = self.STATE_API_KEY
            return

        self.screen_state = self.STATE_GENERATING
        self.progress = GenerationProgress()

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        generator = AvatarGenerator(self.api_key, base_dir)

        def on_progress(p: GenerationProgress):
            with self._progress_lock:
                self._pending_progress = p

        def on_complete(result: AvatarGenerationResult):
            with self._progress_lock:
                self.result = result
                if result.success:
                    self._pending_progress = GenerationProgress(
                        current_step=6, total_steps=6,
                        step_description="Done!",
                        is_complete=True, result=result
                    )
                else:
                    self._pending_progress = GenerationProgress(
                        is_error=True,
                        error_message=result.error_message
                    )

        self.gen_thread = generator.generate_avatar_async(
            self.photo_path, self.dog_name.strip(),
            progress_callback=on_progress,
            completion_callback=on_complete,
        )

    def _save_api_key(self, key: str) -> None:
        """Save the API key to .env file."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_path = os.path.join(base_dir, ".env")

        lines = []
        key_found = False
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith("OPENROUTER_API_KEY="):
                        lines.append(f"OPENROUTER_API_KEY={key}\n")
                        key_found = True
                    else:
                        lines.append(line)

        if not key_found:
            lines.append(f"OPENROUTER_API_KEY={key}\n")

        with open(env_path, "w") as f:
            f.writelines(lines)

    def _go_back(self) -> None:
        """Go back to character select."""
        self.state_machine.change_state(GameState.CHARACTER_SELECT, self.passthrough_data)

    def _go_to_character_select(self) -> None:
        """Navigate to character select with the new character available."""
        # Reload characters config
        self.config.reload_config("characters")
        self.state_machine.change_state(GameState.CHARACTER_SELECT, self.passthrough_data)

    def update(self, dt: float) -> None:
        """Update screen state."""
        # Process pending progress from background thread
        with self._progress_lock:
            if self._pending_progress is not None:
                self.progress = self._pending_progress
                self._pending_progress = None

                if self.progress.is_complete:
                    self.screen_state = self.STATE_COMPLETE
                    self.result = self.progress.result
                    # Load generated profile as preview
                    if self.result and self.result.profile_path:
                        try:
                            img = pygame.image.load(self.result.profile_path).convert_alpha()
                            size = 200
                            w, h = img.get_size()
                            scale = min(size / w, size / h)
                            self.generated_preview = pygame.transform.smoothscale(
                                img, (int(w * scale), int(h * scale))
                            )
                        except (pygame.error, FileNotFoundError):
                            pass

                elif self.progress.is_error:
                    self.screen_state = self.STATE_ERROR
                    self.error_message = self.progress.error_message

        # Error timer
        if self.error_timer > 0:
            self.error_timer -= dt

    def render(self, surface: pygame.Surface) -> None:
        """Render the upload avatar screen."""
        surface.fill(self.bg_color)

        if self.screen_state == self.STATE_API_KEY:
            self._render_api_key_input(surface)
        elif self.screen_state == self.STATE_INPUT:
            self._render_input(surface)
        elif self.screen_state == self.STATE_GENERATING:
            self._render_generating(surface)
        elif self.screen_state == self.STATE_COMPLETE:
            self._render_complete(surface)
        elif self.screen_state == self.STATE_ERROR:
            self._render_error(surface)

    def _render_api_key_input(self, surface: pygame.Surface) -> None:
        """Render API key input screen."""
        cx = self.screen_width // 2
        title_font = self.custom_title_font or self.title_font
        font = self.custom_font or self.menu_font
        small_font = self.custom_small_font or self.small_font

        # Title
        self.draw_text(surface, "OpenRouter API Key", title_font,
                       self.accent_color, (cx, 120))

        # Instructions
        self.draw_text(surface, "An API key is needed to", small_font,
                       self.text_color, (cx, 200))
        self.draw_text(surface, "generate your dog avatar.", small_font,
                       self.text_color, (cx, 230))
        self.draw_text(surface, "Get one at openrouter.ai", small_font,
                       (150, 200, 255), (cx, 280))

        # API key input
        input_w = 600
        input_h = 50
        input_x = cx - input_w // 2
        input_y = 340
        input_rect = pygame.Rect(input_x, input_y, input_w, input_h)
        pygame.draw.rect(surface, self.input_active, input_rect, border_radius=8)
        pygame.draw.rect(surface, self.accent_color, input_rect, 2, border_radius=8)

        # Display masked key
        display_key = "*" * min(len(self.api_key), 40) if self.api_key else ""
        key_font = self.small_font or pygame.font.Font(None, 24)
        if display_key:
            self.draw_text(surface, display_key, key_font,
                           self.text_color, (cx, input_y + input_h // 2))
        else:
            self.draw_text(surface, "Paste your API key here...", key_font,
                           (120, 120, 140), (cx, input_y + input_h // 2))

        # Cursor blink
        if pygame.time.get_ticks() % 1000 < 500:
            cursor_x = cx + (len(display_key) * 5)
            pygame.draw.line(surface, self.text_color,
                             (cursor_x, input_y + 10), (cursor_x, input_y + input_h - 10), 2)

        # Submit hint
        self.draw_text(surface, "Press Enter to continue", small_font,
                       (120, 120, 140), (cx, 430))

        # Back hint
        self.draw_text(surface, "Press Escape to go back", small_font,
                       (120, 120, 140), (cx, 470))

    def _render_input(self, surface: pygame.Surface) -> None:
        """Render the input form."""
        cx = self.screen_width // 2
        title_font = self.custom_title_font or self.title_font
        font = self.custom_font or self.menu_font
        small_font = self.custom_small_font or self.small_font

        # Title
        self.draw_text(surface, "Create Your Dog", title_font,
                       self.accent_color, (cx, 80))

        self.draw_text(surface, "Upload a photo and we'll", small_font,
                       self.text_color, (cx, 130))
        self.draw_text(surface, "turn it into a playable", small_font,
                       self.text_color, (cx, 155))
        self.draw_text(surface, "character!", small_font,
                       self.text_color, (cx, 180))

        # Name input
        name_label_y = 230
        self.draw_text(surface, "Dog's Name:", font,
                       self.text_color, (cx, name_label_y))

        input_w = 400
        input_h = 50
        input_x = cx - input_w // 2
        input_y = name_label_y + 35
        input_rect = pygame.Rect(input_x, input_y, input_w, input_h)
        bg = self.input_active if self.name_active else self.input_bg
        pygame.draw.rect(surface, bg, input_rect, border_radius=8)
        border_color = self.accent_color if self.name_active else (80, 90, 120)
        pygame.draw.rect(surface, border_color, input_rect, 2, border_radius=8)

        name_display = self.dog_name if self.dog_name else "Enter name..."
        name_color = self.text_color if self.dog_name else (120, 120, 140)
        self.draw_text(surface, name_display, font,
                       name_color, (cx, input_y + input_h // 2))

        # Photo section
        photo_y = input_y + input_h + 40

        if self.preview_image:
            # Show preview
            preview_rect = self.preview_image.get_rect()
            preview_x = cx - preview_rect.width // 2
            preview_y = photo_y
            surface.blit(self.preview_image, (preview_x, preview_y))

            # File name
            filename = os.path.basename(self.photo_path)
            if len(filename) > 30:
                filename = filename[:27] + "..."
            self.draw_text(surface, filename, small_font,
                           self.success_color, (cx, preview_y + preview_rect.height + 15))

            browse_y = preview_y + preview_rect.height + 40
        else:
            # Upload prompt
            upload_rect = pygame.Rect(cx - 150, photo_y, 300, 150)
            pygame.draw.rect(surface, self.input_bg, upload_rect, border_radius=10)
            pygame.draw.rect(surface, (80, 90, 120), upload_rect, 2, border_radius=10)

            self.draw_text(surface, "No photo selected", font,
                           (120, 120, 140), (cx, photo_y + 55))
            self.draw_text(surface, "Click Browse below", small_font,
                           (120, 120, 140), (cx, photo_y + 90))

            browse_y = photo_y + 170

        # Browse button
        btn_w = 200
        btn_h = 45
        browse_color = self.button_hover if self.browse_hovered else self.button_color
        self.browse_button_rect = pygame.Rect(cx - btn_w // 2, browse_y, btn_w, btn_h)
        pygame.draw.rect(surface, browse_color, self.browse_button_rect, border_radius=8)
        self.draw_text(surface, "Browse...", font,
                       self.text_color, (cx, browse_y + btn_h // 2))

        # Generate button (only enabled when both name and photo are set)
        gen_y = browse_y + btn_h + 30
        can_generate = bool(self.dog_name.strip() and self.photo_path)
        gen_color = (self.button_hover if self.generate_hovered else self.button_color) if can_generate else (60, 60, 80)
        gen_text_color = self.text_color if can_generate else (100, 100, 120)

        self.generate_button_rect = pygame.Rect(cx - 150, gen_y, 300, 55)
        pygame.draw.rect(surface, gen_color, self.generate_button_rect, border_radius=8)
        self.draw_text(surface, "Generate Avatar!", font,
                       gen_text_color, (cx, gen_y + 55 // 2))

        # Back button
        back_y = self.screen_height - 80
        back_color = self.button_hover if self.back_hovered else (100, 70, 60)
        self.back_button_rect = pygame.Rect(cx - 80, back_y, 160, 40)
        pygame.draw.rect(surface, back_color, self.back_button_rect, border_radius=8)
        self.draw_text(surface, "Back", font,
                       self.text_color, (cx, back_y + 20))

        # Error message
        if self.error_message and self.error_timer > 0:
            self.draw_text(surface, self.error_message, small_font,
                           self.error_color, (cx, self.screen_height - 130))

    def _render_generating(self, surface: pygame.Surface) -> None:
        """Render the generation progress screen."""
        cx = self.screen_width // 2
        cy = self.screen_height // 2
        title_font = self.custom_title_font or self.title_font
        font = self.custom_font or self.menu_font
        small_font = self.custom_small_font or self.small_font

        # Title
        self.draw_text(surface, "Generating Avatar", title_font,
                       self.accent_color, (cx, cy - 150))

        # Animated dots
        ticks = pygame.time.get_ticks()
        dots = "." * ((ticks // 500) % 4)
        self.draw_text(surface, f"Please wait{dots}", font,
                       self.text_color, (cx, cy - 90))

        if self.progress:
            # Step description
            self.draw_text(surface, self.progress.step_description, font,
                           self.text_color, (cx, cy - 30))

            # Progress bar
            bar_w = 500
            bar_h = 30
            bar_x = cx - bar_w // 2
            bar_y = cy + 20

            # Background
            pygame.draw.rect(surface, self.progress_bg,
                             (bar_x, bar_y, bar_w, bar_h), border_radius=10)

            # Fill
            if self.progress.total_steps > 0:
                fill_ratio = self.progress.current_step / self.progress.total_steps
                fill_w = int(bar_w * fill_ratio)
                if fill_w > 0:
                    pygame.draw.rect(surface, self.progress_fill,
                                     (bar_x, bar_y, fill_w, bar_h), border_radius=10)

            # Step counter
            step_text = f"Step {self.progress.current_step}/{self.progress.total_steps}"
            self.draw_text(surface, step_text, small_font,
                           self.text_color, (cx, bar_y + bar_h + 25))

        # Preview of source photo
        if self.preview_image:
            preview_rect = self.preview_image.get_rect()
            preview_x = cx - preview_rect.width // 2
            preview_y = cy + 100
            surface.blit(self.preview_image, (preview_x, preview_y))
            self.draw_text(surface, self.dog_name, small_font,
                           self.accent_color, (cx, preview_y + preview_rect.height + 15))

        # Hint
        self.draw_text(surface, "This may take 1-2 minutes", small_font,
                       (120, 120, 140), (cx, self.screen_height - 60))

    def _render_complete(self, surface: pygame.Surface) -> None:
        """Render the completion screen."""
        cx = self.screen_width // 2
        title_font = self.custom_title_font or self.title_font
        font = self.custom_font or self.menu_font
        small_font = self.custom_small_font or self.small_font

        # Title
        self.draw_text(surface, "Avatar Created!", title_font,
                       self.success_color, (cx, 100))

        name = self.result.character_name if self.result else self.dog_name
        self.draw_text(surface, f"{name} is ready to play!", font,
                       self.text_color, (cx, 170))

        # Show generated profile
        preview_y = 220
        if self.generated_preview:
            preview_rect = self.generated_preview.get_rect()
            preview_x = cx - preview_rect.width // 2
            surface.blit(self.generated_preview, (preview_x, preview_y))

            # Border around preview
            border_rect = pygame.Rect(preview_x - 4, preview_y - 4,
                                      preview_rect.width + 8, preview_rect.height + 8)
            pygame.draw.rect(surface, self.accent_color, border_rect, 3, border_radius=10)

            done_y = preview_y + preview_rect.height + 50
        else:
            done_y = preview_y + 100

        # Show original photo next to generated for comparison
        if self.preview_image and self.generated_preview:
            # Draw original smaller, to the left
            small_preview = pygame.transform.smoothscale(
                self.preview_image,
                (self.preview_image.get_width() // 2, self.preview_image.get_height() // 2)
            )
            orig_x = cx - 220
            orig_y = preview_y + 30
            surface.blit(small_preview, (orig_x, orig_y))
            self.draw_text(surface, "Original", small_font,
                           (120, 120, 140), (orig_x + small_preview.get_width() // 2, orig_y - 15))

            # Arrow
            arrow_x = cx - 80
            arrow_y = preview_y + 80
            self.draw_text(surface, ">>>", font,
                           self.accent_color, (arrow_x, arrow_y))

        # "Play Now" button
        btn_w = 300
        btn_h = 55
        done_color = self.button_hover if self.done_hovered else self.button_color
        self.done_button_rect = pygame.Rect(cx - btn_w // 2, done_y, btn_w, btn_h)
        pygame.draw.rect(surface, done_color, self.done_button_rect, border_radius=8)
        self.draw_text(surface, "Choose Character!", font,
                       self.text_color, (cx, done_y + btn_h // 2))

        # Hint
        self.draw_text(surface, "Press Enter to continue", small_font,
                       (120, 120, 140), (cx, self.screen_height - 60))

    def _render_error(self, surface: pygame.Surface) -> None:
        """Render the error screen."""
        cx = self.screen_width // 2
        cy = self.screen_height // 2
        title_font = self.custom_title_font or self.title_font
        font = self.custom_font or self.menu_font
        small_font = self.custom_small_font or self.small_font

        # Title
        self.draw_text(surface, "Generation Failed", title_font,
                       self.error_color, (cx, cy - 120))

        # Error message (wrapped)
        error_msg = self.error_message or "An unknown error occurred."
        # Simple line wrapping
        max_chars = 45
        lines = []
        while len(error_msg) > max_chars:
            split_idx = error_msg[:max_chars].rfind(" ")
            if split_idx == -1:
                split_idx = max_chars
            lines.append(error_msg[:split_idx])
            error_msg = error_msg[split_idx:].strip()
        lines.append(error_msg)

        for i, line in enumerate(lines[:4]):
            self.draw_text(surface, line, small_font,
                           self.text_color, (cx, cy - 40 + i * 30))

        # Retry button
        btn_y = cy + 60
        retry_color = self.button_hover if self.retry_hovered else self.button_color
        self.retry_button_rect = pygame.Rect(cx - 100, btn_y, 200, 50)
        pygame.draw.rect(surface, retry_color, self.retry_button_rect, border_radius=8)
        self.draw_text(surface, "Try Again", font,
                       self.text_color, (cx, btn_y + 25))

        # Back button
        back_y = btn_y + 70
        back_color = self.button_hover if self.back_hovered else (100, 70, 60)
        self.back_button_rect = pygame.Rect(cx - 80, back_y, 160, 40)
        pygame.draw.rect(surface, back_color, self.back_button_rect, border_radius=8)
        self.draw_text(surface, "Back", font,
                       self.text_color, (cx, back_y + 20))
