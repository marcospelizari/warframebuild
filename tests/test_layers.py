"""Code structure rule (ARCHITECTURE.md, "Code structure"): every module belongs to one
layer, and a layer imports only the layers listed for it. Checked statically from the
import statements, so a wrong dependency fails CI before it spreads."""

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
    # Pending move out of app/data/ (ARCHITECTURE.md lists the targets); remove each
    # line when its module moves. Do not add new modules under app/data/.
    "app.data": "pipeline",
    "app.data.models": "gamedata",
    "app.data.cli": "cli",
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
