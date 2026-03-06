# Jazzy's Treat Storm — System Design

This document summarizes the implemented system architecture and runtime flows of the game.

## 1) High-Level Architecture

```mermaid
flowchart TB
    User[Player / Twitch Chat]

    subgraph App[Game Application - Pygame]
        Main[main.py]
        Game[src/game.py\nGame loop + render scaling]
        SM[src/core/state_machine.py\nStateMachine]
        EB[src/core/event_bus.py\nEventBus]
        CFG[src/core/config_manager.py\nConfigManager]
        Audio[src/audio/audio_manager.py\nAudioManager]
    end

    subgraph Screens[Screens]
        MM[MainMenuScreen]
        CS[CharacterSelectScreen]
        GP[GameplayScreen]
        TA[TreatAttackGameplay]
        ST[SettingsScreen]
        GO[GameOverScreen]
        UA[UploadAvatarScreen]
        AS[AvatarShowcaseScreen]
    end

    subgraph GameplayDomain[Gameplay Domain]
        P1[Player]
        P2[Player / AIPlayer]
        Arena[Arena + FallingSnack]
        Vote[VotingSystem + VotingMeter + ChatSimulator]
        FX[StormIntroSequence + Powerup VFX]
    end

    subgraph Integrations[External Integrations]
        Twitch[Twitch Chat]
        OR[OpenRouter API]
        Rembg[rembg API]
        FS[Assets + JSON Config + .env]
    end

    Main --> Game
    Game --> CFG
    Game --> EB
    Game --> SM
    Game --> Audio
    Audio <-- events --> EB

    SM --> Screens
    MM --> SM
    CS --> SM
    GP --> SM
    TA --> SM
    ST --> SM
    GO --> SM
    UA --> SM
    AS --> SM

    GP --> P1
    GP --> P2
    GP --> Arena
    GP --> Vote
    GP --> FX
    GP --> Twitch

    TA --> Vote
    TA --> FX

    UA --> OR
    UA --> Rembg

    CFG --> FS
    Game --> FS
    GP --> FS
    UA --> FS

    Twitch --> GP
    User --> MM
    User --> CS
    User --> GP
    User --> TA
    User --> UA
```

## 2) Core Runtime Loop

```mermaid
sequenceDiagram
    participant U as User Input
    participant PG as pygame event queue
    participant G as Game.run()
    participant SM as StateMachine
    participant S as Current Screen
    participant EB as EventBus
    participant A as AudioManager

    loop Every frame
        G->>G: dt = clock.tick(fps)
        U->>PG: keyboard/mouse/window events
        G->>PG: poll events
        G->>S: handle_event(event)
        G->>EB: process_queue()
        EB-->>A: dispatch subscribed events
        G->>S: update(dt)
        G->>S: render(game_surface)
        G->>G: scale + blit to display
    end
```

## 3) Screen State Machine

```mermaid
stateDiagram-v2
    [*] --> MAIN_MENU

    MAIN_MENU --> CHARACTER_SELECT: 1P / 2P
    MAIN_MENU --> SETTINGS: Settings
    MAIN_MENU --> [*]: Quit

    SETTINGS --> MAIN_MENU: Back / Esc

    CHARACTER_SELECT --> GAMEPLAY: Confirm character(s)
    CHARACTER_SELECT --> UPLOAD_AVATAR: Create Your Dog
    CHARACTER_SELECT --> AVATAR_SHOWCASE: Right-click character
    CHARACTER_SELECT --> MAIN_MENU: Back / Esc

    AVATAR_SHOWCASE --> CHARACTER_SELECT: Back / Esc / Enter

    UPLOAD_AVATAR --> CHARACTER_SELECT: Done / Back

    GAMEPLAY --> GAME_OVER: Match complete
    GAMEPLAY --> MAIN_MENU: Pause + Quit

    GAME_OVER --> CHARACTER_SELECT: Play Again
    GAME_OVER --> MAIN_MENU: Main Menu
```

