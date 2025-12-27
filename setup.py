"""py2app build configuration for Whisper Dictation."""

from pathlib import Path

from setuptools import setup

# Application entry point
APP = ["src/main.py"]

# Data files to include in the app bundle
DATA_FILES = [
    (
        "resources",
        [
            "resources/icon_idle.png",
            "resources/icon_recording.png",
            "resources/icon_processing.png",
        ],
    ),
]

# py2app options
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "resources/app_icon.icns",
    "plist": {
        # App identification
        "CFBundleName": "Whisper Dictation",
        "CFBundleDisplayName": "Whisper Dictation",
        "CFBundleIdentifier": "com.whisper.dictation",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        # Menu bar app (no Dock icon)
        "LSUIElement": True,
        # Permission descriptions (shown in system dialogs)
        "NSMicrophoneUsageDescription": (
            "Whisper Dictation needs microphone access to record your speech "
            "for transcription."
        ),
        # Note: This key is not standard but may help with accessibility prompts
        "NSAccessibilityUsageDescription": (
            "Whisper Dictation needs accessibility access for global hotkeys "
            "and automatic paste functionality."
        ),
        # Minimum macOS version
        "LSMinimumSystemVersion": "10.15",
    },
    # Packages to include
    "packages": [
        "rumps",
        "openai",
        "pyaudio",
        "pynput",
        "pyperclip",
        "httpx",
        "httpcore",
        "anyio",
        "certifi",
    ],
    # Additional includes
    "includes": [
        "src",
        "src.app",
        "src.audio_recorder",
        "src.config",
        "src.constants",
        "src.hotkey_manager",
        "src.output_handler",
        "src.transcriber",
    ],
}

# Check if icon file exists, if not skip it
icon_path = Path("resources/app_icon.icns")
if not icon_path.exists():
    print("Warning: app_icon.icns not found, building without custom app icon")
    del OPTIONS["iconfile"]

setup(
    app=APP,
    name="Whisper Dictation",
    version="1.0.0",
    description="A macOS menu bar app for speech-to-text using OpenAI Whisper",
    author="",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
