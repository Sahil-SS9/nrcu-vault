"""Offline Suno prompt-package export and local audio import."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from pipeline.digest import sha256_file

_ALLOWED_AUDIO_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def export_suno_package(
    destination: Path,
    *,
    title: str,
    style: str,
    lyrics: str,
    source_project: str,
) -> Path:
    for name, value in {
        "title": title,
        "style": style,
        "lyrics": lyrics,
        "source_project": source_project,
    }.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be non-empty text")
    package = {
        "schema_version": 1,
        "provider": "suno",
        "mode": "prompt-export-only",
        "cloud_generation_authorised": False,
        "source_project": source_project.strip(),
        "title": title.strip(),
        "style": style.strip(),
        "lyrics": lyrics.strip(),
    }
    _atomic_json(destination, package)
    return destination


def _probe_audio(source: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name:stream=codec_type,codec_name,sample_rate,channels",
            "-of",
            "json",
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"audio validation failed: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    if not any(stream.get("codec_type") == "audio" for stream in data.get("streams", [])):
        raise ValueError("source does not contain an audio stream")
    return data


def import_suno_audio(
    source: Path | str,
    destination: Path,
    *,
    metadata: Mapping[str, str],
    ffprobe: str = "ffprobe",
) -> Path:
    if isinstance(source, str) and urlparse(source).scheme:
        raise ValueError("Suno import requires a local file; remote sources are disabled")
    source_path = Path(source).expanduser().resolve(strict=True)
    if not source_path.is_file():
        raise ValueError("Suno import source must be a local file")
    if source_path.suffix.lower() not in _ALLOWED_AUDIO_SUFFIXES:
        raise ValueError(f"unsupported audio type: {source_path.suffix}")
    receipt_path = destination.with_suffix(".receipt.json")
    if receipt_path.exists():
        raise FileExistsError(receipt_path)
    probe = _probe_audio(source_path, ffprobe)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source_path.open("rb") as source_handle, destination.open("xb") as destination_handle:
        shutil.copyfileobj(source_handle, destination_handle)
    digest = sha256_file(destination)
    receipt = {
        "schema_version": 1,
        "provider": str(metadata.get("provider", "suno")),
        "generation_id": str(metadata.get("generation_id", "manual-import")),
        "source_name": source_path.name,
        "sha256": digest,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "probe": probe,
    }
    try:
        _atomic_json(receipt_path, receipt)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination
