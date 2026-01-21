# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jazzy's Snack Attack is a retro-style 2D arcade game built with Pygame where players control dogs to collect snacks. Features split-screen gameplay (1P vs AI, 2P local), a Treat Attack mode, and Twitch chat integration for audience voting.

## Running the Project

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the game
source venv/bin/activate && python -m main
```

For Twitch integration, copy `.env.example` to `.env` and add your `TWITCH_ACCESS_TOKEN`.

## Architecture

### Core Design Patterns

**State Machine** (`src/core/state_machine.py`): Manages screen transitions via `GameState` enum (MAIN_MENU, CHARACTER_SELECT, GAMEPLAY, TREAT_ATTACK, PAUSED, SETTINGS, GAME_OVER).

**Event Bus** (`src/core/event_bus.py`): Singleton pub/sub system for game-wide communication. Events are emitted with payloads:
```python
self.event_bus.emit(GameEvent.SNACK_COLLECTED, {"snack_id": "pizza", "points": 100})
```

**Configuration Manager** (`src/core/config_manager.py`): Singleton that loads 9 JSON config files from `config/`. Supports dot notation:
```python
fps = config.get("game_settings.window.fps", 60)
```

**Screen Base Class** (`src/screens/base_screen.py`): Abstract base with lifecycle hooks: `on_enter(data)` → `update(dt)` → `render(surface)` → `on_exit()`.

### Key Singletons

`EventBus`, `ConfigManager`, `SpriteSheetLoader`, `AudioManager` all use singleton pattern - get instance via their class methods.

### Directory Structure

- `src/core/` - State machine, event bus, config manager
- `src/screens/` - Game screens (menu, character select, gameplay, etc.)
- `src/entities/` - Player, AI player, snacks, falling treats
- `src/sprites/` - Sprite sheet loading and animation controllers
- `src/audio/` - Event-driven audio manager
- `src/interaction/` - Twitch chat integration (async in background thread)
- `config/` - All game parameters in JSON (characters, snacks, levels, AI difficulty, controls)

### Asset Locations

- `Sprite sheets/` - Character animations (3 frames per animation)
- `Profile/` - Character portrait images
- `Food/` - Snack sprite images

## Display Configuration

- Window: 1200x1000 (wider to accommodate chat integration area)
- Split-screen: ~500px per player area with gap
- Sprite sizes: 144x144 (gameplay), 160x160 (portraits), 80x80 (food)

## Twitch Integration

The Twitch bot (`src/interaction/twitch_chat.py`) runs asynchronously in a background thread using `twitchio`. It posts pygame custom events from chat votes. Token is loaded from `.env` via `src/core/env_loader.py`.

## Game Modes

1. **1P vs AI** - Player vs computer with Easy/Medium/Hard difficulty
2. **2P Local** - Two-player split-screen on same keyboard
3. **Treat Attack** - Special mode with falling treats and catcher dogs
