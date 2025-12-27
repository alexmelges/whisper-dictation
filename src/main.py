"""Entry point for Whisper Dictation application."""

import logging
import os
import sys

from src.app import WhisperDictationApp
from src.config import ConfigManager
from src.constants import APP_NAME


def setup_logging() -> None:
    """Configure logging for the application.

    Uses INFO level by default. Set WHISPER_DICTATION_DEBUG=1 for DEBUG level.
    """
    log_level = logging.DEBUG if os.environ.get("WHISPER_DICTATION_DEBUG") else logging.INFO
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
