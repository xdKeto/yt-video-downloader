# Stream Downloader

Windows-friendly Python CLI for inspecting and downloading YouTube videos and ended live stream archives at the best quality exposed to the current session.

Version 1 intentionally does not record active livestreams. It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for extraction and ffmpeg for lossless stream merging.

## Install on Windows

1. Install Python 3.11 or newer.
2. Install FFmpeg (both `ffmpeg.exe` and `ffprobe.exe` are required).
3. Install the recommended JavaScript runtime, Deno.
4. From this folder, install the project and run the diagnostics:

   ```powershell
   py -m pip install -e .
   stream-downloader doctor
   ```

### Install FFmpeg manually

If `winget` is unavailable, download the **release essentials** ZIP from the
[Gyan FFmpeg builds](https://www.gyan.dev/ffmpeg/builds/). Extract it and place
the `bin` directory at a stable location such as:

```text
C:\ffmpeg\bin\ffmpeg.exe
C:\ffmpeg\bin\ffprobe.exe
```

Add `C:\ffmpeg\bin` to your Windows user `PATH`. You can also keep FFmpeg in
another directory and pass that directory to commands with
`--ffmpeg-location C:\path\to\ffmpeg\bin`.

### Install Deno manually

Download the Windows installer from the
[latest Deno release](https://github.com/denoland/deno/releases/latest) and
install it. The default per-user location is usually:

```text
C:\Users\<your-user>\.deno\bin
```

Add that directory to your Windows user `PATH` if the installer did not do so.
Close and reopen PowerShell after changing `PATH`, then verify all required
executables:

```powershell
ffmpeg -version
ffprobe -version
deno --version
```

Finally, run:

```powershell
stream-downloader doctor
```

The `ffmpeg`, `ffprobe`, and `JavaScript runtime` checks must report `OK`.

The `doctor` command reports missing dependencies and the next setup action. The current yt-dlp YouTube extractor also needs its EJS support; `yt-dlp[default]` installs the supported dependency set.

## Usage

```powershell
stream-downloader inspect "https://www.youtube.com/watch?v=VIDEO_ID"
stream-downloader inspect "https://www.youtube.com/watch?v=VIDEO_ID" --json
stream-downloader download "https://www.youtube.com/watch?v=VIDEO_ID" --min-height 1080 --wait-for-height 1080 --wait-timeout 30m
stream-downloader download "https://www.youtube.com/watch?v=VIDEO_ID" --profile mp4 --output-dir downloads
```

`maximum` is the default profile. It selects the best video-only plus best audio-only streams, falling back to a combined format, and uses MKV when the codecs need it. `mp4` prefers MP4/M4A only when that does not reduce the highest available height.

Use `--allow-lower-quality` to explicitly accept a result below `--min-height`. Archive polling is bounded by `--wait-timeout`; the command fails with the highest observed height when the deadline expires.

Authorized browser cookies can be supplied for one invocation, for example `--cookies-from-browser edge` or `--cookies-from-browser chrome:Default`. Cookie values are never written to logs or manifests.

## Configuration

Pass a TOML file with `--config`. See [examples/config.toml](examples/config.toml). Command-line options override file values. Downloads go to `./downloads` and temporary fragments go to `./.stream-downloader-temp` by default.

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for troubleshooting, profiles, output verification, and common Windows setup issues.
