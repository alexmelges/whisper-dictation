"""Main menu bar application for Whisper Dictation."""

import asyncio
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import rumps

from .audio_recorder import AudioRecorder
from .config import Config, ConfigManager
from .constants import APP_NAME, Language
from .hotkey_manager import HotkeyManager
from .output_handler import OutputHandler
from .permission_checker import (
    PermissionStatus,
    check_accessibility_permission,
    request_accessibility_permission,
)
from .transcriber import Transcriber, TranscriptionError

logger = logging.getLogger(__name__)

# Maximum display length for recent transcriptions in menu
MAX_RECENT_DISPLAY_LENGTH = 50

# Get the resources directory path
# Handle both development and bundled app contexts
def _get_resources_dir() -> Path:
    """Get the resources directory, handling both dev and bundled app."""
    # Check if running as a bundled py2app application
    if hasattr(sys, '_MEIPASS'):  # PyInstaller
        return Path(sys._MEIPASS) / "resources"

    # For py2app, check if we're in a .app bundle
    app_path = Path(__file__).resolve()
    if ".app/Contents/Resources" in str(app_path):
        # We're in a bundled app - resources are at Contents/Resources/resources
        parts = str(app_path).split(".app/Contents/Resources")
        return Path(parts[0] + ".app/Contents/Resources/resources")

    # Development mode - resources relative to src/
    return Path(__file__).parent.parent / "resources"

_RESOURCES_DIR = _get_resources_dir()


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

        # Lock for thread-safe icon updates
        self._icon_lock = threading.Lock()
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
        self._recorder = AudioRecorder(on_max_duration=self._on_max_duration)
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

    def _set_icon_safe(self, icon_path: str) -> None:
        """Set the menu bar icon in a thread-safe manner.

        Args:
            icon_path: Path to the icon file.
        """
        with self._icon_lock:
            self.icon = icon_path

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

        # Double-check accessibility permission
        if check_accessibility_permission() == PermissionStatus.DENIED:
            logger.warning("Recording attempted but accessibility denied")
            self._output.show_notification(
                "Permission Required",
                "Enable Accessibility in System Settings for hotkeys to work.",
            )
            request_accessibility_permission()
            return

        self._set_icon_safe(self.ICON_RECORDING)

        try:
            self._recorder.start_recording()
        except OSError as e:
            logger.error("Failed to start recording: %s", e)
            self._set_icon_safe(self.ICON_IDLE)
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
            self._set_icon_safe(self.ICON_IDLE)
            return

        # Check if we have a transcriber
        if self._transcriber is None:
            logger.error("No transcriber available (missing API key)")
            self._set_icon_safe(self.ICON_IDLE)
            audio_path.unlink(missing_ok=True)
            self._output.show_notification(
                "API Key Missing",
                "Please set OPENAI_API_KEY environment variable.",
            )
            return

        # Update icon and start transcription in background
        self._set_icon_safe(self.ICON_PROCESSING)
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
        self._set_icon_safe(self.ICON_IDLE)
        self._output.show_notification("Cancelled", "Recording cancelled")

    def _on_max_duration(self) -> None:
        """Handle max recording duration reached (auto-stop).

        Called from timer thread when recording exceeds MAX_RECORDING_DURATION.
        """
        logger.warning("Max recording duration reached, auto-stopping")

        # Stop the recording and process it
        audio_path = self._recorder.stop_recording()

        if audio_path is None:
            self._set_icon_safe(self.ICON_IDLE)
            return

        # Check if we have a transcriber
        if self._transcriber is None:
            logger.error("No transcriber available (missing API key)")
            self._set_icon_safe(self.ICON_IDLE)
            audio_path.unlink(missing_ok=True)
            self._output.show_notification(
                "API Key Missing",
                "Please set OPENAI_API_KEY environment variable.",
            )
            return

        # Notify user about auto-stop
        self._output.show_notification(
            "Auto-stopped",
            "Recording reached max duration, transcribing...",
        )

        # Update icon and start transcription in background
        self._set_icon_safe(self.ICON_PROCESSING)
        thread = threading.Thread(
            target=self._run_transcription,
            args=(audio_path,),
            daemon=True,
        )
        thread.start()

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
            # Note: audio file cleanup is handled by transcriber's finally block

        except Exception as e:
            # Log full error for debugging, but show sanitized message to user
            logger.error("Unexpected error during transcription: %s", e, exc_info=True)
            self._output.show_notification(
                "Error", "An unexpected error occurred. Please try again."
            )
            # Note: audio file cleanup is handled by transcriber's finally block

        finally:
            self._set_icon_safe(self.ICON_IDLE)

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

        # Actually install/uninstall the login item
        if self._config.start_at_login:
            self._install_login_item()
        else:
            self._uninstall_login_item()

    def _get_login_item_plist_path(self) -> Path:
        """Get the path to the login item plist file."""
        return Path.home() / "Library" / "LaunchAgents" / "com.whisper.dictation.plist"

    def _install_login_item(self) -> None:
        """Install the LaunchAgent for auto-start at login.

        Creates a plist file that references the launcher script,
        which will source shell profile for API key.
        """
        plist_path = self._get_login_item_plist_path()
        script_dir = Path(__file__).parent.parent.resolve()
        launcher_script = script_dir / ".whisper-launcher.sh"

        # Create the launcher script if it doesn't exist
        if not launcher_script.exists():
            self._create_launcher_script(launcher_script, script_dir)

        # Create LaunchAgents directory if needed
        plist_path.parent.mkdir(parents=True, exist_ok=True)

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.whisper.dictation</string>
    <key>ProgramArguments</key>
    <array>
        <string>{launcher_script}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{script_dir}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>{Path.home()}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{Path.home()}/Library/Logs/WhisperDictation.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/Library/Logs/WhisperDictation.log</string>
