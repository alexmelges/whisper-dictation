#!/bin/bash
#
# Build Whisper Dictation as a standalone macOS app
#
# Usage:
#   ./build.sh          # Build the app
#   ./build.sh clean    # Clean build artifacts
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Handle clean command
if [ "$1" = "clean" ]; then
    echo_info "Cleaning build artifacts..."
    rm -rf build dist .eggs *.egg-info
    echo_info "Clean complete."
    exit 0
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo_error "Virtual environment not found."
    echo "Please run:"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo_info "Activating virtual environment..."
source venv/bin/activate

# Check for py2app
if ! python -c "import py2app" 2>/dev/null; then
    echo_warn "py2app not found, installing..."
    pip install py2app
fi

# Generate app icon if it doesn't exist
if [ ! -f "resources/app_icon.icns" ]; then
    echo_warn "App icon not found. Building without custom dock icon."
    echo_warn "To add an icon, create resources/app_icon.icns"
fi

# Clean previous builds
echo_info "Cleaning previous builds..."
rm -rf build dist

# Build the app
echo_info "Building Whisper Dictation..."
python setup.py py2app

# Remove quarantine and ad-hoc sign the app
echo_info "Signing the app..."
xattr -cr "dist/Whisper Dictation.app"
codesign --force --deep --sign - "dist/Whisper Dictation.app"

echo ""
echo "========================================"
echo -e "${GREEN}Build complete!${NC}"
echo "========================================"
echo ""
echo "App location:"
echo "  dist/Whisper Dictation.app"
echo ""
echo "To run the app:"
echo "  open 'dist/Whisper Dictation.app'"
echo ""
echo "To install (copy to Applications):"
echo "  cp -r 'dist/Whisper Dictation.app' /Applications/"
echo "  codesign --force --deep --sign - '/Applications/Whisper Dictation.app'"
echo ""
echo "========================================"
echo "IMPORTANT: First-time setup"
echo "========================================"
echo "1. Set your OpenAI API key:"
echo "   export OPENAI_API_KEY='your-api-key-here'"
echo ""
echo "2. Grant permissions when prompted:"
echo "   - Microphone access (for recording)"
echo "   - Accessibility (for global hotkeys)"
echo ""
echo "For code signing (distribution), see SECURITY.md"
echo ""
