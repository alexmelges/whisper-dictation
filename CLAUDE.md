# Whisper Dictation App

A macOS menu bar application for speech-to-text using OpenAI's Whisper API.

## Project Overview

This is a lightweight dictation tool that sits in the macOS menu bar. Users hold a hotkey to record speech, release to transcribe via OpenAI Whisper API, and the text is copied to clipboard (with optional direct paste).

## Target User

- Native Brazilian Portuguese speaker
- Uses both English and Portuguese
- Prefers OpenAI Whisper API over local models for better accent handling
- macOS user (Sonoma/Ventura)

## Technical Stack

- Python 3.11+
- rumps: Menu bar app framework
- pyaudio: Audio recording
- openai: Whisper API client
- pynput: Global hotkey detection
- pyperclip: Clipboard management
- py2app: macOS app packaging

## Architecture
```
src/
├── main.py              # Entry point
├── app.py               # Menu bar app (rumps)
├── audio_recorder.py    # Microphone capture
├── transcriber.py       # OpenAI Whisper API
├── hotkey_manager.py    # Global hotkey listener
├── output_handler.py    # Clipboard/paste/notification
├── config.py            # Settings management
└── constants.py         # App constants
```

## Core Behaviors

### Recording Flow
1. User presses and holds hotkey (default: Option+Space)
2. App state changes to RECORDING, menu bar icon updates
3. Audio is captured to memory buffer
4. User releases hotkey
5. App state changes to PROCESSING
6. Audio saved to temp WAV file
7. Sent to Whisper API with language parameter
8. Response copied to clipboard
9. Notification shown with transcribed text
10. Temp file deleted
11. App state returns to IDLE

### States
- IDLE: Default, waiting for input
- RECORDING: Capturing audio
- PROCESSING: API call in progress
- ERROR: Transient, shows error then returns to IDLE

### Menu Bar Structure
```
[Icon] ▼
├── Language: English ✓
├── Language: Portuguese
├── ──────────────
├── ☐ Paste directly
├── ☐ Start at login
├── ──────────────
├── Recent:
│   ├── "Last transcription..."
│   └── "Previous one..."
├── ──────────────
└── Quit
```

## Code Style Rules

1. Use type hints for all function parameters and returns
2. Use dataclasses for structured data
3. Use Enum for states and constants
4. Async/await for API calls only
5. Docstrings for all public methods (Google style)
6. Keep functions under 30 lines
7. No global mutable state
8. Handle all exceptions explicitly, log errors
9. Use pathlib.Path for file operations
10. Use logging module, not print statements

## Error Handling

- Network errors: Show notification "Connection failed. Check your internet."
- API key missing: Show notification "OpenAI API key not configured." and open settings
- API rate limit: Show notification "Rate limited. Please wait."
- Microphone permission denied: Show notification with instructions to enable in System Settings
- Recording too short (<0.5s): Ignore, return to IDLE
- Recording too long (>120s): Auto-stop, transcribe what was captured

## Audio Configuration

- Sample rate: 16000 Hz (Whisper optimal)
- Channels: 1 (mono)
- Format: 16-bit signed integer
- Temp file format: WAV

## Security

- API key stored in environment variable OPENAI_API_KEY
- Never log API key
- Never persist audio files
- Delete temp files immediately after use

## Testing Approach

- Unit tests for each module
- Mock API calls in tests
- Test error conditions explicitly
- No integration tests required initially

## Files to Create (in order)

1. src/constants.py - Enums and constants
2. src/config.py - Configuration management
3. src/audio_recorder.py - Recording logic
4. src/transcriber.py - API client
5. src/output_handler.py - Clipboard and notifications
6. src/hotkey_manager.py - Hotkey detection
7. src/app.py - Menu bar app
8. src/main.py - Entry point
9. setup.py - py2app configuration

## Dependencies Note

pyaudio requires PortAudio system library:
```bash
brew install portaudio
```

## Permissions Required

The app will need these macOS permissions:
- Microphone access (for recording)
- Accessibility (for global hotkeys and paste simulation)

These will be requested on first use.

## Do NOT

- Do not use threading directly; let pyaudio handle audio threads
- Do not save audio files permanently
- Do not use synchronous API calls in the main thread
- Do not hardcode the API key
- Do not use root logger; create named loggers per module
- Do not catch bare `except:` without logging
- Do not use mutable default arguments
```
