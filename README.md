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

### 4. Run the App

```bash
python run.py
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

## Building Standalone App

### Option 1: Build and Install (Recommended)

Build, install to Applications, and sign in one step:

```bash
./build.sh install
```

The app will be installed to `/Applications/Whisper Dictation.app` and ready to use.

### Option 2: Build Only

Build without installing:

```bash
./build.sh
```

The app will be created at `dist/Whisper Dictation.app`.

To install manually, you **must** copy and re-sign (copying invalidates the code signature):

```bash
cp -r 'dist/Whisper Dictation.app' /Applications/
codesign --force --deep --sign - '/Applications/Whisper Dictation.app'
```

> **Note**: If you skip the `codesign` step after copying, the app will fail to launch silently due to macOS code signature validation.

### Clean Build

To remove build artifacts:

```bash
./build.sh clean
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

### App doesn't launch (no error)

If the app fails to launch silently after copying to Applications, run:

```bash
codesign --force --deep --sign - '/Applications/Whisper Dictation.app'
```

This re-signs the app after copying, which is required because copying invalidates the code signature.

### "Rate limited"

You've exceeded OpenAI's rate limits. Wait a moment and try again.

## Debug Mode

For verbose logging:

```bash
export WHISPER_DICTATION_DEBUG=1
python run.py
```

## License

MIT