</dict>
</plist>
"""
        try:
            plist_path.write_text(plist_content)
            logger.info("Login item installed at %s", plist_path)
            self._output.show_notification(
                "Start at Login Enabled",
                "App will start automatically on login.",
            )
        except OSError as e:
            logger.error("Failed to install login item: %s", e)
            self._output.show_notification(
                "Error",
                "Failed to enable start at login.",
            )

    def _create_launcher_script(self, launcher_path: Path, script_dir: Path) -> None:
        """Create the launcher script that sources shell profile."""
        launcher_content = f"""#!/bin/bash
# Whisper Dictation Launcher
# This script sources shell profile to get OPENAI_API_KEY, then runs the app.

# Source shell profile to get environment variables
if [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc" 2>/dev/null || true
elif [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc" 2>/dev/null || true
elif [ -f "$HOME/.bash_profile" ]; then
    source "$HOME/.bash_profile" 2>/dev/null || true
fi

# Also check for .env file in the script directory
SCRIPT_DIR="{script_dir}"
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs) 2>/dev/null || true
fi

# Verify API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: OPENAI_API_KEY not found in shell profile or .env file" >&2
    echo "Please add to ~/.zshrc or ~/.bashrc:" >&2
    echo "  export OPENAI_API_KEY='your-api-key-here'" >&2
    exit 1
fi

# Run the app
cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/venv/bin/python" -m src.main
"""
        try:
            launcher_path.write_text(launcher_content)
            launcher_path.chmod(0o755)
            logger.info("Created launcher script at %s", launcher_path)
        except OSError as e:
            logger.error("Failed to create launcher script: %s", e)

    def _uninstall_login_item(self) -> None:
        """Uninstall the LaunchAgent for auto-start at login."""
        plist_path = self._get_login_item_plist_path()

        # First unload if currently loaded
        try:
            subprocess.run(
                ["launchctl", "unload", str(plist_path)],
                capture_output=True,
                check=False,
            )
        except Exception as e:
            logger.debug("launchctl unload failed (may not be loaded): %s", e)

        # Remove the plist file
        try:
            if plist_path.exists():
                plist_path.unlink()
                logger.info("Login item removed from %s", plist_path)
            self._output.show_notification(
                "Start at Login Disabled",
                "App will no longer start automatically.",
            )
        except OSError as e:
            logger.error("Failed to remove login item: %s", e)
            self._output.show_notification(
                "Error",
                "Failed to disable start at login.",
            )

    def _quit_app(self, sender: rumps.MenuItem) -> None:
        """Quit the application gracefully."""
        logger.info("Quitting application")
        self._cleanup()
        rumps.quit_application()

    def _cleanup(self) -> None:
        """Clean up resources before shutdown.

        Stops the hotkey listener, cancels any in-progress recording,
        and cleans up other resources.
        """
        logger.debug("Cleaning up resources")
        try:
            if self._hotkey_manager.is_listening:
                self._hotkey_manager.stop_listening()
            if self._recorder.is_recording:
                self._recorder.cancel_recording()
            self._output.cleanup()
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
    """Run the Whisper Dictation application.

    Note: Logging should be configured by main.py before calling this.
    """
    logger.info("Starting %s", APP_NAME)
    _validate_icons()
    app = WhisperDictationApp()
    app.run()


if __name__ == "__main__":
    run()
