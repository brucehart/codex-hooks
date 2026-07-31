from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "codex_hooks_installer",
    PROJECT_ROOT / "scripts" / "install.py",
)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_install_hook_preserves_other_groups_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex_home = root / "codex"
            spool_dir = root / "spool"
            codex_home.mkdir()
            other_group = {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 /other/session_end.py",
                    }
                ]
            }
            (codex_home / "hooks.json").write_text(
                json.dumps({"hooks": {"SessionEnd": [other_group]}}),
                encoding="utf-8",
            )

            installer.install_hook(codex_home, spool_dir)
            installer.install_hook(codex_home, spool_dir)
            data = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
            groups = data["hooks"]["SessionEnd"]

            self.assertEqual(groups.count(other_group), 1)
            installed_commands = [
                handler["command"]
                for group in groups
                for handler in group.get("hooks", [])
                if "codex_api_cost.py" in handler.get("command", "")
            ]
            self.assertEqual(len(installed_commands), 1)
            self.assertTrue((codex_home / "hooks.json.bak").exists())

    def test_replace_managed_block_updates_in_place(self) -> None:
        first = (
            "before\n"
            f"{installer.START_MARKER}\nold\n{installer.END_MARKER}\n"
            "after\n"
        )
        replacement = (
            f"{installer.START_MARKER}\nnew\n{installer.END_MARKER}\n"
        )
        result = installer.replace_managed_block(first, replacement)

        self.assertEqual(result.count(installer.START_MARKER), 1)
        self.assertIn("new", result)
        self.assertNotIn("old", result)
        self.assertIn("before", result)
        self.assertIn("after", result)


if __name__ == "__main__":
    unittest.main()
