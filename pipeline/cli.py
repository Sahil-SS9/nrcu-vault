"""CLI for the local/private NRCU studio."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from pipeline.delivery import export_delivery
from pipeline.h3_backend import render_shot
from pipeline.studio import create_run_directory, load_project, plan_shots
from pipeline.suno_bridge import export_suno_package, import_suno_audio


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())


def _selected(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {part.strip() for part in value.split(",") if part.strip()}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local/private NRCU video studio")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate a project manifest")
    _common(validate)

    plan = subparsers.add_parser("plan", help="Create or resume a safe run plan")
    _common(plan)
    plan.add_argument("--run-id", required=True)
    plan.add_argument("--shots")
    plan.add_argument("--resume", action="store_true")
    plan.add_argument("--skip-existing", action="store_true")

    render = subparsers.add_parser("render", help="Render selected H3 shots locally")
    _common(render)
    render.add_argument("--run-id", required=True)
    render.add_argument("--shots")
    render.add_argument("--resume", action="store_true")
    render.add_argument("--skip-existing", action="store_true")
    render.add_argument(
        "--comfy-input",
        type=Path,
        default=Path(os.environ.get("COMFYUI_INPUT_DIR", "/home/kensei/comfyui-h3/inputs")),
    )

    suno_export = subparsers.add_parser(
        "suno-export", help="Create an offline Suno-ready prompt package"
    )
    suno_export.add_argument("--destination", required=True, type=Path)
    suno_export.add_argument("--title", required=True)
    suno_export.add_argument("--style", required=True)
    suno_export.add_argument("--lyrics-file", required=True, type=Path)
    suno_export.add_argument("--source-project", required=True)

    suno_import = subparsers.add_parser(
        "suno-import", help="Import a manually downloaded Suno audio file"
    )
    suno_import.add_argument("--source", required=True, type=Path)
    suno_import.add_argument("--destination", required=True, type=Path)
    suno_import.add_argument("--generation-id", default="manual-import")

    deliver = subparsers.add_parser("deliver", help="Create a local delivery master")
    deliver.add_argument("--source", required=True, type=Path)
    deliver.add_argument("--destination", required=True, type=Path)
    deliver.add_argument("--profile", choices=["16x9", "9x16"], required=True)
    deliver.add_argument("--subtitles", type=Path)
    return parser


def _plan_payload(project, run_dir: Path, plans) -> dict:
    return {
        "project": project.id,
        "privacy": project.privacy,
        "run_dir": str(run_dir),
        "plan": [
            {
                "id": item.shot.id,
                "backend": item.shot.backend,
                "quality": item.shot.quality,
                "output": str(item.output_path),
            }
            for item in plans
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "suno-export":
        output = export_suno_package(
            args.destination,
            title=args.title,
            style=args.style,
            lyrics=args.lyrics_file.resolve(strict=True).read_text(),
            source_project=args.source_project,
        )
        print(output.read_text(), end="")
        return 0
    if args.command == "suno-import":
        output = import_suno_audio(
            args.source,
            args.destination,
            metadata={"provider": "suno", "generation_id": args.generation_id},
        )
        print(output.with_suffix(".receipt.json").read_text(), end="")
        return 0
    if args.command == "deliver":
        output = export_delivery(
            args.source,
            args.destination,
            profile=args.profile,
            subtitles=args.subtitles,
        )
        print(json.dumps({"output": str(output), "profile": args.profile}, indent=2))
        return 0

    root = args.repo_root.resolve(strict=True)
    project = load_project(args.manifest, root)
    if args.command == "validate":
        print(
            json.dumps(
                {
                    "project": project.id,
                    "privacy": project.privacy,
                    "image_backend": project.image_backend,
                    "video_backend": project.video_backend,
                    "music_backend": project.music_backend,
                    "shots": len(project.shots),
                },
                indent=2,
            )
        )
        return 0

    run_dir = create_run_directory(
        project.output_root,
        project.id,
        args.run_id,
        resume=args.resume,
    )
    plans = plan_shots(
        project,
        run_dir,
        selected=_selected(args.shots),
        skip_existing=args.skip_existing,
    )
    if args.command == "plan":
        print(json.dumps(_plan_payload(project, run_dir, plans), indent=2))
        return 0

    completed = []
    for index, item in enumerate(plans, start=1):
        if item.shot.backend != "h3":
            raise RuntimeError(
                f"backend {item.shot.backend!r} is not activated; FastVideo remains isolated until its spike passes"
            )
        completed.append(
            str(
                render_shot(
                    item.shot,
                    index,
                    endpoint=project.video_endpoint,
                    comfy_input=args.comfy_input,
                    destination=item.output_path,
                )
            )
        )
    payload = _plan_payload(project, run_dir, plans)
    payload["completed"] = completed
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
