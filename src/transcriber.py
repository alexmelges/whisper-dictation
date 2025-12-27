"""OpenAI Whisper API transcription module."""

import logging
import os
from pathlib import Path

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Raised when transcription fails.

    Attributes:
        message: User-friendly error message.
        original_error: The underlying exception that caused this error.
    """

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        """Initialize transcription error.

        Args:
            message: User-friendly error message.
            original_error: The underlying exception.
        """
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class Transcriber:
    """Handles audio transcription via OpenAI Whisper API.

    Uses the OpenAI Whisper API to transcribe audio files to text.
    Supports multiple languages and handles API errors gracefully.
    """

    def __init__(self, api_key: str) -> None:
        """Initialize the transcriber with an OpenAI API key.

        Args:
            api_key: OpenAI API key for authentication.
        """
        logger.debug("Initializing Transcriber")
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=30.0,
        )
        logger.info("Transcriber initialized")

    async def transcribe(self, audio_path: Path, language: str) -> str:
        """Transcribe an audio file to text.

        Args:
            audio_path: Path to the audio file (WAV format).
            language: ISO 639-1 language code (e.g., "en", "pt").

        Returns:
            The transcribed text.

        Raises:
            TranscriptionError: If transcription fails for any reason.
        """
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        file_size = audio_path.stat().st_size
        logger.info(
            "Transcribing: %s (%d bytes), language=%s",
            audio_path.name,
            file_size,
            language,
        )

        try:
            with audio_path.open("rb") as audio_file:
                response = await self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                )

            text = response.text
            logger.info("Transcription successful: %d characters", len(text))

            # Delete the audio file after successful transcription
            audio_path.unlink(missing_ok=True)
            logger.debug("Deleted audio file: %s", audio_path)

            return text

        except AuthenticationError as e:
            logger.error("Authentication failed: %s", e)
            raise TranscriptionError("Invalid API key", e) from e

        except RateLimitError as e:
            logger.error("Rate limit exceeded: %s", e)
            raise TranscriptionError("Rate limited, please wait", e) from e

        except APIConnectionError as e:
            logger.error("Connection failed: %s", e)
            raise TranscriptionError("Connection failed", e) from e

        except APITimeoutError as e:
            logger.error("Request timed out: %s", e)
            raise TranscriptionError("Request timed out", e) from e

        except Exception as e:
            logger.error("Unexpected error during transcription: %s", e)
            raise TranscriptionError(f"Transcription failed: {e}", e) from e


if __name__ == "__main__":
    import asyncio
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if len(sys.argv) != 2:
        print("Usage: python -m src.transcriber <path_to_wav>")
        sys.exit(1)

    wav_path = Path(sys.argv[1])
    if not wav_path.exists():
        print(f"Error: File not found: {wav_path}")
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    async def main() -> None:
        transcriber = Transcriber(api_key)
        try:
            text = await transcriber.transcribe(wav_path, "en")
            print(f"Transcription: {text}")
        except TranscriptionError as e:
            print(f"Error: {e.message}")
            sys.exit(1)

    asyncio.run(main())
