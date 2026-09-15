"""Offline syntax and source-policy checks using Python's standard library."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPES = ("kittyscape", "packaging", "scripts", "tests")
BRANCHES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp)


def function_issues(node):
    complexity = 1 + sum(isinstance(child, BRANCHES) for child in ast.walk(node))
    complexity += sum(len(child.values) - 1 for child in ast.walk(node) if isinstance(child, ast.BoolOp))
    if complexity > 8:
        yield f"{node.name}: complexity {complexity} exceeds 8"
    if node.end_lineno - node.lineno + 1 > 200:
        yield f"{node.name}: function exceeds 200 lines"
    parameters = node.args.posonlyargs + node.args.args
    if len(parameters) > 5:
        yield f"{node.name}: positional parameters exceed 5"


def duplicate_definitions(node):
    seen = set()
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if child.name in seen:
                yield f"duplicate definition {child.name}"
            seen.add(child.name)


def source_issues(path):
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    compile(tree, str(path), "exec", dont_inherit=True)
    for line, value in enumerate(text.splitlines(), 1):
        if len(value) > 150:
            yield f"{line}: line exceeds 150 characters"
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for issue in function_issues(node):
                yield f"{node.lineno}: {issue}"
        if isinstance(node, (ast.Module, ast.ClassDef)):
            yield from duplicate_definitions(node)


def main():
    files = [ROOT / "setup.py"]
    for scope in SCOPES:
        files.extend(sorted((ROOT / scope).rglob("*.py")))
    failures = []
    for path in files:
        failures.extend(f"{path.relative_to(ROOT)}:{issue}" for issue in source_issues(path))
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Static checks passed for {len(files)} Python files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
