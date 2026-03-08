"""Admin / master settings screen — game parameters only."""

import os
import pygame
from typing import Dict, Any, List, Optional

from .base_screen import BaseScreen
from ..core.state_machine import GameState
from ..core.event_bus import GameEvent


# ──────────────────────────────────────────────────────────────────────────────
# Data model — identical pattern to SettingItem in settings.py
# ──────────────────────────────────────────────────────────────────────────────

class AdminItem:
    """A single editable admin parameter row."""

    def __init__(self, name: str, section: str, key: str, kind: str,
                 y_position: int, current_value: Any,
                 options: List = None,
                 min_val: float = 0.0, max_val: float = 10.0, step: float = 0.5):
        self.name          = name
        self.section       = section
        self.key           = key
        self.kind          = kind          # "select" | "slider"
        self.y_position    = y_position
        self.value         = current_value
        self.options       = options or []
        self.min_val       = min_val
        self.max_val       = max_val
        self.step          = step
        self.selected      = False
        self.rect: Optional[pygame.Rect] = None


# ──────────────────────────────────────────────────────────────────────────────
# Screen
# ──────────────────────────────────────────────────────────────────────────────

class AdminSettingsScreen(BaseScreen):
    """Admin settings screen — exposes tunable game parameters."""

    def __init__(self, state_machine, config, event_bus):
        super().__init__(state_machine, config, event_bus)

        self.items: List[AdminItem] = []
        self.selected_index = 0

        # Colours — pixel-perfect match with SettingsScreen
        self.bg_color       = (20, 20, 40)
        self.title_color    = (255, 200, 0)
        self.text_color     = (77, 43, 31)      # #4D2B1F
        self.selected_color = (147, 76, 48)     # #934C30
        self.slider_bg      = (220, 165, 86)    # #DCA556

        # Assets
        self.background_image:   Optional[pygame.Surface] = None
        self.title_image:        Optional[pygame.Surface] = None
        self.menu_tall_image:    Optional[pygame.Surface] = None
        self.select_indicator:   Optional[pygame.Surface] = None

        # Fonts  (set in _load_custom_font — always override base defaults)
        self.label_font:         Optional[pygame.font.Font] = None  # item labels
        self.value_font:         Optional[pygame.font.Font] = None  # select values
        self.back_font:          Optional[pygame.font.Font] = None  # buttons & title
        self.footer_font:        Optional[pygame.font.Font] = None  # footer hint
        # Keep menu_font / small_font for compatibility with draw_text fallbacks
        self.menu_font:          Optional[pygame.font.Font] = None
        self.small_font:         Optional[pygame.font.Font] = None

        # Button rects & state
        self.back_button_rect:   Optional[pygame.Rect] = None
        self.save_button_rect:   Optional[pygame.Rect] = None
        self.back_selected       = False
        self.save_selected       = False

        # Pending values — written to disk only on Save
        self._pending: Dict[str, Dict[str, Any]] = {}

        # Text input state
        self.typing_text = False
        self.text_input  = ""

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, data: Dict[str, Any] = None) -> None:
        self.initialize_fonts()   # base defaults (overridden below)
        self._load_custom_font()
        self._load_images()
        self._create_items()
        self.selected_index = 0
        self.back_selected  = False
        self.save_selected  = False
        if self.items:
            self.items[0].selected = True

    def on_exit(self) -> None:
        pass  # changes only committed on Save

    # ── Font loading ──────────────────────────────────────────────────────────

    def _load_custom_font(self) -> None:
        base_dir  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        font_path = os.path.join(base_dir, "ui", "Daydream.ttf")
        if os.path.exists(font_path):
            # label_font is smaller than the settings 28px to avoid overflow
            self.label_font  = pygame.font.Font(font_path, 22)
            self.value_font  = pygame.font.Font(font_path, 22)
            self.back_font   = pygame.font.Font(font_path, 32)
            self.footer_font = pygame.font.Font(font_path, 16)
            # Keep menu_font / small_font for anything calling the base pattern
            self.menu_font   = self.label_font
            self.small_font  = self.footer_font

    # ── Image loading ─────────────────────────────────────────────────────────

    def _load_images(self) -> None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ui_dir   = os.path.join(base_dir, "ui")

        # Background
        bg_path = os.path.join(ui_dir, "Settings background.png")
        if os.path.exists(bg_path):
            img = pygame.image.load(bg_path).convert()
            self.background_image = pygame.transform.scale(
                img, (self.screen_width, self.screen_height)
            )

        # Title text image — reuse the "settings text.png" style header
        title_path = os.path.join(ui_dir, "settings text.png")
        if os.path.exists(title_path):
            img = pygame.image.load(title_path).convert_alpha()
            max_w = int(self.screen_width * 0.6)
            max_h = int(self.screen_height * 0.12)
            scale = min(max_w / img.get_width(), max_h / img.get_height())
            self.title_image = pygame.transform.scale(
                img, (int(img.get_width() * scale), int(img.get_height() * scale))
            )

        # Tall panel — same scale as settings screen
        panel_path = os.path.join(ui_dir, "Menu tall.png")
        if os.path.exists(panel_path):
            img   = pygame.image.load(panel_path).convert_alpha()
            max_w = int(self.screen_width  * 0.8)
            max_h = int(self.screen_height * 0.7)
            scale = min(max_w / img.get_width(), max_h / img.get_height())
            self.menu_tall_image = pygame.transform.scale(
                img, (int(img.get_width() * scale), int(img.get_height() * scale))
            )

        # Select chevron
        sel_path = os.path.join(ui_dir, "Select.png")
        if os.path.exists(sel_path):
            img = pygame.image.load(sel_path).convert_alpha()
            s   = 0.576
            self.select_indicator = pygame.transform.scale(
                img, (int(img.get_width() * s), int(img.get_height() * s))
            )

    # ── Build items from config ────────────────────────────────────────────────

    def _create_items(self) -> None:
        admin    = self.config.get_admin_settings()
        game_cfg = admin.get("game_settings", {})

        self._pending = {"game_settings": dict(game_cfg)}

        round_val = game_cfg.get("round_duration_seconds", 90)
        ta_val    = game_cfg.get("treat_attack_round_duration_seconds", 60)
        pu_dur    = float(game_cfg.get("powerup_duration_seconds", 5.0))
        spd_mult  = float(game_cfg.get("powerup_speed_boost_multiplier", 1.5))
        cust_img  = game_cfg.get("custom_power_treat_image", "")
        cust_name = game_cfg.get("custom_power_treat_name", "")

        # --- Vertical layout — same anchor as SettingsScreen ---
        start_y = int(self.screen_height * 0.35)
        spacing = int(self.screen_height * 0.08)

        round_opts = [30, 60, 90, 120]
        ta_opts    = [30, 60, 90]
        round_val  = min(round_opts, key=lambda x: abs(x - round_val))
        ta_val     = min(ta_opts,    key=lambda x: abs(x - ta_val))

        # NOTE: keep labels ≤ 11 characters so they never overflow into the
        #       value column at label_font size 22px.
        self.items = [
            AdminItem("Round Dur",   "game_settings", "round_duration_seconds",
                      "select", start_y,           round_val, options=round_opts),
            AdminItem("Treat Atk",   "game_settings", "treat_attack_round_duration_seconds",
                      "select", start_y + spacing,  ta_val,   options=ta_opts),
            AdminItem("Powerup Dur", "game_settings", "powerup_duration_seconds",
                      "slider", start_y + spacing * 2, pu_dur,
                      min_val=1.0, max_val=15.0, step=0.5),
            AdminItem("Speed Boost", "game_settings", "powerup_speed_boost_multiplier",
                      "slider", start_y + spacing * 3, spd_mult,
                      min_val=1.0, max_val=3.0, step=0.1),
            AdminItem("Spcl Treat",  "game_settings", "custom_power_treat_image",
                      "logo",   start_y + spacing * 4, cust_img),
            AdminItem("Spcl Name",   "game_settings", "custom_power_treat_name",
                      "text",   start_y + spacing * 5, cust_name),
        ]

    # ── Input handling ─────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.typing_text:
            self._handle_text_input(event)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self._move_selection(-1)
            elif event.key == pygame.K_DOWN:
                self._move_selection(1)
            elif event.key == pygame.K_LEFT:
                self._adjust_value(-1)
            elif event.key == pygame.K_RIGHT:
                self._adjust_value(1)
            elif event.key == pygame.K_RETURN:
                if self.save_selected:
                    self._save_and_back()
                elif self.back_selected:
                    self._go_back()
                else:
                    self._adjust_value(1)
            elif event.key == pygame.K_ESCAPE:
                self._go_back()

        elif event.type == pygame.MOUSEMOTION:
            self._handle_hover(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def _handle_hover(self, pos) -> None:
        hovered = False
        for i, item in enumerate(self.items):
            if item.rect and item.rect.collidepoint(pos):
                hovered = True
                if self.selected_index != i or self.back_selected or self.save_selected:
                    self._clear_selection()
                    self.selected_index = i
                    item.selected = True
                break

        if not hovered:
            if self.save_button_rect and self.save_button_rect.collidepoint(pos):
                if not self.save_selected:
                    self._clear_selection()
                    self.save_selected = True
            elif self.back_button_rect and self.back_button_rect.collidepoint(pos):
                if not self.back_selected:
                    self._clear_selection()
                    self.back_selected = True
            else:
                if self.back_selected or self.save_selected:
                    self.back_selected = False
                    self.save_selected = False
                    if 0 <= self.selected_index < len(self.items):
                        self.items[self.selected_index].selected = True

    def _handle_click(self, pos) -> None:
        if self.save_button_rect and self.save_button_rect.collidepoint(pos):
            self._save_and_back()
        elif self.back_button_rect and self.back_button_rect.collidepoint(pos):
            self._go_back()

    def _clear_selection(self) -> None:
        for item in self.items:
            item.selected = False
        self.back_selected = False
        self.save_selected = False

    def _move_selection(self, direction: int) -> None:
        n   = len(self.items)
        # Virtual index: 0..n-1 = items, n = save button, n+1 = back button
        cur = (n if self.save_selected
               else n + 1 if self.back_selected
               else self.selected_index)
        nxt = (cur + direction) % (n + 2)

        self._clear_selection()
        if nxt < n:
            self.selected_index = nxt
            self.items[nxt].selected = True
        elif nxt == n:
            self.save_selected = True
        else:
            self.back_selected = True

        self.event_bus.emit(GameEvent.PLAY_SOUND, {"sound": "select"})

    def _adjust_value(self, direction: int) -> None:
        if self.back_selected or self.save_selected:
            return
        if not self.items:
            return
        item = self.items[self.selected_index]

        if item.kind == "logo":
            self._open_file_dialog(item)
        elif item.kind == "text":
            self.typing_text = True
            self.text_input  = str(item.value)
        elif item.kind == "select":
            idx = item.options.index(item.value) if item.value in item.options else 0
            idx = (idx + direction) % len(item.options)
            item.value = item.options[idx]
        elif item.kind == "slider":
            item.value = round(
                max(item.min_val, min(item.max_val, item.value + direction * item.step)), 2
            )
        self._pending[item.section][item.key] = item.value

    def _handle_text_input(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.typing_text = False
                item = self.items[self.selected_index]
                item.value = self.text_input
                self._pending[item.section][item.key] = item.value
            elif event.key == pygame.K_ESCAPE:
                self.typing_text = False
            elif event.key == pygame.K_BACKSPACE:
                self.text_input = self.text_input[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable() and len(self.text_input) < 15:
                    self.text_input += ch

    def _copy_to_food_dir(self, source_path: str) -> str:
        import os
        import shutil
        food_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Food")
        os.makedirs(food_dir, exist_ok=True)
        filename = os.path.basename(source_path)
        dest_path = os.path.join(food_dir, filename)
        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            shutil.copy2(source_path, dest_path)
        return dest_path

    def _open_file_dialog(self, item: AdminItem) -> None:
        import sys
        if sys.platform == 'darwin':
            try:
                import subprocess
                script = (
                    'set theFile to choose file with prompt "Select a custom image" '
                    'of type {"public.png", "public.jpeg", "public.image"}\n'
                    'return POSIX path of theFile'
                )
                result = subprocess.run(
                    ['osascript', '-e', script],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0 and result.stdout.strip():
                    item.value = self._copy_to_food_dir(result.stdout.strip())
                    self._pending[item.section][item.key] = item.value
            except Exception:
                self._open_file_dialog_tkinter(item)
        else:
            self._open_file_dialog_tkinter(item)

    def _open_file_dialog_tkinter(self, item: AdminItem) -> None:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.lift()
            root.attributes("-topmost", True)

            file_path = filedialog.askopenfilename(
                title="Select a custom image",
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")],
            )
            root.destroy()
            if file_path:
                item.value = self._copy_to_food_dir(file_path)
                self._pending[item.section][item.key] = item.value
        except ImportError:
            pass

    # ── Commit / discard ──────────────────────────────────────────────────────

    def _save_and_back(self) -> None:
        for section, kv in self._pending.items():
            for key, val in kv.items():
                self.config.update_admin_setting(section, key, val)
        
        # Clear sprite cache so custom treat images reload
        from ..sprites.sprite_sheet_loader import SpriteSheetLoader
        SpriteSheetLoader().clear_cache()
        
        self.state_machine.change_state(GameState.SETTINGS)

    def _go_back(self) -> None:
        self.state_machine.change_state(GameState.SETTINGS)

    # ── Update ─────────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        pass

    # ═══════════════════════════════════════════════════════════════════════════
    # Render
    # ═══════════════════════════════════════════════════════════════════════════

    def render(self, surface: pygame.Surface) -> None:
        # 1 — Background ──────────────────────────────────────────────────
        if self.background_image:
            surface.blit(self.background_image, (0, 0))
        else:
            surface.fill(self.bg_color)

        # 2 — Tall panel ──────────────────────────────────────────────────
        if self.menu_tall_image:
            mr = self.menu_tall_image.get_rect()
            mx = (self.screen_width  - mr.width)  // 2
            my = int(self.screen_height * 0.22)
            surface.blit(self.menu_tall_image, (mx, my))

        # 3 — Title ───────────────────────────────────────────────────────
        self._render_title(surface)

        # 4 — Parameter rows ──────────────────────────────────────────────
        for item in self.items:
            self._render_item(surface, item)

        # 5 — Bottom buttons ──────────────────────────────────────────────
        self._render_bottom_buttons(surface)

        # 6 — Footer hint ─────────────────────────────────────────────────
        ff = self.footer_font or self.small_font
        if ff:
            self.draw_text(
                surface,
                "Arrow Keys + Enter  |  Left / Right to change",
                ff, self.text_color,
                (self.screen_width // 2, self.screen_height - 40),
            )

    # ── Render helpers ────────────────────────────────────────────────────────

    def _render_title(self, surface: pygame.Surface) -> None:
        """Draw title above the panel, mirroring settings.py."""
        title_y = int(self.screen_height * 0.12)
        if self.title_image:
            tr = self.title_image.get_rect()
            surface.blit(self.title_image, ((self.screen_width - tr.width) // 2, title_y))
        else:
            # Fallback: plain text with a subtle dark backing for legibility
            font = self.back_font
            if font:
                text = "Admin Settings"
                ts   = font.render(text, True, self.title_color)
                tx   = (self.screen_width  - ts.get_width())  // 2
                ty   = title_y - ts.get_height() // 2
                # Dark backing rect
                pad = 10
                backing = pygame.Rect(tx - pad, ty - pad // 2,
                                      ts.get_width() + pad * 2, ts.get_height() + pad)
                pygame.draw.rect(surface, (20, 10, 5, 180), backing, border_radius=6)
                surface.blit(ts, (tx, ty))

    def _render_item(self, surface: pygame.Surface, item: AdminItem) -> None:
        """Render one parameter row.  Layout mirrors SettingsScreen exactly:
           label at name_x (left-aligned), control at value_x (left-aligned)."""
        color = self.selected_color if item.selected else self.text_color
        font  = self.label_font or self.menu_font

        # ── Proportional x positions (pushed inward to fit wide controls) ────────
        name_x  = int(self.screen_width * 0.25)
        value_x = int(self.screen_width * 0.55)

        # ── Hit-rect (wide, same as SettingsScreen) ────────────────────────
        item.rect = pygame.Rect(
            name_x, item.y_position - 15,
            int(self.screen_width * 0.65), 40
        )

        # ── Label ──────────────────────────────────────────────────────────
        if font:
            self.draw_text(surface, item.name, font, color,
                           (name_x, item.y_position), center=False)

        # ── Selection chevron (left of label) ─────────────────────────────
        if item.selected and self.select_indicator:
            si = self.select_indicator
            surface.blit(si, (name_x - si.get_width() - 6,
                               item.y_position - si.get_height() // 2))

        # ── Value control ──────────────────────────────────────────────────
        if item.kind == "select":
            self._render_select(surface, item, value_x, color)
        elif item.kind == "slider":
            self._render_slider(surface, item, value_x, color)
        elif item.kind == "logo":
            self._render_logo_slot(surface, item, value_x, color)
        elif item.kind == "text":
            self._render_text_slot(surface, item, value_x, color)

    # ── Select (< VALUE >) ────────────────────────────────────────────────────

    def _render_select(self, surface: pygame.Surface, item: AdminItem,
                       value_x: int, color: tuple) -> None:
        """Render a cycle-selector using drawn triangle arrows and centred text.

        We deliberately do NOT use '<' and '>' text glyphs because the Daydream
        pixel font may render them as blank / invisible at small sizes.
        """
        font = self.value_font or self.label_font
        if not font:
            return

        # Fixed geometry — all measured from value_x
        arrow_size = 10          # px half-size of the triangle
        arrow_gap  = 14          # gap from value_x to left-arrow tip
        zone_w     = 90          # fixed zone for the value text
        right_gap  = 14          # gap after value zone before right arrow

        left_ax  = value_x + arrow_gap
        val_cx   = left_ax + arrow_size + 12 + zone_w // 2
        right_ax = val_cx + zone_w // 2 + 12 + arrow_size

        # Centre-y for text: y_position is the *top-left* y in our system,
        # so add half line-height to get visual midpoint.
        lh = font.get_height()
        cy = item.y_position + lh // 2   # visual vertical centre

        # Left triangle ◄
        self._draw_triangle(surface, left_ax, cy, arrow_size, direction=-1, color=color)

        # Value text — centred in its zone
        val_text = f"{item.value}s"
        val_surf = font.render(val_text, True,
                               self.selected_color if item.selected else color)
        vx = val_cx - val_surf.get_width()  // 2
        vy = cy     - val_surf.get_height() // 2
        surface.blit(val_surf, (vx, vy))

        # Right triangle ►
        self._draw_triangle(surface, right_ax, cy, arrow_size, direction=1, color=color)

    def _draw_triangle(self, surface: pygame.Surface,
                       cx: int, cy: int, size: int,
                       direction: int, color: tuple) -> None:
        """Draw a solid filled triangle arrow.
        direction: -1 = left-pointing, +1 = right-pointing."""
        if direction < 0:   # ◄
            pts = [(cx + size, cy - size),
                   (cx - size, cy),
                   (cx + size, cy + size)]
        else:               # ►
            pts = [(cx - size, cy - size),
                   (cx + size, cy),
                   (cx - size, cy + size)]
        pygame.draw.polygon(surface, color, pts)

    # ── Slider ────────────────────────────────────────────────────────────────

    def _render_slider(self, surface: pygame.Surface, item: AdminItem,
                       value_x: int, color: tuple) -> None:
        """Render a horizontal slider — exactly like SettingsScreen."""
        slider_width  = int(self.screen_width * 0.14)
        slider_height = 20
        slider_x      = value_x
        # Vertically centre the bar on the text baseline (same offset as SettingsScreen)
        slider_y      = item.y_position - slider_height // 2 + 24

        # Track
        pygame.draw.rect(surface, self.slider_bg,
                         (slider_x, slider_y, slider_width, slider_height),
                         border_radius=4)

        # Fill
        ratio  = (item.value - item.min_val) / max(item.max_val - item.min_val, 0.001)
        fill_w = int(slider_width * ratio)
        if fill_w > 0:
            pygame.draw.rect(surface, color,
                             (slider_x, slider_y, fill_w, slider_height),
                             border_radius=4)

        # Border
        pygame.draw.rect(surface, color,
                         (slider_x, slider_y, slider_width, slider_height),
                         2, border_radius=4)

        # Numeric label to the right
        sf = self.footer_font or self.small_font
        if sf:
            suffix  = "x" if item.key.endswith("multiplier") else "s"
            val_str = f"{item.value:.1f}{suffix}"
            # Vertically align with the bar centre
            lbl_y = slider_y + slider_height // 2 - sf.get_height() // 2
            self.draw_text(surface, val_str, sf, color,
                           (slider_x + slider_width + 12, lbl_y), center=False)

    # ── Logo Slot ─────────────────────────────────────────────────────────────

    def _render_logo_slot(self, surface: pygame.Surface, item: AdminItem,
                          value_x: int, color: tuple) -> None:
        font = self.footer_font or self.small_font
        if not font:
            return

        display_text = str(item.value)
        if not display_text:
            display_text = "[None - Press Enter to Upload]"
        else:
            # show filename instead of full path
            import os
            display_text = os.path.basename(display_text)

        # Simple text box rendering for the path
        box_width = int(self.screen_width * 0.35)
        box_height = 24
        box_y = item.y_position - box_height // 2 + 10

        bg_col = (20, 10, 5)
        pygame.draw.rect(surface, bg_col, (value_x, box_y, box_width, box_height), border_radius=4)
        pygame.draw.rect(surface, color,  (value_x, box_y, box_width, box_height), 2, border_radius=4)

        rendered = font.render(display_text, True, color)
        # If text is too wide, we only show the start or end of it
        if rendered.get_width() > box_width - 8:
            surf = pygame.Surface((box_width - 8, rendered.get_height()), pygame.SRCALPHA)
            surf.blit(rendered, (0, 0)) # just show the start
            rendered = surf
        
        surface.blit(rendered, (value_x + 4, box_y + box_height // 2 - rendered.get_height() // 2))

    # ── Text Slot ─────────────────────────────────────────────────────────────

    def _render_text_slot(self, surface: pygame.Surface, item: AdminItem,
                          value_x: int, color: tuple) -> None:
        font = self.footer_font or self.small_font
        if not font:
            return

        is_editing = (self.typing_text and item.selected)
        display_text = self.text_input + "_" if is_editing else str(item.value)
        if not display_text and not is_editing:
            display_text = "[None]"

        # Simple text box rendering for the text
        box_width = int(self.screen_width * 0.35)
        box_height = 24
        box_y = item.y_position - box_height // 2 + 10

        bg_col = (40, 20, 15) if is_editing else (20, 10, 5)
        pygame.draw.rect(surface, bg_col, (value_x, box_y, box_width, box_height), border_radius=4)
        pygame.draw.rect(surface, color,  (value_x, box_y, box_width, box_height), 2, border_radius=4)

        # Truncate text if it's too long
        rendered = font.render(display_text, True, self.title_color if is_editing else color)
        # If text is too wide, we only show the end of it
        if rendered.get_width() > box_width - 8:
            surf = pygame.Surface((box_width - 8, rendered.get_height()), pygame.SRCALPHA)
            surf.blit(rendered, (box_width - 8 - rendered.get_width(), 0))
            rendered = surf
        
        surface.blit(rendered, (value_x + 4, box_y + box_height // 2 - rendered.get_height() // 2))

    # ── Bottom buttons ─────────────────────────────────────────────────────────

    def _render_bottom_buttons(self, surface: pygame.Surface) -> None:
        font = self.back_font
        if not font:
            return

        # Same vertical position as SettingsScreen back button
        btn_y = int(self.screen_height * 0.92) - 40
        ctr   = self.screen_width // 2

        # Back ────────────────────────────────────────────────────────────────
        back_col = self.selected_color if self.back_selected else self.text_color
        self.back_button_rect = self.draw_text(
            surface, "Back", font, back_col,
            (ctr - 160, btn_y)
        )
        if self.back_selected and self.select_indicator:
            si = self.select_indicator
            surface.blit(si, (self.back_button_rect.left - si.get_width() - 6,
                               self.back_button_rect.centery - si.get_height() // 2))

        # Save ────────────────────────────────────────────────────────────────
        save_col = self.title_color if self.save_selected else self.text_color
        self.save_button_rect = self.draw_text(
            surface, "Save", font, save_col,
            (ctr + 80, btn_y)
        )
        if self.save_selected and self.select_indicator:
            si = self.select_indicator
            surface.blit(si, (self.save_button_rect.left - si.get_width() - 6,
                               self.save_button_rect.centery - si.get_height() // 2))
