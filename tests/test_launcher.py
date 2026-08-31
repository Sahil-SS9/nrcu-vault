from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "runtime" / "start-h3-local.sh"


class H3LauncherTests(unittest.TestCase):
    def test_dry_run_supports_isolated_temp_and_database(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "H3_DRY_RUN": "1",
                "H3_PORT": "8190",
                "H3_TEMP": "/tmp/nrcu-h3-launch-proof",
                "H3_DATABASE_URL": "sqlite:///:memory:",
            }
        )
        result = subprocess.run(
            [str(LAUNCHER)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--port 8190", result.stdout)
        self.assertIn("--temp-directory /tmp/nrcu-h3-launch-proof", result.stdout)
        self.assertIn("--database-url sqlite:///:memory:", result.stdout)

    def test_rejects_non_sqlite_database_url(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "H3_DRY_RUN": "1",
                "H3_DATABASE_URL": "postgresql://db.example.invalid/comfyui",
            }
        )
        result = subprocess.run(
            [str(LAUNCHER)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("SQLite", result.stderr)


if __name__ == "__main__":
    unittest.main()
