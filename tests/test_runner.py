from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.cli import main
from pipeline.h3_backend import build_workflow
from pipeline.studio import ShotSpec


class H3WorkflowTests(unittest.TestCase):
    def _shot(self, quality: str) -> ShotSpec:
        return ShotSpec(
            id="shot-01",
            keyframe=Path("/tmp/frame.png"),
            prompt="One subject performs one action. No one speaks.",
            backend="h3",
            quality=quality,
        )

    def test_base_route_uses_twenty_steps_without_lora(self) -> None:
        workflow = build_workflow(self._shot("base"), 1)
        self.assertEqual(workflow["9"]["inputs"]["steps"], 20)
        self.assertNotIn("15", workflow)

    def test_workflow_uses_explicit_private_staged_image_name(self) -> None:
        workflow = build_workflow(
            self._shot("base"), 1, image_name="private-shot-01-deadbeef.png"
        )
        self.assertEqual(
            workflow["5"]["inputs"]["image"], "private-shot-01-deadbeef.png"
        )

    def test_turbo_route_uses_six_steps_and_turbo_lora(self) -> None:
        workflow = build_workflow(self._shot("turbo"), 1)
        self.assertEqual(workflow["9"]["inputs"]["steps"], 6)
        self.assertIn("turbo_v4", workflow["15"]["inputs"]["lora_name"])

    def test_preview_route_uses_four_steps_and_fasth3_lora(self) -> None:
        workflow = build_workflow(self._shot("preview"), 1)
        self.assertEqual(workflow["9"]["inputs"]["steps"], 4)
        self.assertIn("fasth3_preview", workflow["15"]["inputs"]["lora_name"])

    def test_unsupported_h3_route_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "not implemented"):
            build_workflow(self._shot("control"), 1)


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
prompt = "A second clear action."
backend = "h3"
quality = "turbo"
'''


class StudioCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "assets").mkdir()
        (self.root / "assets/s01.png").write_bytes(b"one")
        (self.root / "assets/s02.png").write_bytes(b"two")
        self.manifest = self.root / "project.toml"
        self.manifest.write_text(MANIFEST)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, args: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def test_validate_reports_local_private_contract(self) -> None:
        code, data = self._run(
            ["validate", "--manifest", str(self.manifest), "--repo-root", str(self.root)]
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["project"], "demo-ad")
        self.assertEqual(data["privacy"], "local-private")
        self.assertEqual(data["shots"], 2)

    def test_plan_creates_new_run_and_honours_shot_selection(self) -> None:
        code, data = self._run(
            [
                "plan",
                "--manifest",
                str(self.manifest),
                "--repo-root",
                str(self.root),
                "--run-id",
                "test-run",
                "--shots",
                "s02",
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual([item["id"] for item in data["plan"]], ["s02"])
        self.assertTrue((self.root / "outputs/demo-ad/test-run/clips").is_dir())


if __name__ == "__main__":
    unittest.main()
