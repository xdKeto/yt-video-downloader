from __future__ import annotations

import importlib
import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

from .models import DiagnosticResult


def run_diagnostics(config, browsers: list[str] | None = None) -> list[DiagnosticResult]:
    checks = [check_python(), check_ytdlp(), check_ejs(), check_executable("ffmpeg"), check_executable("ffprobe"), check_js_runtime(config.js_runtime), check_directory(config.output_dir, "output"), check_directory(config.temp_dir, "temporary")]
    if browsers:
        checks.extend(check_browser(name) for name in browsers)
    return checks


def check_python() -> DiagnosticResult:
    good = sys.version_info >= (3, 11)
    return DiagnosticResult("Python", "ok" if good else "missing", sys.version.split()[0], None if good else "Install Python 3.11 or newer.")


def check_ytdlp() -> DiagnosticResult:
    try:
        module = importlib.import_module("yt_dlp")
        version = getattr(module, "version", None)
        value = getattr(version, "__version__", None) or importlib.metadata.version("yt-dlp")
        return DiagnosticResult("yt-dlp", "ok", str(value))
    except Exception as exc:
        return DiagnosticResult("yt-dlp", "missing", str(exc), "Install with: python -m pip install -e .")


def check_executable(name: str) -> DiagnosticResult:
    path = shutil.which(name) or shutil.which(f"{name}.exe")
    if not path:
        return DiagnosticResult(name, "missing", "not found on PATH", f"Install {name} and ensure {name}.exe is on PATH.")
    try:
        output = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10).stdout.splitlines()[0]
    except Exception as exc:
        output = str(exc)
    return DiagnosticResult(name, "ok", f"{path}: {output}")


def check_ejs() -> DiagnosticResult:
    try:
        version = importlib.metadata.version("yt-dlp-ejs")
        return DiagnosticResult("yt-dlp-ejs", "ok", version)
    except importlib.metadata.PackageNotFoundError:
        return DiagnosticResult("yt-dlp-ejs", "missing", "package not installed", "Install yt-dlp[default] or add yt-dlp-ejs to the environment.")


def check_js_runtime(runtime: str) -> DiagnosticResult:
    path = shutil.which(runtime) or shutil.which(f"{runtime}.exe")
    if not path:
        return DiagnosticResult("JavaScript runtime", "missing", f"{runtime} not found on PATH", "Install Deno (recommended) or configure a supported Node runtime.")
    return DiagnosticResult("JavaScript runtime", "ok", f"{runtime}: {path}")


def check_directory(path: Path, label: str) -> DiagnosticResult:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".stream-downloader-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return DiagnosticResult(f"{label} directory", "ok", str(path.resolve()))
    except OSError as exc:
        return DiagnosticResult(f"{label} directory", "missing", f"{path}: {exc}", "Choose a writable directory with --output-dir or --temp-dir.")


def check_browser(name: str) -> DiagnosticResult:
    return DiagnosticResult(f"browser profile {name}", "info", "yt-dlp will inspect the profile only when the command runs", "Close the browser if cookie database access is denied.")

