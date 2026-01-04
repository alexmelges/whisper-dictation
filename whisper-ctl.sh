#!/bin/bash
#
# Whisper Dictation Control Script
#
# Usage:
#   ./whisper-ctl.sh start    # Start the service (runs in background)
#   ./whisper-ctl.sh stop     # Stop the service
#   ./whisper-ctl.sh restart  # Restart the service
#   ./whisper-ctl.sh status   # Check if running
#   ./whisper-ctl.sh run      # Run interactively (foreground)
#   ./whisper-ctl.sh logs     # Tail the log file
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.whisper.dictation"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
LOG_FILE="$HOME/Library/Logs/WhisperDictation.log"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
LAUNCHER_SCRIPT="$SCRIPT_DIR/.whisper-launcher.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prereqs() {
    if [ ! -f "$VENV_PYTHON" ]; then
        echo_error "Virtual environment not found at $SCRIPT_DIR/venv"
        echo "Please run:"
        echo "  python -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt"
        exit 1
    fi

    if [ -z "$OPENAI_API_KEY" ]; then
        echo_error "OPENAI_API_KEY environment variable not set"
        echo "Please set it:"
        echo "  export OPENAI_API_KEY='your-api-key-here'"
        exit 1
    fi
}

# Create launcher script that sources shell profile for API key
create_launcher() {
    cat > "$LAUNCHER_SCRIPT" << 'LAUNCHER_EOF'
#!/bin/bash
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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
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
LAUNCHER_EOF
    chmod +x "$LAUNCHER_SCRIPT"
    echo_info "Created launcher script at $LAUNCHER_SCRIPT"
}

# Create LaunchAgent plist
create_plist() {
    mkdir -p "$HOME/Library/LaunchAgents"

    # Create the launcher script that sources shell profile
    create_launcher

    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$LAUNCHER_SCRIPT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>$HOME</string>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_FILE</string>
    <key>StandardErrorPath</key>
    <string>$LOG_FILE</string>
</dict>
</plist>
EOF
    echo_info "Created LaunchAgent at $PLIST_PATH"
}

# Start the service
cmd_start() {
    check_prereqs

    if launchctl list | grep -q "$PLIST_NAME"; then
        echo_warn "Service is already running"
        echo "Use './whisper-ctl.sh restart' to restart"
        exit 0
    fi

    create_plist
    launchctl load "$PLIST_PATH"
    echo_info "Whisper Dictation started"
    echo ""
    echo "The menu bar icon should appear shortly."
    echo "Use Option+Space to record."
    echo ""
    echo "To view logs: ./whisper-ctl.sh logs"
    echo "To stop:      ./whisper-ctl.sh stop"
}

# Stop the service
cmd_stop() {
    if ! launchctl list | grep -q "$PLIST_NAME"; then
        echo_warn "Service is not running"
        exit 0
    fi

    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    rm -f "$LAUNCHER_SCRIPT"
    echo_info "Whisper Dictation stopped"
}

# Restart the service
cmd_restart() {
    echo_info "Restarting Whisper Dictation..."
    cmd_stop
    sleep 1
    cmd_start
}

# Check status
cmd_status() {
    if launchctl list | grep -q "$PLIST_NAME"; then
        echo_info "Whisper Dictation is running"

        # Show PID
        PID=$(pgrep -f "python.*src.main" 2>/dev/null || true)
        if [ -n "$PID" ]; then
            echo "  PID: $PID"
        fi

        # Show log file location
        if [ -f "$LOG_FILE" ]; then
            echo "  Log: $LOG_FILE"
            echo ""
            echo "Recent log entries:"
            tail -5 "$LOG_FILE" 2>/dev/null | sed 's/^/  /'
        fi
    else
        echo_warn "Whisper Dictation is not running"
        echo "Use './whisper-ctl.sh start' to start"
    fi
}

# Run interactively (foreground)
cmd_run() {
    check_prereqs

    echo_info "Running Whisper Dictation interactively..."
    echo "Press Ctrl+C to stop"
    echo ""

    cd "$SCRIPT_DIR"
    exec "$VENV_PYTHON" -m src.main
}

# Tail logs
cmd_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo_warn "No log file found at $LOG_FILE"
        echo "Start the service first: ./whisper-ctl.sh start"
        exit 1
    fi

    echo_info "Tailing $LOG_FILE (Ctrl+C to stop)"
    echo ""
    tail -f "$LOG_FILE"
}

# Show usage
cmd_help() {
    echo "Whisper Dictation Control Script"
    echo ""
    echo "Usage: ./whisper-ctl.sh <command>"
    echo ""
    echo "Commands:"
    echo "  start    Start the service (runs in background, auto-starts at login)"
    echo "  stop     Stop the service"
    echo "  restart  Restart the service"
    echo "  status   Check if running"
    echo "  run      Run interactively (foreground, for debugging)"
    echo "  logs     Tail the log file"
    echo "  help     Show this help message"
    echo ""
    echo "Prerequisites:"
    echo "  1. Set OPENAI_API_KEY environment variable"
    echo "  2. Create and activate virtual environment:"
    echo "     python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
}

# Main
case "${1:-help}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    run)     cmd_run ;;
    logs)    cmd_logs ;;
    help|--help|-h) cmd_help ;;
    *)
        echo_error "Unknown command: $1"
        echo ""
        cmd_help
        exit 1
        ;;
esac