## 4) Gameplay (Split-Screen) Internal Component Diagram

```mermaid
flowchart LR
    subgraph GameplayScreen
        Input[Keyboard + Mouse + TWITCH_VOTE_EVENT]
        Rounds[Countdown -> Walk-in -> Round -> EndRound]
        Vote[VotingSystem\nACTION / TREAT / TRIVIA]
        Chat[ChatSimulator Panel]
        Arena1[Arena 1]
        Arena2[Arena 2]
        Collisions[Collision + Scoring + Effects]
    end

    subgraph Entities
        P1[Player 1]
        P2[Player 2 / AIPlayer]
        Snacks[FallingSnack list]
    end

    subgraph Services
        EB2[EventBus]
        Audio2[AudioManager]
        Twitch2[TwitchChatManager]
    end

    Input --> Rounds
    Input --> Vote
    Vote --> Chat
    Twitch2 --> Input

    Rounds --> Arena1
    Rounds --> Arena2
    Arena1 --> Snacks
    Arena2 --> Snacks

    P1 --> Collisions
    P2 --> Collisions
    Snacks --> Collisions

    Collisions --> EB2
    EB2 --> Audio2
    Collisions --> P1
    Collisions --> P2
```

## 5) Gameplay Round & Crowd Chaos Flow

```mermaid
flowchart TD
    Enter[on_enter] --> Setup[Setup arenas, players, voting, music]
    Setup --> Intro[Storm intro sequence]
    Intro --> Countdown[3..2..1 countdown]
    Countdown --> WalkIn[Character walk-in animation]
    WalkIn --> RoundStart[Round active]

    RoundStart --> Tick[Update timer, players, AI, arenas, collisions]
    Tick --> ChaosCheck{elapsed >= 40s?}
    ChaosCheck -- No --> Tick
    ChaosCheck -- Yes --> ChaosCountdown[Crowd Chaos countdown]
    ChaosCountdown --> ChaosLive[Activate single vote window]
    ChaosLive --> VoteResult{Winner}

    VoteResult -->|ACTION| ActionFX[extend / yank leash]
    VoteResult -->|TREAT| TreatFX[force snack lightning drop]
    VoteResult -->|TRIVIA| TriviaFX[correct => speed boost]

    ActionFX --> Tick
    TreatFX --> Tick
    TriviaFX --> Tick

    Tick --> TimeUp{round_timer <= 0?}
    TimeUp -- No --> Tick
    TimeUp -- Yes --> EndRound[Compute round winner]

    EndRound --> MatchDone{wins reached or rounds finished?}
    MatchDone -- No --> Countdown
    MatchDone -- Yes --> GameOver[change_state]
```

## 6) Event Bus + Audio Event Flow

```mermaid
sequenceDiagram
    participant Screen as Gameplay/Settings/Menu
    participant EB as EventBus
    participant AM as AudioManager
    participant Mixer as pygame.mixer

    Screen->>EB: emit(PLAY_SOUND, payload)
    Screen->>EB: emit(SNACK_COLLECTED, snack_id)
    Screen->>EB: emit(SETTINGS_CHANGED)

    EB-->>AM: _on_play_sound
    EB-->>AM: _on_snack_collected
    EB-->>AM: _on_settings_changed

    AM->>Mixer: Sound.play() / set_volume()
```

## 7) Twitch Voting Integration

```mermaid
sequenceDiagram
    participant TW as Twitch Chat User
    participant Bot as twitchio Bot (thread)
    participant PG as pygame event queue
    participant GP as GameplayScreen
    participant VS as VotingSystem
    participant CS as ChatSimulator

    TW->>Bot: !extend / !yank / !option
    Bot->>PG: post(TWITCH_VOTE_EVENT)
    GP->>PG: read event in handle_event()
    GP->>VS: add_vote(vote_type, voter_id)
    GP->>CS: add_message(voter, !vote)
    VS-->>GP: winner when voting window closes
    GP->>GP: apply vote effect
```

## 8) Treat Attack Mode Flow

