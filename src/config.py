"""Configuration management for the Whisper Dictation app."""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

from pynput.keyboard import Key, KeyCode

from .constants import (
    APP_NAME,
    CONFIG_FILENAME,
    DEFAULT_HOTKEY,
    MAX_RECENT_TRANSCRIPTIONS,
    Language,
)

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration settings.

    Attributes:
        language: The language for transcription.
        paste_directly: Whether to paste text directly after transcription.
        start_at_login: Whether to start the app at system login.
        hotkey: The hotkey combination to trigger recording.
        recent_transcriptions: List of recent transcription texts.
    """

    language: Language = Language.ENGLISH
    paste_directly: bool = False
    start_at_login: bool = False
    hotkey: frozenset[Union[Key, KeyCode]] = field(
        default_factory=lambda: DEFAULT_HOTKEY
    )
    recent_transcriptions: list[str] = field(default_factory=list)

    def add_transcription(self, text: str) -> None:
        """Add a transcription to the recent list.

        Args:
            text: The transcribed text to add.
        """
        if text and text not in self.recent_transcriptions:
            self.recent_transcriptions.insert(0, text)
            self.recent_transcriptions = self.recent_transcriptions[
                :MAX_RECENT_TRANSCRIPTIONS
            ]


class ConfigManager:
    """Manages loading and saving of application configuration."""

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize the configuration manager.

        Args:
            config_path: Optional path to the config file. If None, uses the
                default Application Support directory.
        """
        if config_path is None:
            app_support = Path.home() / "Library" / "Application Support" / APP_NAME
            app_support.mkdir(parents=True, exist_ok=True)
            self._config_path = app_support / CONFIG_FILENAME
        else:
            self._config_path = config_path

        self._config: Config | None = None

    @property
    def config_path(self) -> Path:
        """Return the path to the config file."""
        return self._config_path

    def load(self) -> Config:
        """Load configuration from disk.

        Returns:
            The loaded configuration, or default config if file doesn't exist.
        """
        if not self._config_path.exists():
            logger.info("Config file not found, using defaults")
            self._config = self.create_default()
            return self._config

        try:
            with self._config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._config = self._from_dict(data)
            logger.info("Configuration loaded from %s", self._config_path)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Failed to load config: %s. Using defaults.", e)
            self._config = self.create_default()

        return self._config

    def save(self, config: Config) -> None:
        """Save configuration to disk.

        Args:
            config: The configuration to save.
        """
        self._config = config
        data = self._to_dict(config)

        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with self._config_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Configuration saved to %s", self._config_path)
        except OSError as e:
            logger.error("Failed to save config: %s", e)

    @staticmethod
    def get_api_key() -> str | None:
        """Get the OpenAI API key from environment.

        Returns:
            The API key, or None if not set.
        """
        return os.environ.get("OPENAI_API_KEY")

    @staticmethod
    def create_default() -> Config:
        """Create a default configuration.

        Returns:
            A new Config instance with default values.
        """
        return Config()

    def _to_dict(self, config: Config) -> dict[str, Any]:
        """Convert Config to a JSON-serializable dictionary.

        Args:
            config: The configuration to convert.

        Returns:
            A dictionary representation of the config.
        """
        hotkey_list = []
        for key in config.hotkey:
            if isinstance(key, Key):
                hotkey_list.append({"type": "Key", "value": key.name})
            elif isinstance(key, KeyCode):
                hotkey_list.append(
                    {"type": "KeyCode", "char": key.char, "vk": key.vk}
                )

        return {
            "language": config.language.name,
            "paste_directly": config.paste_directly,
            "start_at_login": config.start_at_login,
            "hotkey": hotkey_list,
            "recent_transcriptions": config.recent_transcriptions,
        }

    def _from_dict(self, data: dict[str, Any]) -> Config:
        """Convert a dictionary to a Config instance.

        Args:
            data: The dictionary to convert.

        Returns:
            A Config instance.
        """
        try:
            language = Language[data.get("language", "ENGLISH")]
        except KeyError:
            logger.warning(
                "Invalid language '%s' in config, using ENGLISH",
                data.get("language"),
            )
            language = Language.ENGLISH

        hotkey_set: set[Union[Key, KeyCode]] = set()
        for key_data in data.get("hotkey", []):
            try:
                if key_data.get("type") == "Key":
                    hotkey_set.add(Key[key_data["value"]])
                elif key_data.get("type") == "KeyCode":
                    hotkey_set.add(
                        KeyCode(char=key_data.get("char"), vk=key_data.get("vk"))
                    )
            except KeyError as e:
                logger.warning("Invalid hotkey data in config: %s", e)

        if not hotkey_set:
            hotkey_set = set(DEFAULT_HOTKEY)

        return Config(
            language=language,
            paste_directly=data.get("paste_directly", False),
            start_at_login=data.get("start_at_login", False),
            hotkey=frozenset(hotkey_set),
            recent_transcriptions=data.get("recent_transcriptions", []),
        )
