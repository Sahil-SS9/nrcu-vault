"""File-backed project contracts for local NRCU video production."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import tomllib


class ContractError(ValueError):
    """Raised when a project manifest violates the local production contract."""


@dataclass(frozen=True)
class ShotSpec:
    id: str
    keyframe: Path
    prompt: str
    backend: str
    quality: str


@dataclass(frozen=True)
class ProjectSpec:
    id: str
    kind: str
    privacy: str
    output_root: Path
    image_backend: str
    video_endpoint: str
    video_backend: str
    music_backend: str
    shots: tuple[ShotSpec, ...]


@dataclass(frozen=True)
class ShotPlan:
    shot: ShotSpec
    output_path: Path


_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ALLOWED_PROJECT_KINDS = {"advert", "episode", "test"}
_ALLOWED_IMAGE_BACKENDS = {"comfyui-local", "preapproved-local"}
_ALLOWED_VIDEO_BACKENDS = {"h3", "fastvideo"}
_ALLOWED_MUSIC_BACKENDS = {"music3", "suno-import", "none"}
_ALLOWED_QUALITIES = {"preview", "turbo", "base", "control", "reference"}


def _require_mapping(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be a table")
    return value


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be non-empty text")
    return value.strip()


def _validate_id(value: str, field: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise ContractError(f"{field} must use lowercase letters, numbers, dot, dash or underscore")
    return value


def _contained_path(
    root: Path,
    raw: object,
    field: str,
    *,
    must_exist: bool,
) -> Path:
    text = _require_text(raw, field)
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        raise ContractError(f"{field} must be contained within the trusted root")
    trusted_root = root.resolve(strict=True)
    candidate = (trusted_root / relative).resolve(strict=must_exist)
    try:
        candidate.relative_to(trusted_root)
    except ValueError as exc:
        raise ContractError(f"{field} must be physically contained within the trusted root") from exc
    if must_exist and not candidate.is_file():
        raise ContractError(f"{field} does not name a regular file")
    return candidate


def _local_endpoint(value: object) -> str:
    endpoint = _require_text(value, "backends.video_endpoint")
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        raise ContractError("video endpoint must use HTTP on localhost")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ContractError("private projects may use localhost video endpoints only")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ContractError("video endpoint may not contain credentials, query or fragment")
    return endpoint.rstrip("/")


def load_project(path: Path, repo_root: Path) -> ProjectSpec:
    root = repo_root.resolve(strict=True)
    manifest_path = path.resolve(strict=True)
    try:
        manifest_path.relative_to(root)
    except ValueError as exc:
        raise ContractError("project manifest must be contained within the repository") from exc

    with manifest_path.open("rb") as handle:
        data = tomllib.load(handle)
    if data.get("schema_version") != 1:
        raise ContractError("schema_version must be 1")

    project_data = _require_mapping(data.get("project"), "project")
    paths_data = _require_mapping(data.get("paths"), "paths")
    backends_data = _require_mapping(data.get("backends"), "backends")

    project_id = _validate_id(_require_text(project_data.get("id"), "project.id"), "project.id")
    kind = _require_text(project_data.get("kind"), "project.kind")
    if kind not in _ALLOWED_PROJECT_KINDS:
        raise ContractError(f"project.kind must be one of {sorted(_ALLOWED_PROJECT_KINDS)}")
    privacy = _require_text(project_data.get("privacy"), "project.privacy")
    if privacy != "local-private":
        raise ContractError("project.privacy must be local-private")

    output_root = _contained_path(
        root,
        paths_data.get("output_root"),
        "paths.output_root",
        must_exist=False,
    )
    image_backend = _require_text(backends_data.get("image"), "backends.image")
    if image_backend not in _ALLOWED_IMAGE_BACKENDS:
        raise ContractError(f"image backend must be one of {sorted(_ALLOWED_IMAGE_BACKENDS)}")
    video_backend = _require_text(backends_data.get("video"), "backends.video")
    if video_backend not in _ALLOWED_VIDEO_BACKENDS:
        raise ContractError(f"video backend must be one of {sorted(_ALLOWED_VIDEO_BACKENDS)}")
    music_backend = _require_text(backends_data.get("music"), "backends.music")
    if music_backend not in _ALLOWED_MUSIC_BACKENDS:
        raise ContractError(f"music backend must be one of {sorted(_ALLOWED_MUSIC_BACKENDS)}")
    endpoint = _local_endpoint(backends_data.get("video_endpoint"))

    raw_shots = data.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ContractError("shots must contain at least one shot")
    shots: list[ShotSpec] = []
    seen: set[str] = set()
    for index, raw_shot in enumerate(raw_shots, start=1):
        shot_data = _require_mapping(raw_shot, f"shots[{index}]")
        shot_id = _validate_id(
            _require_text(shot_data.get("id"), f"shots[{index}].id"),
            f"shots[{index}].id",
        )
        if shot_id in seen:
            raise ContractError(f"duplicate shot id: {shot_id}")
        seen.add(shot_id)
        backend = _require_text(shot_data.get("backend"), f"shots[{index}].backend")
        if backend not in _ALLOWED_VIDEO_BACKENDS:
            raise ContractError(f"unsupported shot backend: {backend}")
        quality = _require_text(shot_data.get("quality"), f"shots[{index}].quality")
        if quality not in _ALLOWED_QUALITIES:
            raise ContractError(f"unsupported shot quality: {quality}")
        shots.append(
            ShotSpec(
                id=shot_id,
                keyframe=_contained_path(
                    root,
                    shot_data.get("keyframe"),
                    f"shots[{index}].keyframe",
                    must_exist=True,
                ),
                prompt=_require_text(shot_data.get("prompt"), f"shots[{index}].prompt"),
                backend=backend,
                quality=quality,
            )
        )

    return ProjectSpec(
        id=project_id,
        kind=kind,
        privacy=privacy,
        output_root=output_root,
        image_backend=image_backend,
        video_endpoint=endpoint,
        video_backend=video_backend,
        music_backend=music_backend,
        shots=tuple(shots),
    )


def create_run_directory(
    output_root: Path,
    project_id: str,
    run_id: str,
    *,
    resume: bool = False,
) -> Path:
    project_id = _validate_id(project_id, "project_id")
    run_id = _validate_id(run_id, "run_id")
    root = output_root.resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = (root / project_id / run_id).resolve(strict=False)
    try:
        run_dir.relative_to(root)
    except ValueError as exc:
        raise ContractError("run directory escaped the output root") from exc
    if run_dir.exists() and not resume:
        raise FileExistsError(f"run directory already exists: {run_dir}")
    (run_dir / "clips").mkdir(parents=True, exist_ok=resume)
    (run_dir / "audio").mkdir(parents=True, exist_ok=resume)
    (run_dir / "delivery").mkdir(parents=True, exist_ok=resume)
    return run_dir


def plan_shots(
    project: ProjectSpec,
    run_dir: Path,
    *,
    selected: Iterable[str] | None = None,
    skip_existing: bool = False,
) -> list[ShotPlan]:
    known = {shot.id for shot in project.shots}
    wanted = set(selected) if selected is not None else known
    unknown = wanted - known
    if unknown:
        raise ContractError(f"unknown shot ids: {', '.join(sorted(unknown))}")
    clips = (run_dir.resolve(strict=True) / "clips").resolve(strict=True)
    plans: list[ShotPlan] = []
    for shot in project.shots:
        if shot.id not in wanted:
            continue
        output_path = (clips / f"{shot.id}.mp4").resolve(strict=False)
        try:
            output_path.relative_to(clips)
        except ValueError as exc:
            raise ContractError("shot output escaped the clips directory") from exc
        if skip_existing and output_path.is_file():
            continue
        plans.append(ShotPlan(shot=shot, output_path=output_path))
    return plans
