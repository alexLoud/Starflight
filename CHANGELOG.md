# Starflight Changelog

## [Unreleased]

## [1.1.1] - 2026-08-29

- Video export progress uses a fixed preparation band (0–10%) and frame rendering (10–100%); star preparation is no longer shown as a separate step
- Closing the export dialog no longer regenerates an already valid parallax preview

## [1.1.0] - 2026-08-29

- New App start screen with a redesigned welcome splash and project actions
- Preset library with built-in looks and user-saved custom presets
- New Parallax effect that adds depth motion to starless images
- Easing for camera movement with linear, ease-in, ease-out, and ease-in/out
- Enhanced Preview performance with pre-rendering and cached timeline playback
- Guided introduction that walks new users through the app
- Several UI improvements and redesigns across settings, export, and the project window

## [1.0.3] - 2026-08-24

- Reset buttons for sidebar settings to restore defaults
- Background zoom and rotation now scale at a constant rate from the first to the last frame
- Fixed Windows video export failures (FFmpeg pipe crash, hidden console window, and output path when the default Desktop folder is missing)



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

