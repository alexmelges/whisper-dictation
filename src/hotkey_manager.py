"""Global hotkey detection for recording control."""

import logging
import threading
from collections.abc import Callable
from typing import Any, Union

from pynput.keyboard import Key, KeyCode, Listener

# macOS keycode for space bar
_SPACE_KEYCODE = 49

from .constants import DEFAULT_HOTKEY

logger = logging.getLogger(__name__)

# Mapping of left/right modifier variants to their canonical form
_KEY_NORMALIZATIONS: dict[Key, Key] = {
    Key.alt_l: Key.alt,
    Key.alt_r: Key.alt,
    Key.alt_gr: Key.alt,
    Key.ctrl_l: Key.ctrl,
    Key.ctrl_r: Key.ctrl,
    Key.shift_l: Key.shift,
    Key.shift_r: Key.shift,
    Key.cmd_l: Key.cmd,
    Key.cmd_r: Key.cmd,
}


class HotkeyManager:
    """Manages global hotkey detection for recording control.

    Implements a "hold to record" pattern where pressing the hotkey
    combination starts recording, and releasing any key in the
    combination stops recording.

    Attributes:
        is_listening: True if the keyboard listener is active.
    """

    def __init__(
        self,
        on_record_start: Callable[[], None],
        on_record_stop: Callable[[], None],
        on_cancel: Callable[[], None] | None = None,
        hotkey: frozenset[Union[Key, KeyCode]] | None = None,
    ) -> None:
        """Initialize the hotkey manager.

        Args:
            on_record_start: Callback when recording should start.
            on_record_stop: Callback when recording should stop.
            on_cancel: Optional callback when recording is cancelled (ESC).
            hotkey: Optional custom hotkey combination. Defaults to Option+Space.
        """
        logger.debug("Initializing HotkeyManager")
        self._on_record_start = on_record_start
        self._on_record_stop = on_record_stop
        self._on_cancel = on_cancel or (lambda: None)
        self._hotkey = hotkey if hotkey is not None else DEFAULT_HOTKEY

        # Thread lock for protecting state
        self._lock = threading.RLock()
        self._pressed_keys: set[Union[Key, KeyCode]] = set()
        self._is_recording: bool = False
        self._listener: Listener | None = None

        logger.info(
            "HotkeyManager initialized with hotkey: %s",
            {str(k) for k in self._hotkey},
        )

    @property
    def is_listening(self) -> bool:
        """Return True if the keyboard listener is active."""
        return self._listener is not None and self._listener.is_alive()

    @property
    def is_recording(self) -> bool:
        """Return True if currently in recording state (thread-safe)."""
        with self._lock:
            return self._is_recording

    def start_listening(self) -> None:
        """Start the keyboard listener in a background thread.

        The listener will detect hotkey presses and releases,
        triggering the appropriate callbacks.
        """
        if self.is_listening:
            logger.warning("Listener already running")
            return

        logger.info("Starting keyboard listener")
        with self._lock:
            self._pressed_keys.clear()
            self._is_recording = False

        self._listener = Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=True,
            darwin_intercept=self._intercept_event,
        )
        self._listener.start()
        logger.debug("Keyboard listener started")

    def stop_listening(self) -> None:
        """Stop the keyboard listener.

        If currently recording, triggers the stop callback first.
        """
        if self._listener is None:
            return

        logger.info("Stopping keyboard listener")

        # Check recording state and prepare callback outside lock
        should_stop_recording = False
        with self._lock:
            if self._is_recording:
                self._is_recording = False
                should_stop_recording = True
            self._pressed_keys.clear()

        # Execute callback outside lock to prevent deadlocks
        if should_stop_recording:
            try:
                self._on_record_stop()
            except Exception as e:
                logger.error("Error in on_record_stop callback: %s", e)

        self._listener.stop()
        self._listener.join(timeout=1.0)
        self._listener = None
        logger.debug("Keyboard listener stopped")

    def _normalize_key(self, key: Union[Key, KeyCode]) -> Union[Key, KeyCode]:
        """Normalize a key to its canonical form.

        Maps left/right modifier variants (e.g., alt_l, alt_r) to their
        canonical form (e.g., alt).

        Args:
            key: The key to normalize.

        Returns:
            The normalized key.
        """
        if isinstance(key, Key) and key in _KEY_NORMALIZATIONS:
            return _KEY_NORMALIZATIONS[key]
        return key

    def _intercept_event(self, event_type: int, event: Any) -> Any | None:
        """Intercept keyboard events and suppress hotkey keys during recording.

        This prevents the space character from being typed into the active
        application while holding Option+Space to record.

        Args:
            event_type: The type of keyboard event.
            event: The raw CGEvent from macOS.

        Returns:
            None to suppress the event, or the event to allow it through.
        """
        # Only suppress when recording is active (thread-safe check)
        with self._lock:
            is_recording = self._is_recording
        if not is_recording:
            return event

        # Suppress space key while recording to prevent typing spaces
        try:
            from Quartz import CGEventGetIntegerValueField, kCGKeyboardEventKeycode

            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            if keycode == _SPACE_KEYCODE:
                return None  # Suppress space
        except Exception:
            # If Quartz import fails, allow event through
            pass

        return event

    def _on_press(self, key: Union[Key, KeyCode]) -> None:
        """Handle a key press event.

        Args:
            key: The key that was pressed.
        """
        normalized = self._normalize_key(key)
        callback_to_call = None

        with self._lock:
            # Ignore key repeat (key already pressed)
            if normalized in self._pressed_keys:
                return

            self._pressed_keys.add(normalized)
            logger.debug("Key pressed: %s (normalized: %s)", key, normalized)

            # Check for cancel (ESC during recording)
            if self._is_recording and key == Key.esc:
                logger.info("Recording cancelled via ESC")
                self._is_recording = False
                callback_to_call = "cancel"
            # Check if hotkey combination is complete
            elif not self._is_recording and self._hotkey.issubset(self._pressed_keys):
                logger.info("Hotkey activated, starting recording")
                self._is_recording = True
                callback_to_call = "start"

        # Execute callbacks outside lock to prevent deadlocks
        if callback_to_call == "cancel":
            try:
                self._on_cancel()
            except Exception as e:
                logger.error("Error in on_cancel callback: %s", e)
        elif callback_to_call == "start":
            try:
                self._on_record_start()
            except Exception as e:
                logger.error("Error in on_record_start callback: %s", e)
                with self._lock:
                    self._is_recording = False

    def _on_release(self, key: Union[Key, KeyCode]) -> None:
        """Handle a key release event.

        Args:
            key: The key that was released.
        """
        normalized = self._normalize_key(key)
        logger.debug("Key released: %s (normalized: %s)", key, normalized)

        should_stop_recording = False
        with self._lock:
            # If recording and released a hotkey key, stop recording
            if self._is_recording and normalized in self._hotkey:
                logger.info("Hotkey released, stopping recording")
                self._is_recording = False
                should_stop_recording = True

            self._pressed_keys.discard(normalized)

        # Execute callback outside lock to prevent deadlocks
        if should_stop_recording:
            try:
                self._on_record_stop()
            except Exception as e:
                logger.error("Error in on_record_stop callback: %s", e)


if __name__ == "__main__":
    import signal
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    def on_start() -> None:
        print("Recording started")

    def on_stop() -> None:
        print("Recording stopped")

    def on_cancel() -> None:
        print("Cancelled")

    manager = HotkeyManager(on_start, on_stop, on_cancel)
    manager.start_listening()

    print("Press Option+Space to record, ESC to cancel, Ctrl+C to quit")
    print("Listening for hotkeys...")

    # Keep running until Ctrl+C
    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\nShutting down...")
        manager.stop_listening()
        sys.exit(0)
