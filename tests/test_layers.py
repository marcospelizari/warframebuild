"""Code structure rules (ARCHITECTURE.md, "Code structure"), checked in CI so they hold
while a task grows: every module belongs to one layer and imports only the layers listed
for it; modules stay small and are named after their job; app/data/ is gone for good."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

# Layer -> layers it may import (itself always allowed).
ALLOWED: dict[str, frozenset[str]] = {
    "domain": frozenset(),
    "parse": frozenset({"domain"}),
    "gamedata": frozenset({"domain"}),
    "optimize": frozenset({"domain", "gamedata"}),
    "pipeline": frozenset({"domain", "parse", "gamedata", "optimize"}),
    "api": frozenset({"domain", "gamedata", "optimize"}),
    "cli": frozenset({"domain", "parse", "gamedata", "optimize", "pipeline", "api"}),
}

# Module prefix -> layer; the longest matching prefix wins.
LAYER_OF: dict[str, str] = {
    "app.domain": "domain",
    "app.parse": "parse",
    "app.gamedata": "gamedata",
    "app.optimize": "optimize",
    "app.pipeline": "pipeline",
    "app.api": "api",
    "app.cli": "cli",
}

# Layers that stay pure: no file, network or process access.
PURE = frozenset({"domain", "parse"})
IO_MODULES = frozenset(
    {"os", "pathlib", "shutil", "tempfile", "io", "urllib", "http", "socket", "subprocess"}
)


def layer_of(module: str) -> str | None:
    matches = [p for p in LAYER_OF if module == p or module.startswith(p + ".")]
    return LAYER_OF[max(matches, key=len)] if matches else None


def _module_name(path: Path, root: Path) -> str:
    parts = path.relative_to(root.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(tree: ast.Module, module: str) -> list[tuple[int, str]]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: resolve against this package
                base = module.split(".")[: -node.level]
                target = ".".join([*base, node.module] if node.module else base)
            else:
                target = node.module or ""
            out.append((node.lineno, target))
    return out


def violations(root: Path = APP) -> list[str]:
    found = []
    for path in sorted(root.rglob("*.py")):
        module = _module_name(path, root)
        if module == "app":
            continue  # the root package itself holds no code
        layer = layer_of(module)
        where = path.relative_to(root.parent)
        if layer is None:
            found.append(f"{where}: belongs to no layer (add it to LAYER_OF)")
            continue
        for line, target in _imports(ast.parse(path.read_text(encoding="utf-8")), module):
            top = target.split(".")[0]
            if layer in PURE and top in IO_MODULES:
                found.append(f"{where}:{line}: {layer} must stay pure, imports {target}")
            if top != "app" or target == "app":
                continue
            other = layer_of(target)
            if other is None:
                found.append(f"{where}:{line}: imports {target}, which belongs to no layer")
            elif other != layer and other not in ALLOWED[layer]:
                found.append(f"{where}:{line}: {layer} may not import {other} ({target})")
    return found


def test_app_follows_layer_rule() -> None:
    assert violations() == []


def test_rule_catches_wrong_imports(tmp_path: Path) -> None:
    app = tmp_path / "app"
    (app / "domain").mkdir(parents=True)
    (app / "domain" / "damage.py").write_text("from app.gamedata.models import Mod\nimport os\n")
    (app / "api").mkdir()
    (app / "api" / "routes.py").write_text("from app.pipeline import refresh\n")
    (app / "stray").mkdir()
    (app / "stray" / "x.py").write_text("")
    assert violations(app) == [
        "app/api/routes.py:1: api may not import pipeline (app.pipeline)",
        "app/domain/damage.py:1: domain may not import gamedata (app.gamedata.models)",
        "app/domain/damage.py:2: domain must stay pure, imports os",
        "app/stray/x.py: belongs to no layer (add it to LAYER_OF)",
    ]


MAX_LINES = 300  # past this, a module becomes a subpackage of modules per entity (rule 4)
BANNED_NAMES = frozenset({"common", "utils", "util", "helpers", "misc"})


def structure_violations(root: Path = APP) -> list[str]:
    found = []
    if (root / "data").exists():
        found.append("app/data/: removed in step 3d; use app/gamedata/ or app/pipeline/")
    for path in sorted(root.rglob("*.py")):
        where = path.relative_to(root.parent)
        if path.stem in BANNED_NAMES or path.parent.name in BANNED_NAMES:
            found.append(f"{where}: name says nothing about its job (no common/utils/helpers)")
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > MAX_LINES:
            found.append(f"{where}: {lines} lines > {MAX_LINES}, split into a subpackage")
    return found


def test_app_follows_structure_rules() -> None:
    assert structure_violations() == []


def test_structure_rules_catch_violations(tmp_path: Path) -> None:
    app = tmp_path / "app"
    (app / "data").mkdir(parents=True)
    (app / "parse").mkdir()
    (app / "parse" / "common.py").write_text("")
    (app / "domain").mkdir()
    (app / "domain" / "damage.py").write_text("x = 1\n" * (MAX_LINES + 1))
    assert structure_violations(app) == [
        "app/data/: removed in step 3d; use app/gamedata/ or app/pipeline/",
        f"app/domain/damage.py: {MAX_LINES + 1} lines > {MAX_LINES}, split into a subpackage",
        "app/parse/common.py: name says nothing about its job (no common/utils/helpers)",
    ]
