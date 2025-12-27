"""Main menu bar application for Whisper Dictation."""

import asyncio
import logging
import threading
from pathlib import Path

import rumps

from .audio_recorder import AudioRecorder
from .config import Config, ConfigManager
from .constants import APP_NAME, Language
from .hotkey_manager import HotkeyManager
from .output_handler import OutputHandler
from .transcriber import Transcriber, TranscriptionError

logger = logging.getLogger(__name__)

# Maximum display length for recent transcriptions in menu
MAX_RECENT_DISPLAY_LENGTH = 50

# Get the resources directory path
_RESOURCES_DIR = Path(__file__).parent.parent / "resources"


def _get_icon_path(name: str) -> str:
    """Get the full path to an icon file.

    Args:
        name: Icon filename (e.g., 'icon_idle.png').

    Returns:
        Absolute path to the icon file as a string.
    """
    return str(_RESOURCES_DIR / name)


class WhisperDictationApp(rumps.App):
    """Main menu bar application for Whisper Dictation.

    Integrates audio recording, transcription, and output handling
    into a macOS menu bar application.
    """

    # Icon paths for different states
    ICON_IDLE = _get_icon_path("icon_idle.png")
    ICON_RECORDING = _get_icon_path("icon_recording.png")
    ICON_PROCESSING = _get_icon_path("icon_processing.png")

    def __init__(self) -> None:
        """Initialize the application with all components."""
        logger.debug("Initializing WhisperDictationApp")
        super().__init__(name=APP_NAME, icon=self.ICON_IDLE, quit_button=None)
        # Hide the title, show only icon
        self.title = None

        # Load configuration
        self._config_manager = ConfigManager()
        self._config = self._config_manager.load()

        # Initialize transcriber (may be None if no API key)
        api_key = ConfigManager.get_api_key()
        if api_key:
            self._transcriber: Transcriber | None = Transcriber(api_key)
        else:
            logger.warning("No OpenAI API key found")
            self._transcriber = None

        # Initialize components
        self._recorder = AudioRecorder()
        self._output = OutputHandler(self._config_manager)
        self._hotkey_manager = HotkeyManager(
            on_record_start=self._on_record_start,
            on_record_stop=self._on_record_stop,
            on_cancel=self._on_cancel,
            hotkey=self._config.hotkey,
        )

        # Build menu and start listening
        self._build_menu()
        self._update_menu_state()
        self._hotkey_manager.start_listening()

        logger.info("WhisperDictationApp initialized")

    def _build_menu(self) -> None:
        """Build the application menu structure.

        Creates the menu bar dropdown with language selection,
        settings toggles, recent transcriptions, and quit option.
        """
        # Create Recent submenu with initial placeholder
        recent_menu = rumps.MenuItem("Recent:")
        recent_menu.add(rumps.MenuItem("(none)", callback=None))

        self.menu = [
            rumps.MenuItem("Language: English", callback=self._toggle_english),
            rumps.MenuItem("Language: Portuguese", callback=self._toggle_portuguese),
            None,  # Separator
            rumps.MenuItem("Paste directly", callback=self._toggle_paste_directly),
            rumps.MenuItem("Start at login", callback=self._toggle_start_at_login),
            None,  # Separator
            recent_menu,
            None,  # Separator
            rumps.MenuItem("Quit", callback=self._quit_app),
        ]
        self._update_recent_menu()

    def _update_menu_state(self) -> None:
        """Update menu item states to reflect current configuration.

        Sets checkmarks on language options (radio-button style) and
        toggle settings based on the current Config values.
        """
        # Language checkmarks (radio-button style)
        self.menu["Language: English"].state = (
            self._config.language == Language.ENGLISH
        )
        self.menu["Language: Portuguese"].state = (
            self._config.language == Language.PORTUGUESE
        )

        # Toggle checkmarks
        self.menu["Paste directly"].state = self._config.paste_directly
        self.menu["Start at login"].state = self._config.start_at_login

    def _update_recent_menu(self) -> None:
        """Update the recent transcriptions submenu.

        Clears and rebuilds the Recent: submenu with the latest
        transcriptions from config. Each item copies its text
        to clipboard when clicked.
        """
        recent_item = self.menu["Recent:"]

        # Clear existing items
        recent_item.clear()

        if not self._config.recent_transcriptions:
            empty_item = rumps.MenuItem("(none)", callback=None)
            recent_item.add(empty_item)
            return

        for text in self._config.recent_transcriptions:
            # Truncate for display
            if len(text) > MAX_RECENT_DISPLAY_LENGTH:
                display = text[:MAX_RECENT_DISPLAY_LENGTH - 3] + "..."
            else:
                display = text

            # Replace newlines with spaces for display
            display = display.replace("\n", " ")

            item = rumps.MenuItem(display, callback=self._copy_recent)
            # Store full text as attribute for copying
            item._full_text = text
            recent_item.add(item)

    def _copy_recent(self, sender: rumps.MenuItem) -> None:
        """Copy a recent transcription to clipboard when clicked.

        Args:
            sender: The menu item that was clicked.
        """
        full_text = getattr(sender, "_full_text", sender.title)
        self._output.copy_to_clipboard(full_text)
        self._output.show_notification("Copied", full_text)

    def _on_record_start(self) -> None:
        """Handle recording start (hotkey pressed)."""
        logger.info("Recording started via hotkey")
        self.icon = self.ICON_RECORDING

        try:
            self._recorder.start_recording()
        except OSError as e:
            logger.error("Failed to start recording: %s", e)
            self.icon = self.ICON_IDLE
            self._output.show_notification(
                "Microphone Error",
                "Please enable microphone access in System Settings.",
            )

    def _on_record_stop(self) -> None:
        """Handle recording stop (hotkey released)."""
        logger.info("Recording stopped via hotkey")

        audio_path = self._recorder.stop_recording()

        if audio_path is None:
            # Recording too short
            logger.info("Recording was too short, ignoring")
            self.icon = self.ICON_IDLE
            return

        # Check if we have a transcriber
        if self._transcriber is None:
            logger.error("No transcriber available (missing API key)")
            self.icon = self.ICON_IDLE
            audio_path.unlink(missing_ok=True)
            self._output.show_notification(
                "API Key Missing",
                "Please set OPENAI_API_KEY environment variable.",
            )
            return

        # Update icon and start transcription in background
        self.icon = self.ICON_PROCESSING
        thread = threading.Thread(
            target=self._run_transcription,
            args=(audio_path,),
            daemon=True,
        )
        thread.start()

    def _on_cancel(self) -> None:
        """Handle recording cancellation (ESC pressed)."""
        logger.info("Recording cancelled via ESC")
        self._recorder.cancel_recording()
        self.icon = self.ICON_IDLE
        self._output.show_notification("Cancelled", "Recording cancelled")

    def _run_transcription(self, audio_path: Path) -> None:
        """Run transcription in a background thread.

        Args:
            audio_path: Path to the audio file to transcribe.
        """
        asyncio.run(self._transcribe_and_output(audio_path))

    async def _transcribe_and_output(self, audio_path: Path) -> None:
        """Transcribe audio and handle output.

        Args:
            audio_path: Path to the audio file to transcribe.
        """
        try:
            # Transcribe
            text = await self._transcriber.transcribe(
                audio_path,
                self._config.language.code,
            )

            # Handle output
            if self._config.paste_directly:
                try:
                    self._output.paste_directly(text)
                except PermissionError as e:
                    logger.warning("Paste failed (no accessibility): %s", e)
                    self._output.copy_to_clipboard(text)
                    self._output.show_notification(
                        "Copied to Clipboard",
                        "Enable Accessibility permission for direct paste.",
                    )
            else:
                self._output.copy_to_clipboard(text)

            # Add to recent and update menu
            self._output.add_recent_transcription(text)
            self._config.add_transcription(text)
            self._update_recent_menu()

            # Show notification
            self._output.show_notification("Transcribed", text)

            logger.info("Transcription complete: %d characters", len(text))

        except TranscriptionError as e:
            logger.error("Transcription failed: %s", e.message)
            self._output.show_notification("Transcription Failed", e.message)
            # Clean up audio file on error
            audio_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error("Unexpected error during transcription: %s", e)
            self._output.show_notification("Error", str(e))
            audio_path.unlink(missing_ok=True)

        finally:
            self.icon = self.ICON_IDLE

    def _toggle_english(self, sender: rumps.MenuItem) -> None:
        """Toggle English language selection."""
        self._config.language = Language.ENGLISH
        self._config_manager.save(self._config)
        self._update_menu_state()
        logger.info("Language changed to English")

    def _toggle_portuguese(self, sender: rumps.MenuItem) -> None:
        """Toggle Portuguese language selection."""
        self._config.language = Language.PORTUGUESE
        self._config_manager.save(self._config)
        self._update_menu_state()
        logger.info("Language changed to Portuguese")

    def _toggle_paste_directly(self, sender: rumps.MenuItem) -> None:
        """Toggle paste directly setting."""
        self._config.paste_directly = not self._config.paste_directly
        self._config_manager.save(self._config)
        self._update_menu_state()
        logger.info("Paste directly: %s", self._config.paste_directly)

    def _toggle_start_at_login(self, sender: rumps.MenuItem) -> None:
        """Toggle start at login setting."""
        self._config.start_at_login = not self._config.start_at_login
        self._config_manager.save(self._config)
        self._update_menu_state()
        logger.info("Start at login: %s", self._config.start_at_login)
        # Note: Actual login item management would require additional implementation

    def _quit_app(self, sender: rumps.MenuItem) -> None:
        """Quit the application gracefully."""
        logger.info("Quitting application")
        self._cleanup()
        rumps.quit_application()

    def _cleanup(self) -> None:
        """Clean up resources before shutdown.

        Stops the hotkey listener and cancels any in-progress recording.
        """
        logger.debug("Cleaning up resources")
        try:
            if self._hotkey_manager.is_listening:
                self._hotkey_manager.stop_listening()
            if self._recorder.is_recording:
                self._recorder.cancel_recording()
        except Exception as e:
            logger.error("Error during cleanup: %s", e)

    def __del__(self) -> None:
        """Destructor to ensure cleanup on garbage collection."""
        self._cleanup()


def _validate_icons() -> None:
    """Validate that all required icon files exist.

    Logs warnings for any missing icons.
    """
    icons = [
        WhisperDictationApp.ICON_IDLE,
        WhisperDictationApp.ICON_RECORDING,
        WhisperDictationApp.ICON_PROCESSING,
    ]
    for icon_path in icons:
        if not Path(icon_path).exists():
            logger.warning("Icon file not found: %s", icon_path)


def run() -> None:
    """Run the Whisper Dictation application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting %s", APP_NAME)
    _validate_icons()
    app = WhisperDictationApp()
    app.run()


if __name__ == "__main__":
    run()
