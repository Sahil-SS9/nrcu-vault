from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.runtime_preflight import PreflightError, verify_runtime


class RuntimePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.core = self.root / "core"
        self.plugin = self.root / "plugin"
        self.core.mkdir()
        self.plugin.mkdir()
        self.model = self.root / "model.safetensors"
        self.model.write_bytes(b"model")
        self.lock = self.root / "h3.lock.json"
        self.lock.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "endpoint": "http://127.0.0.1:8189",
                    "comfyui": {
                        "path": str(self.core),
                        "commit": "core-sha",
                        "version": "0.33.0",
                    },
                    "plugins": [
                        {"name": "plugin", "path": str(self.plugin), "commit": "plugin-sha"}
                    ],
                    "models": [
                        {
                            "name": "model",
                            "path": str(self.model),
                            "size": 5,
                            "sha256": "9372c470eeadd5ec6f6bf4b9f6f352de32bcbf2b785d7c4f0f9f0635d6a0d6e4",
                        }
                    ],
                    "required_nodes": ["MiniMaxH3ImageToVideo", "H3LongVideos"],
                }
            )
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _fetch(self, path: str) -> dict:
        if path == "/system_stats":
            return {"system": {"comfyui_version": "0.33.0"}}
        if path == "/object_info":
            return {"MiniMaxH3ImageToVideo": {}, "H3LongVideos": {}}
        if path == "/queue":
            return {"queue_running": [], "queue_pending": []}
        raise AssertionError(path)

    def _git_head(self, path: Path) -> str:
        return "core-sha" if path == self.core else "plugin-sha"

    def test_preflight_accepts_matching_local_runtime(self) -> None:
        report = verify_runtime(
            self.lock,
            fetch_json=self._fetch,
            git_head=self._git_head,
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["queue"], {"running": 0, "pending": 0})

    def test_preflight_rejects_remote_endpoint(self) -> None:
        data = json.loads(self.lock.read_text())
        data["endpoint"] = "https://video.example.com"
        self.lock.write_text(json.dumps(data))
        with self.assertRaisesRegex(PreflightError, "localhost"):
            verify_runtime(self.lock, fetch_json=self._fetch, git_head=self._git_head)

    def test_preflight_rejects_missing_required_node(self) -> None:
        def fetch(path: str) -> dict:
            if path == "/object_info":
                return {"MiniMaxH3ImageToVideo": {}}
            return self._fetch(path)

        with self.assertRaisesRegex(PreflightError, "H3LongVideos"):
            verify_runtime(self.lock, fetch_json=fetch, git_head=self._git_head)

    def test_preflight_rejects_model_size_drift(self) -> None:
        data = json.loads(self.lock.read_text())
        data["models"][0]["size"] = 99
        self.lock.write_text(json.dumps(data))
        with self.assertRaisesRegex(PreflightError, "size drift"):
            verify_runtime(self.lock, fetch_json=self._fetch, git_head=self._git_head)

    def test_hash_check_rejects_digest_drift(self) -> None:
        data = json.loads(self.lock.read_text())
        data["models"][0]["sha256"] = "0" * 64
        self.lock.write_text(json.dumps(data))
        with self.assertRaisesRegex(PreflightError, "hash drift"):
            verify_runtime(
                self.lock,
                check_hashes=True,
                fetch_json=self._fetch,
                git_head=self._git_head,
            )


if __name__ == "__main__":
    unittest.main()
