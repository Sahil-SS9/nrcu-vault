from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.cli import main
from pipeline.delivery import build_ffmpeg_command, export_delivery


class DeliveryCommandTests(unittest.TestCase):
    def test_horizontal_profile_is_web_compatible(self) -> None:
        command = build_ffmpeg_command(
            Path("input.mp4"), Path("output.mp4"), profile="16x9"
        )
        rendered = " ".join(command)
        self.assertIn("scale=1280:720", rendered)
        self.assertIn("yuv420p", command)
        self.assertIn("+faststart", command)

    def test_vertical_profile_uses_central_crop(self) -> None:
        command = build_ffmpeg_command(
            Path("input.mp4"), Path("output.mp4"), profile="9x16"
        )
        self.assertIn("crop=720:1280", " ".join(command))

    def test_subtitle_file_is_local_and_added_to_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subtitles = root / "captions.srt"
            subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
            command = build_ffmpeg_command(
                root / "input.mp4",
                root / "output.mp4",
                profile="16x9",
                subtitles=subtitles,
            )
            self.assertIn("subtitles=", " ".join(command))

    def test_export_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.mp4"
            destination = root / "output.mp4"
            source.write_bytes(b"source")
            destination.write_bytes(b"approved")
            with self.assertRaises(FileExistsError):
                export_delivery(source, destination, profile="16x9")

    def test_export_runs_full_decode_and_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.mp4"
            destination = root / "output.mp4"
            source.write_bytes(b"source")
            calls: list[list[str]] = []

            def fake_run(command, **kwargs):
                calls.append(command)
                if command[0] == "ffmpeg" and str(destination) in command:
                    destination.write_bytes(b"rendered")
                result = type("Result", (), {"returncode": 0, "stderr": "", "stdout": "{}"})
                return result()

            with patch("pipeline.delivery.subprocess.run", side_effect=fake_run):
                output = export_delivery(source, destination, profile="16x9")
            self.assertEqual(output, destination)
            self.assertEqual([call[0] for call in calls], ["ffmpeg", "ffmpeg", "ffprobe"])


class MediaCliTests(unittest.TestCase):
    def _run(self, args: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def test_suno_export_cli_creates_private_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lyrics = root / "lyrics.txt"
            lyrics.write_text("[Instrumental]\n")
            destination = root / "package.json"
            code, data = self._run(
                [
                    "suno-export",
                    "--destination",
                    str(destination),
                    "--title",
                    "Private cue",
                    "--style",
                    "Cinematic electronic",
                    "--lyrics-file",
                    str(lyrics),
                    "--source-project",
                    "demo-ad",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(data["mode"], "prompt-export-only")
            self.assertTrue(destination.is_file())


if __name__ == "__main__":
    unittest.main()
