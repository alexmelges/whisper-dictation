# Security Considerations

This document outlines security features, limitations, and recommendations for Whisper Dictation.

## Security Features Implemented

### Data Protection

- **Clipboard Auto-Clear**: Transcriptions are automatically cleared from clipboard after 60 seconds
- **Secure Audio Buffer Wiping**: Audio data is overwritten with zeros before memory release
- **Atomic Config Writes**: Configuration uses temp file + rename pattern to prevent corruption
- **File Permissions**: Config directory (0o700) and files (0o600) are owner-only accessible
- **File Locking**: Config file access uses `fcntl` locking to prevent race conditions

### Error Handling

- **Sanitized Error Messages**: User-facing notifications don't expose system paths or stack traces
- **Full Logging**: Detailed errors are logged for debugging (not shown to users)

### API Security

- **Environment Variable Storage**: API key read from `OPENAI_API_KEY` environment variable
- **No Key Logging**: API key is never logged or displayed
- **HTTPS Only**: OpenAI client enforces TLS for all API calls

## Known Limitations

### Recent Transcriptions

Recent transcriptions are stored in plaintext in the config file at:
```
~/Library/Application Support/Whisper Dictation/config.json
```

**Mitigation**:
- File permissions restrict access to owner only
- Consider disabling recent transcriptions for sensitive use cases
- Clear the file manually if needed: `rm ~/Library/Application\ Support/Whisper\ Dictation/config.json`

### Memory Security

- Audio data exists briefly in memory before/after recording
- API key resides in process memory during runtime
- Python's garbage collector may not immediately free memory

**Mitigation**:
- Audio buffers are zeroed before clearing (best-effort)
- Keep system secure from memory-scraping malware
- Don't run in untrusted environments

### Clipboard Security

- Other applications can read clipboard contents
- Clipboard managers may persist transcribed text

**Mitigation**:
- Auto-clear after 60 seconds
- Avoid sensitive dictation when using clipboard managers
- Use "Paste directly" mode for immediate paste without clipboard persistence

## Code Signing & Distribution

### Why Code Signing Matters

Unsigned apps:
- Trigger macOS Gatekeeper warnings
- Cannot be notarized for distribution
- May be blocked on managed machines
- Cannot access certain entitlements

### Signing the App

1. **Get an Apple Developer account**: https://developer.apple.com

2. **Create signing certificate**:
   ```bash
   # List available identities
   security find-identity -v -p codesigning
   ```

3. **Sign the app**:
   ```bash
   codesign --deep --force --verify --verbose \
     --sign "Developer ID Application: Your Name (TEAM_ID)" \
     "dist/Whisper Dictation.app"
   ```

4. **Create entitlements file** (`entitlements.plist`):
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>com.apple.security.device.audio-input</key>
       <true/>
       <key>com.apple.security.automation.apple-events</key>
       <true/>
   </dict>
   </plist>
   ```

5. **Sign with entitlements**:
   ```bash
   codesign --deep --force --verify --verbose \
     --sign "Developer ID Application: Your Name (TEAM_ID)" \
     --entitlements entitlements.plist \
     --options runtime \
     "dist/Whisper Dictation.app"
   ```

### Notarization

1. **Create ZIP for upload**:
   ```bash
   ditto -c -k --keepParent "dist/Whisper Dictation.app" "WhisperDictation.zip"
   ```

2. **Submit for notarization**:
   ```bash
   xcrun notarytool submit WhisperDictation.zip \
     --apple-id "your@email.com" \
     --team-id "TEAM_ID" \
     --password "app-specific-password" \
     --wait
   ```

3. **Staple the notarization**:
   ```bash
   xcrun stapler staple "dist/Whisper Dictation.app"
   ```

### Sandboxing (Optional)

For App Store distribution or enhanced security, add sandbox entitlements:

```xml
<key>com.apple.security.app-sandbox</key>
<true/>
<key>com.apple.security.files.user-selected.read-write</key>
<true/>
<key>com.apple.security.network.client</key>
<true/>
```

Note: Sandboxing may limit functionality. Test thoroughly.

## Reporting Security Issues

If you discover a security vulnerability, please report it privately rather than opening a public issue.

## Dependencies Security

Dependencies are pinned to specific versions in `requirements.txt` to ensure reproducible builds. Regularly check for security updates:

```bash
pip install pip-audit
pip-audit
```

Update dependencies carefully after testing.
