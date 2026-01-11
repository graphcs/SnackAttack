# Jazzy's Snack Attack

A retro-style 2D arcade game where players control dogs to collect snacks! Features split-screen gameplay with 1-player vs AI and 2-player local modes.

![Main Menu](screenshots/main_menu.png)

## Features

- **6 Unique Dog Characters** - Each with different speeds and personalities
- **Animated Sprite Sheets** - Smooth running and eating animations
- **Split-Screen Gameplay** - Compete head-to-head in real-time
- **1P vs AI Mode** - Challenge the computer with Easy, Medium, or Hard difficulty
- **2P Local Mode** - Play against a friend on the same keyboard
- **6 Different Snacks** - Pizza, Bacon, Steak, Bones, and more!
- **Power-ups & Penalties** - Speed boosts, invincibility, and chaos effects
- **3 Progressive Levels** - Kitchen, Backyard, and Dog Park
- **Retro Pixel Art Style** - Detailed sprites with a nostalgic feel

## Screenshots

### Character Selection
![Character Select](screenshots/character_select.png)

### Gameplay
<img width="1904" height="1488" alt="CleanShot 2026-01-06 at 18 44 44@2x" src="https://github.com/user-attachments/assets/ab0ccf86-36b3-4580-aebe-73b8917bf837" />

### Settings
![Settings](screenshots/settings.png)

### Game Over
![Game Over](screenshots/game_over.png)

## Installation

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/snack-attack.git
cd snack-attack

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

## How to Play

```bash
# Run the game
python main.py
```

### Controls

| Action | Player 1 | Player 2 |
|--------|----------|----------|
| Move Up | W | Arrow Up |
| Move Down | S | Arrow Down |
| Move Left | A | Arrow Left |
| Move Right | D | Arrow Right |

- **Enter** - Confirm selection
- **Escape** - Pause / Back

### Snacks

| Snack | Points | Effect |
|-------|--------|--------|
| Pizza | +100 | None |
| Bacon | +150 | None |
| Steak | +250 | Invincibility (2s) |
| Bone | +25 | Speed Boost (5s) |
| Spicy Pepper | +200 | Chaos - controls flip! (4s) |
| Broccoli | -50 | Slow (3s) |

### Characters

- **Biggie** (Bulldog) - Slow but steady
- **Prissy** (Poodle) - Quick and agile
- **Dash** (Chihuahua) - Fastest of all!
- **Lobo** (Husky) - Balanced speed
- **Rex** (Dachshund) - Slightly above average
- **Jazzy** (Chihuahua) - Swift and spirited

## Project Structure

```
snack_attack/
├── main.py              # Entry point
├── requirements.txt     # Dependencies
├── config/              # Game configuration (JSON)
│   ├── game_settings.json
│   ├── characters.json
│   ├── snacks.json
│   ├── levels.json
│   ├── ai_difficulty.json
│   └── controls.json
├── src/
│   ├── game.py          # Main game loop
│   ├── core/            # Core systems
│   ├── entities/        # Game entities (Player, AI, Snack)
│   ├── screens/         # Game screens (Menu, Gameplay, etc.)
│   ├── sprites/         # Sprite loading and animation
│   └── audio/           # Audio management
├── Sprite sheets/       # Character animation sprite sheets
├── Profile/             # Character profile pictures
└── screenshots/         # Game screenshots
```

## Tech Stack

- **Python 3.10+**
- **Pygame 2.5+** - Game framework
- **JSON** - Configuration files

## License

MIT License - feel free to use and modify!

## Credits

Created with love for retro gaming and adorable dogs!
