"""Local delivery exporters for horizontal and vertical review masters."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

_PROFILES = {
    "16x9": "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
    "9x16": "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280",
}


def _subtitle_filter(path: Path) -> str:
    if urlparse(str(path)).scheme:
        raise ValueError("subtitle input must be a local file")
    local = path.expanduser().resolve(strict=True)
    if not local.is_file():
        raise ValueError("subtitle input must be a local file")
    escaped = str(local).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles=filename='{escaped}'"


def build_ffmpeg_command(
    source: Path,
    destination: Path,
    *,
    profile: str,
    subtitles: Path | None = None,
) -> list[str]:
    if profile not in _PROFILES:
        raise ValueError(f"profile must be one of {sorted(_PROFILES)}")
    filters = [_PROFILES[profile]]
    if subtitles is not None:
        filters.append(_subtitle_filter(subtitles))
    return [
        "ffmpeg",
        "-n",
        "-v",
        "error",
        "-i",
        str(source),
        "-vf",
        ",".join(filters),
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(destination),
    ]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def export_delivery(
    source: Path,
    destination: Path,
    *,
    profile: str,
    subtitles: Path | None = None,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> Path:
    source = source.expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("delivery source must be a local video file")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = build_ffmpeg_command(source, destination, profile=profile, subtitles=subtitles)
    command[0] = ffmpeg
    encoded = _run(command)
    if encoded.returncode != 0:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"delivery encode failed: {encoded.stderr.strip()}")
    decoded = _run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(destination),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-f",
            "null",
            "-",
        ]
    )
    if decoded.returncode != 0:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"delivery decode failed: {decoded.stderr.strip()}")
    probed = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(destination),
        ]
    )
    if probed.returncode != 0:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"delivery probe failed: {probed.stderr.strip()}")
    try:
        json.loads(probed.stdout or "{}")
    except json.JSONDecodeError as exc:
        destination.unlink(missing_ok=True)
        raise RuntimeError("delivery probe returned invalid JSON") from exc
    return destination
