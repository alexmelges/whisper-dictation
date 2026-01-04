"""Output handling: clipboard, paste simulation, and notifications."""

import logging
import threading
import time

import pyperclip
import rumps
from pynput.keyboard import Controller, Key

from .config import ConfigManager

logger = logging.getLogger(__name__)

# Maximum length for notification messages
MAX_NOTIFICATION_LENGTH = 100

# Clipboard auto-clear timeout in seconds (security feature)
CLIPBOARD_CLEAR_TIMEOUT = 60

# Delay before paste to ensure correct window focus (ms)
PASTE_DELAY_MS = 200


class OutputHandler:
    """Handles output operations: clipboard, paste, and notifications.

    Manages copying text to clipboard, simulating paste keystrokes,
    showing macOS notifications, and tracking recent transcriptions.
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize the output handler.

        Args:
            config_manager: ConfigManager instance for saving recent transcriptions.
        """
        logger.debug("Initializing OutputHandler")
        self._config_manager = config_manager
        self._keyboard = Controller()
        self._clipboard_timer: threading.Timer | None = None
        self._clipboard_lock = threading.Lock()
        logger.info("OutputHandler initialized")

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to the system clipboard.

        Automatically clears clipboard after CLIPBOARD_CLEAR_TIMEOUT seconds
        for security.

        Args:
            text: The text to copy to clipboard.
        """
        logger.debug("Copying %d characters to clipboard", len(text))
        try:
            pyperclip.copy(text)
            logger.info("Text copied to clipboard")
            self._schedule_clipboard_clear()
        except Exception as e:
            logger.error("Failed to copy to clipboard: %s", e)
            raise

    def _schedule_clipboard_clear(self) -> None:
        """Schedule automatic clipboard clearing after timeout."""
        with self._clipboard_lock:
            # Cancel any existing timer
            if self._clipboard_timer is not None:
                self._clipboard_timer.cancel()

            # Schedule new clear
            self._clipboard_timer = threading.Timer(
                CLIPBOARD_CLEAR_TIMEOUT,
                self._clear_clipboard,
            )
            self._clipboard_timer.daemon = True
            self._clipboard_timer.start()
            logger.debug(
                "Clipboard will be cleared in %d seconds", CLIPBOARD_CLEAR_TIMEOUT
            )

    def _clear_clipboard(self) -> None:
        """Clear the clipboard contents."""
        try:
            pyperclip.copy("")
            logger.info("Clipboard cleared for security")
        except Exception as e:
            logger.warning("Failed to clear clipboard: %s", e)

    def paste_directly(self, text: str) -> None:
        """Copy text to clipboard and simulate Cmd+V to paste.

        First copies the text to clipboard, then simulates the paste
        keystroke. Requires macOS Accessibility permission.

        Args:
            text: The text to paste.

        Raises:
            PermissionError: If Accessibility permission is not granted.
        """
        logger.debug("Pasting %d characters directly", len(text))

        # First copy to clipboard
        self.copy_to_clipboard(text)

        # Delay to ensure clipboard is ready and correct window has focus
        # Longer delay reduces risk of pasting to wrong application
        time.sleep(PASTE_DELAY_MS / 1000)

        try:
            # Simulate Cmd+V
            self._keyboard.press(Key.cmd)
            self._keyboard.press("v")
            self._keyboard.release("v")
            self._keyboard.release(Key.cmd)
            logger.info("Paste keystroke simulated")
        except Exception as e:
            logger.error("Failed to simulate paste: %s", e)
            raise PermissionError(
                "Cannot simulate paste. Please enable Accessibility permission "
                "in System Settings > Privacy & Security > Accessibility."
            ) from e

    def show_notification(self, title: str, message: str) -> None:
        """Show a macOS notification.

        Truncates the message to MAX_NOTIFICATION_LENGTH characters
        if it exceeds that length.

        Args:
            title: The notification title.
            message: The notification message body.
        """
        # Truncate message if too long
        if len(message) > MAX_NOTIFICATION_LENGTH:
            truncated_message = message[: MAX_NOTIFICATION_LENGTH - 3] + "..."
            logger.debug(
                "Truncated notification from %d to %d chars",
                len(message),
                len(truncated_message),
            )
        else:
            truncated_message = message

        logger.debug("Showing notification: %s", title)
        try:
            rumps.notification(
                title=title,
                subtitle="",
                message=truncated_message,
            )
            logger.info("Notification shown: %s", title)
        except Exception as e:
            logger.error("Failed to show notification: %s", e)

    def add_recent_transcription(self, text: str) -> None:
        """Add a transcription to the recent transcriptions list.

        Loads the current config, adds the transcription, and saves.

        Args:
            text: The transcription text to add.
        """
        if not text:
            return

        logger.debug("Adding transcription to recent list")
        try:
            config = self._config_manager.load()
            config.add_transcription(text)
            self._config_manager.save(config)
            logger.info("Transcription added to recent list")
        except Exception as e:
            logger.error("Failed to save recent transcription: %s", e)

    def cleanup(self) -> None:
        """Clean up resources, cancelling any pending timers.

        Should be called when the application is shutting down.
        """
        logger.debug("Cleaning up OutputHandler")
        with self._clipboard_lock:
            if self._clipboard_timer is not None:
                self._clipboard_timer.cancel()
                self._clipboard_timer = None
                logger.debug("Clipboard timer cancelled")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config_manager = ConfigManager()
    handler = OutputHandler(config_manager)

    # Test clipboard
    handler.copy_to_clipboard("Hello World")
    print("Copied 'Hello World' to clipboard")

    # Test notification
    handler.show_notification("Test", "This is a test notification from Whisper Dictation")
    print("Notification shown")
