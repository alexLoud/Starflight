# Starflight Changelog

## [Unreleased]

- Fixed Windows video export crash (`OSError: [Errno 22] Invalid argument`) when piping frames to FFmpeg
- Hidden the empty FFmpeg console window during export on Windows

## [1.0.2] - 2026-08-23

- Implemented Crash reports with persistent diagnostic logs for startup, runtime, and native failures
- Welcome screen shows an info and link when a newer release on GitHub is available

## [1.0.1] - 2026-08-23

- Rotation range extended to ±45°
- Star density presets: Low 500, Medium 1500, High 2500
- New defaults: smallest stars 1.0 px, size spread 25 %, fill frame off
- Export rendering uses up to 4 CPU cores by default; configurable in Settings
- About dialog under Help menu
- Zoom toolbar: labeled stars on/off toggle and wider panel



## [1.0.0] - 2026-08-22

- Initial release
