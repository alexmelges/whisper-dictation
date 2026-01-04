"""Permission checking for macOS Accessibility and Microphone access."""

import logging
import subprocess
from enum import Enum

logger = logging.getLogger(__name__)


class PermissionStatus(Enum):
    """Status of a permission check."""

    GRANTED = "granted"
    DENIED = "denied"
    UNKNOWN = "unknown"


def check_accessibility_permission() -> PermissionStatus:
    """Check if Accessibility permission is granted.

    Uses ApplicationServices framework to check if the process is trusted
    for accessibility features (required for global hotkeys).

    Returns:
        PermissionStatus indicating whether accessibility is granted.
    """
    try:
        from ApplicationServices import AXIsProcessTrusted

        is_trusted = AXIsProcessTrusted()
        if is_trusted:
            logger.info("Accessibility permission: granted")
            return PermissionStatus.GRANTED
        else:
            logger.warning("Accessibility permission: denied")
            return PermissionStatus.DENIED

    except ImportError:
        # ApplicationServices not available - likely not on macOS
        # or pyobjc-framework-ApplicationServices not installed
        logger.warning(
            "Cannot check Accessibility permission: "
            "ApplicationServices framework not available"
        )
        return PermissionStatus.UNKNOWN
    except Exception as e:
        logger.error("Error checking Accessibility permission: %s", e)
        return PermissionStatus.UNKNOWN


def check_microphone_permission() -> PermissionStatus:
    """Check if Microphone permission is granted.

    Uses AVFoundation framework to check microphone authorization status.

    Returns:
        PermissionStatus indicating whether microphone access is granted.
    """
    try:
        from AVFoundation import (
            AVCaptureDevice,
            AVMediaTypeAudio,
            AVAuthorizationStatusAuthorized,
            AVAuthorizationStatusDenied,
            AVAuthorizationStatusRestricted,
            AVAuthorizationStatusNotDetermined,
        )

        status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)

        if status == AVAuthorizationStatusAuthorized:
            logger.info("Microphone permission: granted")
            return PermissionStatus.GRANTED
        elif status in (AVAuthorizationStatusDenied, AVAuthorizationStatusRestricted):
            logger.warning("Microphone permission: denied")
            return PermissionStatus.DENIED
        elif status == AVAuthorizationStatusNotDetermined:
            # Not yet determined - will be requested on first use
            logger.info("Microphone permission: not yet determined")
            return PermissionStatus.UNKNOWN
        else:
            logger.warning("Microphone permission: unknown status %s", status)
            return PermissionStatus.UNKNOWN

    except ImportError:
        # AVFoundation not available
        logger.warning(
            "Cannot check Microphone permission: "
            "AVFoundation framework not available"
        )
        return PermissionStatus.UNKNOWN
    except Exception as e:
        logger.error("Error checking Microphone permission: %s", e)
        return PermissionStatus.UNKNOWN


def request_accessibility_permission() -> None:
    """Prompt for Accessibility permission by opening System Settings.

    Opens the Accessibility pane in System Settings where the user
    can grant permission to the application.
    """
    logger.info("Opening System Settings > Privacy & Security > Accessibility")
    try:
        # Try to prompt for permission first (shows dialog on first request)
        try:
            from ApplicationServices import AXIsProcessTrustedWithOptions
            from Foundation import NSDictionary

            # kAXTrustedCheckOptionPrompt = True triggers the system dialog
            options = NSDictionary.dictionaryWithObject_forKey_(
                True, "AXTrustedCheckOptionPrompt"
            )
            AXIsProcessTrustedWithOptions(options)
        except ImportError:
            pass

        # Also open System Settings for manual configuration
        subprocess.run(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security"
                "?Privacy_Accessibility",
            ],
            check=False,
        )
    except Exception as e:
        logger.error("Failed to open System Settings: %s", e)


def request_microphone_permission() -> None:
    """Open System Settings to the Microphone privacy pane."""
    logger.info("Opening System Settings > Privacy & Security > Microphone")
    try:
        subprocess.run(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security"
                "?Privacy_Microphone",
            ],
            check=False,
        )
    except Exception as e:
        logger.error("Failed to open System Settings: %s", e)


def check_all_permissions() -> dict[str, PermissionStatus]:
    """Check all required permissions.

    Returns:
        Dictionary mapping permission name to its status.
    """
    return {
        "accessibility": check_accessibility_permission(),
        "microphone": check_microphone_permission(),
    }


def get_missing_permissions() -> list[str]:
    """Get a list of permissions that are not granted.

    Returns:
        List of permission names that are denied or unknown.
    """
    permissions = check_all_permissions()
    missing = []

    for name, status in permissions.items():
        if status != PermissionStatus.GRANTED:
            missing.append(name)

    return missing


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("Checking permissions...")
    permissions = check_all_permissions()

    for name, status in permissions.items():
        print(f"  {name}: {status.value}")

    missing = get_missing_permissions()
    if missing:
        print(f"\nMissing permissions: {', '.join(missing)}")
        print("\nWould you like to open System Settings? (y/n)")
        if input().lower() == "y":
            if "accessibility" in missing:
                request_accessibility_permission()
            if "microphone" in missing:
                request_microphone_permission()
    else:
        print("\nAll permissions granted!")
