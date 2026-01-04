"""Entry point for Whisper Dictation application."""

import logging
import os
import sys

from src.app import WhisperDictationApp
from src.config import ConfigManager
from src.constants import APP_NAME
from src.permission_checker import (
    PermissionStatus,
    check_accessibility_permission,
    check_microphone_permission,
    request_accessibility_permission,
)


def setup_logging() -> None:
    """Configure logging for the application.

    Uses INFO level by default. Set WHISPER_DICTATION_DEBUG=1 for DEBUG level.
    Clears any existing handlers to prevent duplicate log entries.
    """
    log_level = logging.DEBUG if os.environ.get("WHISPER_DICTATION_DEBUG") else logging.INFO

    # Clear any existing handlers to prevent duplicates
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def check_api_key() -> bool:
    """Check if OpenAI API key is configured.

    Returns:
        True if API key is set, False otherwise.
    """
    api_key = ConfigManager.get_api_key()
    if not api_key:
        print("=" * 60)
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("=" * 60)
        print()
        print("Please set your OpenAI API key:")
        print()
        print("  export OPENAI_API_KEY='your-api-key-here'")
        print()
        print("You can get an API key from: https://platform.openai.com/api-keys")
        print()
        return False
    return True


def check_permissions(logger: logging.Logger) -> bool:
    """Check required macOS permissions.

    Checks Accessibility and Microphone permissions. If Accessibility
    is not granted, prompts the user and opens System Settings.

    Args:
        logger: Logger instance for output.

    Returns:
        True if critical permissions are granted or user was notified,
        False if the app should not continue.
    """
    # Check Accessibility (critical for hotkeys)
    accessibility = check_accessibility_permission()
    if accessibility == PermissionStatus.DENIED:
        logger.error("Accessibility permission denied - hotkeys will not work")
        print("=" * 60)
        print("ACCESSIBILITY PERMISSION REQUIRED")
        print("=" * 60)
        print()
        print("Whisper Dictation needs Accessibility permission for")
        print("global hotkeys (Option+Space) to work.")
        print()
        print("Please grant access in System Settings:")
        print("  Privacy & Security > Accessibility")
        print()
        print("Opening System Settings...")
        request_accessibility_permission()
        print()
        print("After granting permission, restart the app.")
        print()
        # Don't exit - let the app run so the menu bar icon appears
        # The user can see the app is running and grant permission

    # Check Microphone (needed for recording, but will prompt on first use)
    microphone = check_microphone_permission()
    if microphone == PermissionStatus.DENIED:
        logger.warning("Microphone permission denied - recording will fail")
        print()
        print("WARNING: Microphone permission denied")
        print("Grant access in System Settings > Privacy & Security > Microphone")
        print()

    return True


def main() -> int:
    """Main entry point for the application.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting %s", APP_NAME)

    if not check_api_key():
        return 1

    # Check permissions before starting (shows warnings but continues)
    check_permissions(logger)

    try:
        app = WhisperDictationApp()
        app.run()
        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0

    except Exception as e:
        logger.exception("Fatal error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
