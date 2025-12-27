"""Constants and enums for the Whisper Dictation app."""

from enum import Enum
from typing import Union

from pynput.keyboard import Key, KeyCode


class AppState(Enum):
    """Application states for the dictation app."""

    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"


class Language(Enum):
    """Supported languages for transcription."""

    ENGLISH = ("en", "English")
    PORTUGUESE = ("pt", "Portuguese")

    def __init__(self, code: str, display_name: str) -> None:
        """Initialize language with code and display name.

        Args:
            code: ISO language code for Whisper API.
            display_name: Human-readable language name.
        """
        self.code = code
        self.display_name = display_name


# Audio configuration (Whisper optimal settings)
SAMPLE_RATE: int = 16000
CHANNELS: int = 1
AUDIO_FORMAT: int = 8  # pyaudio.paInt16 = 8
CHUNK_SIZE: int = 1024
MIN_RECORDING_DURATION: float = 0.5
MAX_RECORDING_DURATION: float = 120.0

# App metadata
APP_NAME: str = "Whisper Dictation"
APP_VERSION: str = "1.0.0"
APP_BUNDLE_ID: str = "com.whisper.dictation"

# Default hotkey (Option + Space)
DEFAULT_HOTKEY: frozenset[Union[Key, KeyCode]] = frozenset({Key.alt, Key.space})

# Config settings
CONFIG_FILENAME: str = "config.json"
MAX_RECENT_TRANSCRIPTIONS: int = 5
