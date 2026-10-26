# User guide

## Quality behavior

`maximum` asks yt-dlp for `bv+ba/b`: the best separate video and audio streams, with a combined fallback. This often exposes 1080p or higher even when a website download button offers only a lower combined file. Video is never re-encoded.

`mp4` prefers MP4 video and M4A audio. If that would lower the requested height, the command keeps the higher-quality selection and writes MKV. The profile is a compatibility preference, not a reason to silently lower quality.

`--min-height 1080` requires a verified 1080p output. If the archive is still processing, combine it with `--wait-for-height 1080 --wait-timeout 30m`. The wait is finite. Add `--allow-lower-quality` only when a lower result is acceptable.

## Commands

### `doctor`

Checks Python, yt-dlp, yt-dlp EJS, ffmpeg, ffprobe, the configured JavaScript runtime, and writable output/temp directories. Use `--json` for automation. `--browser edge` records a diagnostic reminder for an explicitly requested browser profile without printing cookie data.

### `inspect`

Probes metadata and the current format table without downloading. It prints title, duration, archive/live state, available heights, selected format IDs, codecs, and the merge container. `--json` returns stable machine-readable data.

### `download`

Runs the same probe and quality checks, downloads with resume and bounded retries, merges with ffmpeg, verifies the resulting file with ffprobe, and writes a sibling `.json` manifest. Progress output identifies probing, downloading, merging, and completion.

## Configuration file

```toml
[stream_downloader]
output_dir = "downloads"
temp_dir = ".stream-downloader-temp"
profile = "maximum"
retries = 5
fragment_retries = 10
wait_interval = 60
wait_timeout = 1800
js_runtime = "deno"
# ffmpeg_location = "C:/ffmpeg/bin"
```

Do not put cookies, signed media URLs, or browser database paths in this file.

## Troubleshooting

- **Missing ffmpeg/ffprobe:** install a trusted ffmpeg build and add its `bin` directory to `PATH`, then run `stream-downloader doctor`.
- **Missing JavaScript runtime or EJS:** install Deno and `yt-dlp[default]`; run `doctor` again.
- **Only 480p is available:** inspect first. YouTube may not have finished processing the archive, or the current session may not expose a higher stream. Use bounded wait mode or explicitly allow fallback.
- **Cookies rejected:** close the browser, verify the profile name, and retry. Cookies are read only for the requested invocation.
- **Merge failure:** keep the temporary directory until the ffmpeg error is resolved. The adapter uses yt-dlp's resume files so a retry can reuse downloaded parts.
- **Active livestream:** version 1 does not record an active livestream. Download the archive after it ends.

