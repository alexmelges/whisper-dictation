# Whisper Dictation

A macOS menu bar app for speech-to-text using OpenAI's Whisper API.

## Features

- **Hold-to-record**: Hold Option+Space to record, release to transcribe
- **Clipboard integration**: Transcriptions are automatically copied to clipboard
- **Direct paste**: Optional automatic paste after transcription
- **Multi-language**: Supports English and Portuguese
- **Recent transcriptions**: Quick access to recent transcriptions from menu bar
- **Menu bar only**: Runs quietly in the menu bar without a Dock icon

## Requirements

- macOS 10.15 (Catalina) or later
- Python 3.11+
- OpenAI API key
- PortAudio library

## Installation

### 1. Install PortAudio

```bash
brew install portaudio
```

### 2. Clone and Set Up

```bash
git clone https://github.com/alexmelges/whisper-dictation.git
cd whisper-dictation

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set API Key

```bash
export OPENAI_API_KEY='your-api-key-here'
```

You can get an API key from: https://platform.openai.com/api-keys

### 4. Start the App

Start as a background service (recommended):

```bash
./whisper-ctl.sh start
```

The menu bar icon will appear. The app auto-starts at login and runs in the background.

**Other commands:**
```bash
./whisper-ctl.sh stop     # Stop the service
./whisper-ctl.sh restart  # Restart the service
./whisper-ctl.sh status   # Check if running
./whisper-ctl.sh logs     # View log output
./whisper-ctl.sh run      # Run interactively (for debugging)
```

## Usage

### Recording

- **Option+Space** (hold): Start recording
- **Release**: Stop recording and transcribe
- **ESC**: Cancel recording

### Menu Bar Options

- **Language**: Switch between English and Portuguese
- **Paste directly**: Toggle automatic paste after transcription
- **Start at login**: Toggle auto-start (placeholder)
- **Recent**: View and copy recent transcriptions
- **Quit**: Exit the application

## Alternative: Standalone .app Bundle

> **Note**: The recommended method is `./whisper-ctl.sh start` (see Installation above).
> The standalone app has code signing complexities that may cause launch failures.

To build a standalone macOS .app:

```bash
./build.sh install
```

This builds and installs to `/Applications/Whisper Dictation.app`.

If you prefer to build only (without installing):
```bash
./build.sh
# Then manually copy and re-sign:
cp -r 'dist/Whisper Dictation.app' /Applications/
codesign --force --deep --sign - '/Applications/Whisper Dictation.app'
```

## Configuration

Settings are stored in `~/Library/Application Support/Whisper Dictation/config.json`:

- `language`: "ENGLISH" or "PORTUGUESE"
- `paste_directly`: true/false
- `start_at_login`: true/false
- `recent_transcriptions`: list of recent texts

## Permissions

The app requires:

- **Microphone access**: For recording speech
- **Accessibility**: For global hotkeys and paste simulation

Grant these in System Settings > Privacy & Security.

## Troubleshooting

### "Microphone access denied"

Go to System Settings > Privacy & Security > Microphone and enable access for Terminal or the app.

### "API key not configured"

Set the `OPENAI_API_KEY` environment variable before running the app.

### Hotkeys not working

Go to System Settings > Privacy & Security > Accessibility and enable access for Terminal or the app.

### App doesn't start

Check the status and logs:

```bash
./whisper-ctl.sh status
./whisper-ctl.sh logs
```

If using the standalone .app and it fails to launch, re-sign it:
```bash
codesign --force --deep --sign - '/Applications/Whisper Dictation.app'
```

### "Rate limited"

You've exceeded OpenAI's rate limits. Wait a moment and try again.

## Debug Mode

For verbose logging, run interactively:

```bash
export WHISPER_DICTATION_DEBUG=1
./whisper-ctl.sh run
```

Or check the log file:
```bash
./whisper-ctl.sh logs
```

## License

MIT