```mermaid
flowchart TD
    TAEnter[TreatAttack on_enter] --> InitDog[CatcherDog + TreatSpawner]
    InitDog --> VoteInit[VotingMeter + vote timers]
    VoteInit --> Intro2[Storm intro]
    Intro2 --> Loop2[update loop]

    Loop2 --> Spawn[TreatSpawner may spawn FallingTreat]
    Loop2 --> DogMove[Dog movement + leash state]
    Loop2 --> Catch{collision?}
    Catch -- Yes --> Score[score += point_value, trigger eat, emit SNACK_COLLECTED]
    Catch -- No --> Keep[continue]

    Loop2 --> VoteTick[vote window / cooldown]
    VoteTick --> VoteApply{winner}
    VoteApply -->|extend| LeashEx[dog.extend_leash]
    VoteApply -->|yank| LeashYank[dog.yank_leash]

    Loop2 --> TimeEnd{time_remaining <= 0}
    TimeEnd -- No --> Loop2
    TimeEnd -- Yes --> Done[Game over state in mode]
```

## 9) Avatar Generation Pipeline (Custom Character)

```mermaid
flowchart TD
    Upload[UploadAvatarScreen] --> Input[Dog name + photo + API key]
    Input --> Start[AvatarGenerator.generate_avatar_async]

    Start --> Describe[OpenRouter vision: describe dog]
    Describe --> GenProfile[Generate profile image]
    GenProfile --> GenRun[Generate run sheet]
    GenRun --> GenEat[Generate eat sheet]
    GenEat --> GenWalk[Generate walk sheet]
    GenWalk --> GenBoost[Generate boost sprite]

    GenProfile --> BG1[ensure_transparency -> rembg API]
    GenRun --> BG2[ensure_transparency -> rembg API]
    GenEat --> BG3[ensure_transparency -> rembg API]
    GenWalk --> BG4[ensure_transparency -> rembg API]
    GenBoost --> BG5[ensure_transparency -> rembg API]

    BG1 --> Save[Save assets to Profile / Sprite sheets / custom_avatars]
    BG2 --> Save
    BG3 --> Save
    BG4 --> Save
    BG5 --> Save

    Save --> Register[Append character in config/characters.json]
    Register --> Reload[Config reload + SpriteSheetLoader custom mapping]
    Reload --> Back[Return to Character Select]
```

## 10) Configuration Ownership Map

```mermaid
flowchart LR
    CFGM[ConfigManager]

    GS[game_settings.json]
    CH[characters.json]
    SN[snacks.json]
    LV[levels.json]
    AI[ai_difficulty.json]
    AU[audio_settings.json]
    CT[controls.json]
    TA[treat_attack_settings.json]
    TW[twitch_config.json]
    PV[powerup_visuals.json]

    CFGM --> GS
    CFGM --> CH
    CFGM --> SN
    CFGM --> LV
    CFGM --> AI
    CFGM --> AU
    CFGM --> CT
    CFGM --> TA
    CFGM --> TW
    CFGM --> PV

    GS --> GameLoop[Game window/fps]
    CH --> ScreensChars[CharacterSelect + Sprite loading]
    SN --> GameplaySnacks[Gameplay snack spawn/effects]
    LV --> GameplayLevels[Round settings + pools]
    AI --> AIPlayerCfg[AI behavior]
    AU --> AudioCfg[AudioManager]
    CT --> ControlsCfg[Input mapping reference]
    TA --> TreatAttackCfg[Treat Attack mode]
    TW --> TwitchCfg[Twitch connector]
    PV --> VFXCfg[PowerUp visual effects]
```

## Notes

- Main orchestration starts in `main.py` and `src/game.py`.
- Cross-system communication is event-driven through `EventBus`.
- Screen navigation is centralized via `StateMachine` and `GameState`.
- Gameplay and Treat Attack share core ideas (collect, score, vote) but use separate entity pipelines.
- Avatar generation is asynchronous and integrates external AI image generation + background removal before hot-registering custom characters.
