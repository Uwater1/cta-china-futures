"""Stage layout guards (design log 29).

1. Every `cta.*` / `cta_research.*` import in the repo resolves, including function-local imports
   (cli.py and the paper runner import lazily; no other test executes those lines).
2. File-relative default paths still point at the repo after the moves.
3. Import direction between production stages: data -> factor_library -> factor_combination -> execution.
"""

from __future__ import annotations

import ast
import importlib
import importlib.machinery
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_DIRS = ("src", "research", "scripts", "tests")


def _imports(path: Path) -> list[tuple[str, str | None, int]]:
    """(module, imported name or None, line) for every absolute cta/cta_research import, at any depth."""
    out: list[tuple[str, str | None, int]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [
                (a.name, None, node.lineno)
                for a in node.names
                if a.name.split(".")[0] in {"cta", "cta_research"}
            ]
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and node.module.split(".")[0] in {"cta", "cta_research"}
        ):
            out += [(node.module, a.name, node.lineno) for a in node.names]
    return out


def _spec(name: str) -> importlib.machinery.ModuleSpec | None:
    try:
        return importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError):  # missing parent package, or parent is a plain module
        return None


def test_every_import_resolves() -> None:
    files = [p for d in CODE_DIRS for p in sorted((ROOT / d).rglob("*.py"))]
    assert len(files) > 120, len(files)  # a wrong root must not pass vacuously
    bad = []
    for p in files:
        for mod, name, line in _imports(p):
            where = f"{p.relative_to(ROOT)}:{line}"
            spec = _spec(mod)
            if spec is None:
                bad.append(f"{where} no module {mod}")
                continue
            if name is None or name == "*":
                continue
            is_pkg = spec.submodule_search_locations is not None
            if is_pkg and _spec(f"{mod}.{name}") is not None:
                continue
            if not hasattr(importlib.import_module(mod), name):
                bad.append(f"{where} {mod} has no {name}")
    assert not bad, bad


def test_file_relative_paths_point_at_repo() -> None:
    from cta.config import DEFAULT_PATH as CONFIG_PATH
    from cta.data.exchanges.base import DEFAULT_ROOT
    from cta.execution.paper.book import DEFAULT_DIR
    from cta.instruments.specs import DEFAULT_PATH as SPECS_PATH

    assert CONFIG_PATH == ROOT / "configs" / "strategy.yaml"
    assert SPECS_PATH == ROOT / "configs" / "instruments.yaml"
    assert DEFAULT_ROOT == ROOT / "data" / "exchanges"
    assert DEFAULT_DIR == ROOT / "paper" / "v01"


# module prefix -> production packages it must not import
FORBIDDEN = {
    "cta.data": (
        "cta.factor_library",
        "cta.factor_combination",
        "cta.execution",
        "cta.pipeline",
        "cta.analysis",
        "cta.cli",
    ),
    "cta.factor_library": (
        "cta.factor_combination",
        "cta.execution",
        "cta.pipeline",
        "cta.analysis",
        "cta.data",
        "cta.cli",
    ),
    "cta.factor_combination": ("cta.execution", "cta.pipeline", "cta.analysis", "cta.data", "cta.cli"),
    "cta.execution.plan": ("cta.pipeline", "cta.cli"),
    "cta.execution.ledger": ("cta.pipeline", "cta.cli"),
}


def test_stage_import_direction() -> None:
    bad = []
    seen = set()
    for p in sorted((ROOT / "src" / "cta").rglob("*.py")):
        mod = ".".join(p.relative_to(ROOT / "src").with_suffix("").parts).removesuffix(".__init__")
        for prefix, forbidden in FORBIDDEN.items():
            if mod == prefix or mod.startswith(prefix + "."):
                seen.add(prefix)
                for target, _, line in _imports(p):
                    if any(target == f or target.startswith(f + ".") for f in forbidden):
                        bad.append(f"{mod}:{line} imports {target}")
    assert seen == set(FORBIDDEN), seen  # every rule matched at least one module
    assert not bad, bad
