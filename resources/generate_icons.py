#!/usr/bin/env python3
"""Generate menu bar icons for Whisper Dictation."""

from pathlib import Path

from PIL import Image, ImageDraw


def create_microphone(draw: ImageDraw.ImageDraw, color: str = "black") -> None:
    """Draw a simple microphone shape.

    Args:
        draw: PIL ImageDraw object.
        color: Fill color for the microphone.
    """
    # Microphone head (rounded rectangle/capsule)
    # Top curve
    draw.ellipse([7, 2, 15, 8], fill=color)
    # Body
    draw.rectangle([7, 5, 15, 11], fill=color)
    # Bottom curve
    draw.ellipse([7, 8, 15, 14], fill=color)

    # Stand/stem
    draw.rectangle([10, 14, 12, 16], fill=color)

    # Base arc (U-shape holder)
    draw.arc([5, 10, 17, 18], start=0, end=180, fill=color, width=2)

    # Base line
    draw.rectangle([6, 18, 16, 19], fill=color)


def create_idle_icon(output_path: Path) -> None:
    """Create the idle state icon (black microphone).

    Args:
        output_path: Path to save the icon.
    """
    img = Image.new("RGBA", (22, 22), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    create_microphone(draw, "black")
    img.save(output_path)
    print(f"Created: {output_path}")


def create_recording_icon(output_path: Path) -> None:
    """Create the recording state icon (microphone with red dot).

    Args:
        output_path: Path to save the icon.
    """
    img = Image.new("RGBA", (22, 22), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    create_microphone(draw, "black")

    # Red recording indicator dot (top-right)
    draw.ellipse([15, 1, 21, 7], fill="red")

    img.save(output_path)
    print(f"Created: {output_path}")


def create_processing_icon(output_path: Path) -> None:
    """Create the processing state icon (gray microphone with dots).

    Args:
        output_path: Path to save the icon.
    """
    img = Image.new("RGBA", (22, 22), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    create_microphone(draw, "gray")

    # Three processing dots at the bottom
    draw.ellipse([3, 19, 6, 22], fill="black")
    draw.ellipse([9, 19, 12, 22], fill="black")
    draw.ellipse([15, 19, 18, 22], fill="black")

    img.save(output_path)
    print(f"Created: {output_path}")


def create_app_icon_microphone(
    draw: ImageDraw.ImageDraw,
    size: int,
    color: str = "white",
) -> None:
    """Draw a microphone scaled to the given size.

    Args:
        draw: PIL ImageDraw object.
        size: Icon size in pixels.
        color: Fill color for the microphone.
    """
    # Scale factor from 22px base
    scale = size / 22

    # Microphone head (rounded rectangle/capsule)
    draw.ellipse(
        [int(7 * scale), int(2 * scale), int(15 * scale), int(8 * scale)],
        fill=color,
    )
    draw.rectangle(
        [int(7 * scale), int(5 * scale), int(15 * scale), int(11 * scale)],
        fill=color,
    )
    draw.ellipse(
        [int(7 * scale), int(8 * scale), int(15 * scale), int(14 * scale)],
        fill=color,
    )

    # Stand/stem
    draw.rectangle(
        [int(10 * scale), int(14 * scale), int(12 * scale), int(16 * scale)],
        fill=color,
    )

    # Base arc (U-shape holder)
    draw.arc(
        [int(5 * scale), int(10 * scale), int(17 * scale), int(18 * scale)],
        start=0,
        end=180,
        fill=color,
        width=max(2, int(2 * scale)),
    )

    # Base line
    draw.rectangle(
        [int(6 * scale), int(18 * scale), int(16 * scale), int(19 * scale)],
        fill=color,
    )


def create_app_icon(output_dir: Path) -> None:
    """Create the application icon in various sizes for .icns generation.

    Creates a .iconset directory with all required sizes, then uses
    iconutil to generate the .icns file.

    Args:
        output_dir: Directory to save the icon files.
    """
    import subprocess
    import shutil

    iconset_dir = output_dir / "app_icon.iconset"
    iconset_dir.mkdir(exist_ok=True)

    # Required sizes for macOS .icns
    sizes = [16, 32, 64, 128, 256, 512, 1024]

    for size in sizes:
        # Create icon with gradient background
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw rounded rectangle background (blue gradient effect)
        margin = int(size * 0.1)
        radius = int(size * 0.2)
        draw.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=radius,
            fill="#2563eb",  # Blue
        )

        # Draw microphone (centered, slightly smaller)
        mic_size = int(size * 0.6)
        mic_offset = (size - mic_size) // 2

        # Create a separate image for the microphone
        mic_img = Image.new("RGBA", (mic_size, mic_size), (0, 0, 0, 0))
        mic_draw = ImageDraw.Draw(mic_img)
        create_app_icon_microphone(mic_draw, mic_size, "white")

        # Paste microphone onto main image
        img.paste(mic_img, (mic_offset, mic_offset), mic_img)

        # Save standard and @2x versions
        if size <= 512:
            img.save(iconset_dir / f"icon_{size}x{size}.png")
        if size >= 32:
            # The @2x version for the size below
            half_size = size // 2
            if half_size >= 16:
                img.save(iconset_dir / f"icon_{half_size}x{half_size}@2x.png")

    print(f"Created iconset at: {iconset_dir}")

    # Try to generate .icns using iconutil (macOS only)
    icns_path = output_dir / "app_icon.icns"
    try:
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
            check=True,
            capture_output=True,
        )
        print(f"Created: {icns_path}")
        # Clean up iconset directory
        shutil.rmtree(iconset_dir)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Warning: Could not generate .icns file: {e}")
        print(f"Iconset saved at: {iconset_dir}")
        print("Run manually: iconutil -c icns app_icon.iconset -o app_icon.icns")


def main() -> None:
    """Generate all icons."""
    script_dir = Path(__file__).parent

    # Menu bar icons (22x22)
    create_idle_icon(script_dir / "icon_idle.png")
    create_recording_icon(script_dir / "icon_recording.png")
    create_processing_icon(script_dir / "icon_processing.png")

    # App icon (.icns)
    create_app_icon(script_dir)

    print("All icons generated successfully!")


if __name__ == "__main__":
    main()
