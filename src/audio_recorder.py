"""Audio recording module using pyaudio."""

import logging
import tempfile
import threading
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyaudio

from .constants import (
    AUDIO_FORMAT,
    CHANNELS,
    CHUNK_SIZE,
    MAX_RECORDING_DURATION,
    MIN_RECORDING_DURATION,
    SAMPLE_RATE,
)

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Handles audio recording from the microphone.

    Uses pyaudio's callback-based non-blocking stream to capture audio
    without explicit threading.

    Attributes:
        is_recording: True if currently recording audio.
    """

    def __init__(
        self,
        on_max_duration: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the audio recorder.

        Args:
            on_max_duration: Optional callback when max recording duration is reached.
                           This callback will be called from a timer thread.

        Creates a PyAudio instance for managing audio streams.
        """
        logger.debug("Initializing AudioRecorder")
        self._pyaudio: pyaudio.PyAudio = pyaudio.PyAudio()
        self._stream: pyaudio.Stream | None = None
        self._buffer: list[bytes] = []
        self._is_recording: bool = False
        self._on_max_duration = on_max_duration
        self._max_duration_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        logger.info("AudioRecorder initialized")

    @property
    def is_recording(self) -> bool:
        """Return True if currently recording (thread-safe)."""
        with self._lock:
            return self._is_recording

    def _start_max_duration_timer(self) -> None:
        """Start timer to auto-stop recording after MAX_RECORDING_DURATION."""
        self._cancel_max_duration_timer()
        self._max_duration_timer = threading.Timer(
            MAX_RECORDING_DURATION,
            self._on_max_duration_reached,
        )
        self._max_duration_timer.daemon = True
        self._max_duration_timer.start()
        logger.debug(
            "Max duration timer started (%.0fs)", MAX_RECORDING_DURATION
        )

    def _cancel_max_duration_timer(self) -> None:
        """Cancel the max duration timer if active."""
        if self._max_duration_timer is not None:
            self._max_duration_timer.cancel()
            self._max_duration_timer = None
            logger.debug("Max duration timer cancelled")

    def _on_max_duration_reached(self) -> None:
        """Handle max recording duration being reached."""
        with self._lock:
            if not self._is_recording:
                return  # Already stopped

        logger.warning(
            "Max recording duration (%.0fs) reached, auto-stopping",
            MAX_RECORDING_DURATION,
        )
        if self._on_max_duration:
            try:
                self._on_max_duration()
            except Exception as e:
                logger.error("Error in on_max_duration callback: %s", e)

    def _clear_buffer(self) -> None:
        """Clear the audio buffer.

        Simply clears the buffer list. Python's garbage collector
        will handle memory cleanup.
        """
        self._buffer = []
        logger.debug("Audio buffer cleared")

    def start_recording(self) -> None:
        """Begin capturing audio to an internal buffer.

        Opens an audio stream with the configured parameters and starts
        capturing audio data via callback. Also starts a timer to auto-stop
        if MAX_RECORDING_DURATION is exceeded.

        Raises:
            RuntimeError: If already recording.
            OSError: If microphone is not available or permission denied.
        """
        with self._lock:
            if self._is_recording:
                raise RuntimeError("Already recording")

            logger.info("Starting recording")
            self._buffer = []

            try:
                self._stream = self._pyaudio.open(
                    format=AUDIO_FORMAT,
                    channels=CHANNELS,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=CHUNK_SIZE,
                    stream_callback=self._audio_callback,
                )
                self._stream.start_stream()
                self._is_recording = True
                logger.debug("Recording stream started")
            except OSError as e:
                logger.error("Failed to start recording: %s", e)
                raise OSError(f"Failed to access microphone: {e}") from e

        # Start timer outside lock to avoid holding lock during timer setup
        self._start_max_duration_timer()

    def stop_recording(self) -> Path | None:
        """Stop recording and save audio to a temporary WAV file.

        Stops the audio stream, checks if the recording meets the minimum
        duration requirement, and saves the audio data to a temporary file.

        Returns:
            Path to the temporary WAV file, or None if the recording was
            too short (less than MIN_RECORDING_DURATION seconds).
        """
        # Cancel timer first
        self._cancel_max_duration_timer()

        with self._lock:
            if not self._is_recording:
                logger.warning("stop_recording called but not recording")
                return None

        logger.info("Stopping recording")
        self._stop_stream()

        duration = self._calculate_duration()
        logger.debug("Recording duration: %.2f seconds", duration)

        if duration < MIN_RECORDING_DURATION:
            logger.info(
                "Recording too short (%.2fs < %.2fs), discarding",
                duration,
                MIN_RECORDING_DURATION,
            )
            self._clear_buffer()
            return None

        return self._save_to_temp_file()

    def cancel_recording(self) -> None:
        """Cancel the current recording without saving.

        Stops the audio stream if active and discards all recorded data.
        """
        # Cancel timer first
        self._cancel_max_duration_timer()

        logger.info("Cancelling recording")
        self._stop_stream()
        self._clear_buffer()
        logger.debug("Recording cancelled and buffer cleared")

    def _audio_callback(
        self,
        in_data: bytes | None,
        frame_count: int,
        time_info: dict[str, Any],
        status: int,
    ) -> tuple[None, int]:
        """Handle incoming audio data from the stream.

        Args:
            in_data: Raw audio data from the microphone.
            frame_count: Number of frames in the data.
            time_info: Dictionary with timing information.
            status: Stream status flags.

        Returns:
            Tuple of (None, paContinue) to continue the stream.
        """
        if in_data is not None:
            self._buffer.append(in_data)
        return (None, pyaudio.paContinue)

    def _stop_stream(self) -> None:
        """Stop and close the audio stream (thread-safe)."""
        with self._lock:
            if self._stream is not None:
                try:
                    if self._stream.is_active():
                        self._stream.stop_stream()
                    self._stream.close()
                except OSError as e:
                    logger.error("Error closing stream: %s", e)
                finally:
                    self._stream = None
                    self._is_recording = False

    def _calculate_duration(self) -> float:
        """Calculate the duration of the recorded audio in seconds.

        Returns:
            Duration in seconds.
        """
        if not self._buffer:
            return 0.0

        total_bytes = sum(len(chunk) for chunk in self._buffer)
        # 2 bytes per sample (16-bit audio)
        total_samples = total_bytes // 2
        return total_samples / SAMPLE_RATE

    def _save_to_temp_file(self) -> Path | None:
        """Save the recorded audio buffer to a temporary WAV file.

        Returns:
            Path to the temporary WAV file, or None if saving failed.
        """
        try:
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
                prefix="whisper_dictation_",
            )
            temp_path = Path(temp_file.name)
            temp_file.close()

            logger.debug("Saving recording to %s", temp_path)

            with wave.open(str(temp_path), "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)  # 16-bit = 2 bytes
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(b"".join(self._buffer))

            self._clear_buffer()
            logger.info("Recording saved to %s", temp_path)
            return temp_path

        except OSError as e:
            logger.error("Failed to save recording (disk full?): %s", e)
            self._clear_buffer()
            return None

    def __del__(self) -> None:
        """Clean up pyaudio resources."""
        logger.debug("Cleaning up AudioRecorder")
        self._cancel_max_duration_timer()
        self._stop_stream()

        if hasattr(self, "_pyaudio") and self._pyaudio is not None:
            try:
                self._pyaudio.terminate()
            except OSError as e:
                logger.error("Error terminating PyAudio: %s", e)


if __name__ == "__main__":
    import time

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    recorder = AudioRecorder()
    print("Recording for 3 seconds...")
    recorder.start_recording()
    time.sleep(3)
    path = recorder.stop_recording()

    if path:
        print(f"Saved to: {path}")
        print(f"File size: {path.stat().st_size} bytes")
    else:
        print("Recording too short")
