from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import load_config
from .diagnostics import run_diagnostics
from .errors import AppError, sanitize_message
from .models import VideoRequest
from .output import render_download_summary, render_json_probe, render_probe, render_progress, write_manifest
from .service import DownloadService
from .yt_dlp_adapter import YtDlpAdapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stream-downloader", description="Download YouTube videos and ended live stream archives.")
    parser.add_argument("--version", action="version", version=f"stream-downloader {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    add_common(sub.add_parser("inspect", help="Inspect metadata and formats without downloading media"), needs_url=True)
    add_common(sub.add_parser("download", help="Download and verify one video or ended live archive"), needs_url=True)
    doctor = sub.add_parser("doctor", help="Check local dependencies and writable directories")
    doctor.add_argument("--config", type=Path)
    doctor.add_argument("--output-dir", type=Path)
    doctor.add_argument("--temp-dir", type=Path)
    doctor.add_argument("--browser", action="append", dest="browsers", help="Browser name/profile to validate (repeatable)")
    doctor.add_argument("--json", action="store_true", dest="json_output")
    return parser


def add_common(parser: argparse.ArgumentParser, needs_url: bool = True) -> None:
    if needs_url:
        parser.add_argument("url")
    parser.add_argument("--profile", choices=("maximum", "mp4"), default=None)
    parser.add_argument("--min-height", type=positive_int)
    parser.add_argument("--allow-lower-quality", action="store_true")
    parser.add_argument("--wait-for-height", type=positive_int, help="Poll an archive until this height is available")
    parser.add_argument("--wait-interval", type=positive_float, default=None, help="Seconds between archive probes")
    parser.add_argument("--wait-timeout", type=parse_duration, default=None, help="Maximum archive wait (e.g. 30m, 2h)")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--temp-dir", type=Path)
    parser.add_argument("--ffmpeg-location")
    parser.add_argument("--js-runtime", default=None)
    parser.add_argument("--cookies-from-browser", metavar="BROWSER[:PROFILE]")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_output")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return command_doctor(args)
        return command_media(args)
    except AppError as exc:
        print(f"Error: {sanitize_message(str(exc))}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 8
    except Exception as exc:
        print(f"Unexpected error: {sanitize_message(str(exc))}", file=sys.stderr)
        return 10


def command_doctor(args) -> int:
    overrides = {"output_dir": args.output_dir, "temp_dir": args.temp_dir}
    config = load_config(args.config, overrides)
    results = run_diagnostics(config, args.browsers)
    if args.json_output:
        print(json.dumps([result.to_dict() for result in results], indent=2))
    else:
        for result in results:
            suffix = f" — fix: {result.fix}" if result.fix else ""
            print(f"[{result.status.upper():7}] {result.name}: {result.detail}{suffix}")
    return 0 if all(result.status in {"ok", "info"} for result in results) else 3


def command_media(args) -> int:
    if not args.url.startswith(("https://", "http://")):
        raise AppError("URL must start with http:// or https://.", 2)
    browser = parse_browser(args.cookies_from_browser)
    overrides = {
        "profile": args.profile,
        "output_dir": args.output_dir,
        "temp_dir": args.temp_dir,
        "ffmpeg_location": args.ffmpeg_location,
        "js_runtime": args.js_runtime,
        "cookies_from_browser": browser,
        "wait_interval": args.wait_interval,
        "wait_timeout": args.wait_timeout,
    }
    config = load_config(args.config, overrides)
    progress_callback = lambda progress: print(render_progress(progress), file=sys.stderr) if hasattr(progress, "phase") else None
    adapter = YtDlpAdapter(config, progress_callback)
    service = DownloadService(adapter, config, progress=lambda *items: print(f"Waiting: highest available {items[1] or 'unknown'}p; target {items[2]}p", file=sys.stderr) if items and items[0] == "waiting" else None)
    request = VideoRequest(args.url, config.profile, args.min_height, args.allow_lower_quality)
    if args.command == "inspect":
        probe = service.inspect(request)
        diagnostics = run_diagnostics(config)
        dependency_status = {item.name: item.status for item in diagnostics if item.name in {"ffmpeg", "ffprobe", "JavaScript runtime", "yt-dlp-ejs"}}
        if args.json_output:
            payload = render_json_probe(probe)
            payload["dependencies"] = dependency_status
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(render_probe(probe))
            print("Dependencies: " + ", ".join(f"{name}={status}" for name, status in dependency_status.items()))
        return 0
    probe, result = service.download(request, args.wait_for_height, args.wait_timeout, args.wait_interval)
    manifest = write_manifest(result.path, probe, result)
    if args.json_output:
        print(json.dumps({"probe": render_json_probe(probe), "result": {"path": str(result.path), "height": result.height, "video_codec": result.video_codec, "audio_codec": result.audio_codec, "manifest": str(manifest)}}, indent=2))
    else:
        print(render_download_summary(probe, result))
        print(f"Manifest:    {manifest}")
    return 0


def parse_browser(value: str | None) -> tuple[str, str | None] | None:
    if not value:
        return None
    parts = value.split(":", 1)
    return parts[0], parts[1] if len(parts) == 2 else None


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_duration(value: str) -> float:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        suffix = value[-1].lower()
        return float(value[:-1]) * units[suffix] if suffix in units else float(value)
    except (ValueError, KeyError) as exc:
        raise argparse.ArgumentTypeError("use seconds or a value such as 30m or 2h") from exc

