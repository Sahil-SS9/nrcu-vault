from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from pipeline.studio import (
    ContractError,
    create_run_directory,
    load_project,
    plan_shots,
)
from pipeline.suno_bridge import export_suno_package, import_suno_audio

MANIFEST = '''
schema_version = 1

[project]
id = "demo-ad"
kind = "advert"
privacy = "local-private"

[paths]
output_root = "outputs"

[backends]
image = "comfyui-local"
video = "h3"
video_endpoint = "http://127.0.0.1:8189"
music = "music3"

[[shots]]
id = "s01"
keyframe = "assets/s01.png"
prompt = "One clear action."
backend = "h3"
quality = "base"

[[shots]]
id = "s02"
keyframe = "assets/s02.png"
prompt = "One clear second action."
backend = "h3"
quality = "turbo"
'''


class StudioContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "assets").mkdir()
        (self.root / "assets/s01.png").write_bytes(b"one")
        (self.root / "assets/s02.png").write_bytes(b"two")
        self.manifest = self.root / "project.toml"
        self.manifest.write_text(MANIFEST)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_loads_valid_local_private_project(self) -> None:
        project = load_project(self.manifest, self.root)
        self.assertEqual(project.id, "demo-ad")
        self.assertEqual(project.privacy, "local-private")
        self.assertEqual(project.video_endpoint, "http://127.0.0.1:8189")
        self.assertEqual(project.image_backend, "comfyui-local")
        self.assertEqual([shot.id for shot in project.shots], ["s01", "s02"])
        self.assertEqual(project.shots[0].keyframe, self.root / "assets/s01.png")

    def test_private_project_rejects_remote_video_endpoint(self) -> None:
        self.manifest.write_text(
            MANIFEST.replace("http://127.0.0.1:8189", "https://video.example.com")
        )
        with self.assertRaisesRegex(ContractError, "localhost"):
            load_project(self.manifest, self.root)

    def test_private_project_rejects_remote_image_backend(self) -> None:
        self.manifest.write_text(MANIFEST.replace('image = "comfyui-local"', 'image = "codex"'))
        with self.assertRaisesRegex(ContractError, "image backend"):
            load_project(self.manifest, self.root)

    def test_manifest_rejects_lexical_path_traversal(self) -> None:
        self.manifest.write_text(MANIFEST.replace("assets/s01.png", "../outside.png"))
        with self.assertRaisesRegex(ContractError, "contained"):
            load_project(self.manifest, self.root)

    def test_manifest_rejects_physical_symlink_escape(self) -> None:
        outside = self.root.parent / f"{self.root.name}-outside"
        outside.mkdir()
        try:
            (outside / "ref.png").write_bytes(b"outside")
            (self.root / "assets/escape").symlink_to(outside, target_is_directory=True)
            self.manifest.write_text(
                MANIFEST.replace("assets/s01.png", "assets/escape/ref.png")
            )
            with self.assertRaisesRegex(ContractError, "contained"):
                load_project(self.manifest, self.root)
        finally:
            (outside / "ref.png").unlink(missing_ok=True)
            outside.rmdir()

    def test_run_directories_are_non_destructive_and_resumable(self) -> None:
        first = create_run_directory(self.root / "outputs", "demo-ad", "run-001")
        self.assertTrue((first / "clips").is_dir())
        with self.assertRaisesRegex(FileExistsError, "already exists"):
            create_run_directory(self.root / "outputs", "demo-ad", "run-001")
        resumed = create_run_directory(
            self.root / "outputs", "demo-ad", "run-001", resume=True
        )
        self.assertEqual(first, resumed)

    def test_plan_can_select_shots_and_skip_completed_outputs(self) -> None:
        project = load_project(self.manifest, self.root)
        run_dir = create_run_directory(self.root / "outputs", project.id, "run-001")
        completed = run_dir / "clips/s01.mp4"
        completed.write_bytes(b"complete")
        plans = plan_shots(project, run_dir, selected={"s01", "s02"}, skip_existing=True)
        self.assertEqual([plan.shot.id for plan in plans], ["s02"])
        self.assertEqual(plans[0].output_path, run_dir / "clips/s02.mp4")


class SunoBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_wav(self, path: Path) -> None:
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24_000)
            handle.writeframes(b"\x00\x00" * 2_400)

    def test_suno_export_is_an_offline_prompt_package(self) -> None:
        package = export_suno_package(
            self.root / "suno-package.json",
            title="Local cue",
            style="Dark cinematic electronic score",
            lyrics="[Instrumental]",
            source_project="demo-ad",
        )
        data = json.loads(package.read_text())
        self.assertEqual(data["mode"], "prompt-export-only")
        self.assertFalse(data["cloud_generation_authorised"])
        self.assertNotIn("api_key", json.dumps(data).lower())
        self.assertNotIn("http", json.dumps(data).lower())

    def test_suno_import_is_local_validated_and_non_destructive(self) -> None:
        source = self.root / "take.wav"
        self._write_wav(source)
        destination = self.root / "imports/take.wav"
        imported = import_suno_audio(
            source,
            destination,
            metadata={"provider": "suno", "generation_id": "manual-001"},
        )
        self.assertEqual(imported, destination)
        self.assertEqual(
            hashlib.sha256(imported.read_bytes()).hexdigest(),
            hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        receipt = json.loads(destination.with_suffix(".receipt.json").read_text())
        self.assertEqual(receipt["provider"], "suno")
        with self.assertRaises(FileExistsError):
            import_suno_audio(source, destination, metadata={"provider": "suno"})

    def test_suno_import_rejects_remote_sources(self) -> None:
        with self.assertRaisesRegex(ValueError, "local file"):
            import_suno_audio(
                "https://suno.example/take.wav",
                self.root / "take.wav",
                metadata={"provider": "suno"},
            )


if __name__ == "__main__":
    unittest.main()
