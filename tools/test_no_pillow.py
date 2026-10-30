"""Audit every live tool and import its image dependencies with PIL forbidden.

Legacy authoring/playtest scripts execute jobs at module scope. Do not import
those entry points as jobs: import their image declarations independently, then
smoke-import the reusable localization/map modules. Also audit shell snippets.
The excluded experimental/history scripts are not supported build/tool inputs.
"""

import ast
import importlib
import importlib.abc
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIVE_ROOTS = ("tools", "story", "content", "web", "docs", "mods")


def retained_research(path):
    return False  # This published tree contains only supported tools.


sys.path.insert(0, str(ROOT))


class NoPillow(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] == "PIL":
            raise AssertionError("live tool tried to load Pillow: " + fullname)


class DependencyAudit(unittest.TestCase):
    def test_every_tool_image_import(self):
        guard = NoPillow()
        sys.meta_path.insert(0, guard)
        try:
            count = 0
            for folder in LIVE_ROOTS:
                for path in sorted((ROOT / folder).rglob("*.py")):
                    if path == Path(__file__).resolve() or retained_research(path):
                        continue
                    source = path.read_text()
                    tree = ast.parse(source, filename=str(path))
                    if folder == "tools":
                        compile(tree, str(path), "exec")
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            self.assertFalse(
                                any(a.name.split(".")[0] == "PIL" for a in node.names), str(path)
                            )
                        elif isinstance(node, ast.ImportFrom):
                            self.assertNotEqual((node.module or "").split(".")[0], "PIL", str(path))
                            if node.module == "tools.image":
                                with self.subTest(tool=str(path.relative_to(ROOT))):
                                    exec(
                                        compile(
                                            ast.Module(body=[node], type_ignores=[]),
                                            str(path),
                                            "exec",
                                        ),
                                        {},
                                    )
                                count += 1
            self.assertGreater(count, 90)
            for name in (
                "tools.image",
                "tools.localize.sized",
                "tools.localize.signs",
                "tools.localize.build",
                "tools.localize.fromjp",
                "tools.fontgen",
                "tools.atlas",
                "tools.portraits",
            ):
                with self.subTest(module=name):
                    importlib.import_module(name)
            self.assertFalse(any(n == "PIL" or n.startswith("PIL.") for n in sys.modules))
        finally:
            sys.meta_path.remove(guard)

    def test_shell_snippets(self):
        for folder in LIVE_ROOTS:
            for path in (ROOT / folder).rglob("*.sh"):
                if retained_research(path):
                    continue
                self.assertIsNone(
                    re.search(
                        r"\b(?:from\s+PIL\s+import|import\s+[^#\n]*\bPIL\b)", path.read_text()
                    ),
                    str(path),
                )

    def test_documented_experimental_commands(self):
        # Keep retained research scripts out of supported image-tool workflows.
        for root in ("docs", "tools"):
            for document in (ROOT / root).rglob("*.md"):
                if "handoff" in document.parts:
                    continue
                for name in set(
                    re.findall(r"mods/" + r"experimental/[\w./-]+\.py", document.read_text())
                ):
                    path = ROOT / name
                    if not path.is_file():
                        continue
                    for node in ast.walk(ast.parse(path.read_text())):
                        if isinstance(node, ast.Import):
                            self.assertFalse(
                                any(n.name.split(".")[0] == "PIL" for n in node.names),
                                str(document),
                            )
                        elif isinstance(node, ast.ImportFrom):
                            self.assertNotEqual(
                                (node.module or "").split(".")[0], "PIL", str(document)
                            )

    def test_experimental_not_imported(self):
        # Historical experimental scripts may retain PIL; no live import may point at them.
        for path in (ROOT / "tools").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith("mods.experimental"), str(path))


if __name__ == "__main__":
    unittest.main()
