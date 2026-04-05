"""Sandboxed Python execution helpers for scrape plugins."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_IMPORTS = {
    "json",
    "math",
    "statistics",
    "datetime",
    "re",
    "numpy",
    "pandas",
    "bs4",
}

BLOCKED_CALLS = {
    "open",
    "exec",
    "eval", 
    "compile",
    "input",
    "__import__",
    "globals",
    # Removed "locals" to allow local variable introspection in analysis
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "breakpoint",
}

BLOCKED_NAMES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "pathlib",
    "shutil",
}

BLOCKED_ATTRS = {
    "system",
    "popen",
    "spawn",
    "fork",
    "remove",
    "unlink",
    "rmdir",
    "rmtree",
    "chmod",
    "chown",
    "putenv",
    "environ",
    "walk",
    "listdir",
    "mkdir",
    "makedirs",
    "rename",
    "replace",
    "symlink",
}

DEFAULT_ANALYSIS_CODE = """
rows = payload.get("dataset_rows") or []
result = {
    "row_count": len(rows),
    "columns": sorted(list(rows[0].keys())) if rows else [],
    "summary": {},
    "source_links": payload.get("source_links") or [],
}

if rows:
    import pandas as pd
    import numpy as np

    df = pd.DataFrame(rows)
    if "gold_price_usd" in df.columns:
        series = pd.to_numeric(df["gold_price_usd"], errors="coerce").dropna()
        if len(series) > 0:
            result["summary"] = {
                "min_price": float(series.min()),
                "max_price": float(series.max()),
                "mean_price": float(series.mean()),
                "std_price": float(series.std(ddof=0)),
                "median_price": float(np.median(series.to_numpy())),
            }

html_samples = payload.get("html_samples") or {}
if html_samples:
    from bs4 import BeautifulSoup
    html_link_counts = {}
    for source, html in html_samples.items():
        soup = BeautifulSoup(html or "", "html.parser")
        html_link_counts[source] = len(soup.find_all("a"))
    result["html_link_counts"] = html_link_counts
"""


class UnsafePythonCodeError(ValueError):
    """Raised when user-provided Python code violates sandbox constraints."""


@dataclass
class SandboxExecutionResult:
    """Execution result for sandboxed Python plugin runs."""

    success: bool
    output: dict[str, Any] | None = None
    error: str | None = None
    stdout: str = ""
    stderr: str = ""
    timeout: bool = False


def _validate_code(code: str) -> None:
    """Validate user code against sandbox safety constraints."""

    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise UnsafePythonCodeError(f"Invalid Python syntax: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    raise UnsafePythonCodeError(f"Import not allowed: {alias.name}")

        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                raise UnsafePythonCodeError("Relative imports are not allowed in sandbox code")
            module = node.module or ""
            root = module.split(".")[0]
            if root not in ALLOWED_IMPORTS:
                raise UnsafePythonCodeError(f"Import not allowed: {module}")

        if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise UnsafePythonCodeError(f"Blocked name used: {node.id}")

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
                raise UnsafePythonCodeError(f"Blocked call used: {node.func.id}")
            if isinstance(node.func, ast.Attribute):
                if node.func.attr.startswith("__") or node.func.attr in BLOCKED_ATTRS:
                    raise UnsafePythonCodeError(f"Blocked attribute call: {node.func.attr}")

        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise UnsafePythonCodeError("Dunder attribute access is not allowed")


def _build_runner_script(user_code: str) -> str:
    """Wrap user code in a deterministic runner script."""

    return f"""import json
from pathlib import Path

try:
    import numpy as np  # noqa: F401
except Exception:
    np = None  # noqa: N816

try:
    import pandas as pd  # noqa: F401
except Exception:
    pd = None

try:
    from bs4 import BeautifulSoup  # noqa: F401
except Exception:
    BeautifulSoup = None

payload = json.loads(Path("input.json").read_text(encoding="utf-8"))
result = None

{user_code}

if result is None:
    raise ValueError("Sandbox code must assign a JSON-serializable value to `result`.")

print(json.dumps(result, default=str))
"""


def execute_python_sandbox(
    code: str,
    payload: dict[str, Any],
    *,
    session_id: str,
    timeout_seconds: int = 25,
) -> SandboxExecutionResult:
    """Execute validated Python code in an isolated temporary workspace."""

    _validate_code(code)

    workspace = Path(tempfile.mkdtemp(prefix=f"scraperl-sandbox-{session_id}-"))
    try:
        input_path = workspace / "input.json"
        script_path = workspace / "runner.py"
        input_path.write_text(json.dumps(payload, default=str), encoding="utf-8")
        script_path.write_text(_build_runner_script(code), encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        env.pop("PYTHONPATH", None)

        process = subprocess.run(
            [sys.executable, "-I", str(script_path)],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            check=False,
        )

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()

        if process.returncode != 0:
            return SandboxExecutionResult(
                success=False,
                error=f"Sandbox execution failed (exit {process.returncode})",
                stdout=stdout,
                stderr=stderr,
            )

        if not stdout:
            return SandboxExecutionResult(
                success=False,
                error="Sandbox execution returned empty stdout",
                stdout=stdout,
                stderr=stderr,
            )

        try:
            output = json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError as exc:
            return SandboxExecutionResult(
                success=False,
                error=f"Sandbox output was not valid JSON: {exc}",
                stdout=stdout,
                stderr=stderr,
            )

        if not isinstance(output, dict):
            output = {"result": output}

        return SandboxExecutionResult(
            success=True,
            output=output,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return SandboxExecutionResult(
            success=False,
            error="Sandbox execution timed out",
            stdout=(exc.stdout or "").strip(),
            stderr=(exc.stderr or "").strip(),
            timeout=True,
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

