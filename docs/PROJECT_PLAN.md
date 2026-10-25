# YouTube Stream Downloader Project Plan

This project will begin as a Windows-friendly CLI for downloading YouTube videos and ended live stream archives at the highest quality available to the current session.

The approved design is documented in:

- [Detailed design and implementation plan](superpowers/specs/2026-10-25-youtube-stream-downloader-design.md)

## First milestone

Build a Python CLI with:

1. `doctor` to diagnose yt-dlp, ffmpeg/ffprobe, and JavaScript runtime setup.
2. `inspect` to show the archive state, available formats, and selected quality.
3. `download` to select best video plus audio, merge with ffmpeg, and verify the output.
4. A bounded wait mode for archives whose requested quality is still processing.

The default quality policy protects the user's requested minimum. If 1080p is unavailable, the command reports the highest available quality and does not silently download 480p unless lower-quality fallback is explicitly enabled.

## Later milestones

- Batch downloads and reusable profiles.
- Standalone Windows packaging.
- Active livestream capture as a separate mode after archive downloads are reliable.

See the detailed design for architecture, source research, error handling, dependencies, and verification scenarios.
