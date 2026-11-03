import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src/supportflow_ai"


def test_domain_and_application_have_no_framework_or_infrastructure_imports():
    forbidden = (
        "fastapi",
        "starlette",
        "sqlalchemy",
        "torch",
        "transformers",
        "supportflow_ai.api",
        "supportflow_ai.adapters",
        "supportflow_ai.config",
    )
    for layer in ("domain", "application", "ports"):
        for file in (ROOT / layer).rglob("*.py"):
            tree = ast.parse(file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                else:
                    continue
                for imported in modules:
                    assert not any(
                        imported == name or imported.startswith(name + ".") for name in forbidden
                    ), f"Forbidden import {imported} in {file}"
