"""Tiered verification system for validating LLM outputs and generated code.

Provides configurable depth verification from simple schema validation to
full test execution. Verification levels are cumulative - each level includes
all levels below it.

Usage:
    from agent_workshop.agents.software_dev.utils import (
        verify,
        VerificationLevel,
        VerificationConfig,
    )

    # Quick syntax check only
    result = await verify(
        file_path="src/my_module.py",
        level=VerificationLevel.SYNTAX,
    )

    # Full verification with tests
    result = await verify(
        file_path="src/my_module.py",
        level=VerificationLevel.TEST,
        config=VerificationConfig(test_timeout=120),
    )
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class VerificationLevel(IntEnum):
    """Verification depth levels, ordered by cost.

    Each level includes all levels below it.
    """

    SCHEMA = 1  # Pydantic/JSON schema validation
    SYNTAX = 2  # Python compile check
    LINT = 3  # Ruff linting
    TYPE = 4  # Mypy type checking
    TEST = 5  # Pytest execution


class VerificationConfig(BaseModel):
    """Configuration for verification execution."""

    # Test execution
    test_timeout: int = Field(
        default=60,
        description="Timeout for test execution in seconds",
    )
    test_pattern: str = Field(
        default="",
        description="Pytest pattern to filter tests (e.g., '-k test_specific')",
    )
    test_directory: str | None = Field(
        default=None,
        description="Directory containing tests (defaults to 'tests/')",
    )

    # Lint configuration
    lint_fix: bool = Field(
        default=False,
        description="Whether to apply lint fixes automatically",
    )
    lint_config: str | None = Field(
        default=None,
        description="Path to ruff configuration file",
    )

    # Type checking
    type_strict: bool = Field(
        default=False,
        description="Enable strict mode for mypy",
    )
    type_config: str | None = Field(
        default=None,
        description="Path to mypy configuration file",
    )

    # Behavior
    fail_fast: bool = Field(
        default=True,
        description="Stop verification at first failure",
    )
    working_dir: str | None = Field(
        default=None,
        description="Working directory for commands",
    )
    python_executable: str = Field(
        default="python",
        description="Python executable to use (e.g., 'python3', 'uv run python')",
    )


@dataclass
class VerificationResult:
    """Result of tiered verification.

    Contains pass/fail status for each level that was executed,
    plus detailed output and timing information.
    """

    # Overall result
    level: VerificationLevel
    passed: bool
    highest_passing_level: VerificationLevel | None = None

    # Per-tier results (None if not executed)
    schema_valid: bool | None = None
    syntax_valid: bool | None = None
    lint_valid: bool | None = None
    types_valid: bool | None = None
    tests_pass: bool | None = None

    # Error details
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Tier-specific output
    schema_output: str | None = None
    syntax_output: str | None = None
    lint_output: str | None = None
    type_output: str | None = None
    test_output: str | None = None

    # Timing
    duration_seconds: float = 0.0

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    @property
    def summary(self) -> str:
        """Human-readable summary of verification results."""
        parts = [f"Verification to {self.level.name}: {'PASSED' if self.passed else 'FAILED'}"]

        if self.highest_passing_level:
            parts.append(f"Highest passing: {self.highest_passing_level.name}")

        levels = [
            ("SCHEMA", self.schema_valid),
            ("SYNTAX", self.syntax_valid),
            ("LINT", self.lint_valid),
            ("TYPE", self.types_valid),
            ("TEST", self.tests_pass),
        ]

        status_parts = []
        for name, status in levels:
            if status is None:
                continue
            icon = "✓" if status else "✗"
            status_parts.append(f"{icon} {name}")

        if status_parts:
            parts.append(" | ".join(status_parts))

        if self.errors:
            parts.append(f"Errors: {len(self.errors)}")

        return " | ".join(parts)


async def _run_command(
    cmd: list[str],
    cwd: str | Path | None = None,
    timeout: int = 60,
) -> tuple[int, str, str]:
    """Run a command asynchronously and return exit code, stdout, stderr.
    
    Uses create_subprocess_exec which does NOT use shell interpretation,
    making it safe from command injection (equivalent to Node's execFile).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", f"Command timed out after {timeout} seconds"
    except FileNotFoundError as e:
        return -1, "", f"Command not found: {e}"


async def _validate_schema(
    data: Any,
    model_class: type[BaseModel] | None,
    result: VerificationResult,
) -> bool:
    """Validate data against a Pydantic schema."""
    if model_class is None:
        result.schema_valid = True
        result.schema_output = "No schema provided, skipping validation"
        return True

    try:
        import json

        if isinstance(data, str):
            data = json.loads(data)

        model_class.model_validate(data)
        result.schema_valid = True
        result.schema_output = "Schema validation passed"
        return True
    except Exception as e:
        result.schema_valid = False
        result.schema_output = str(e)
        result.add_error(f"Schema validation failed: {e}")
        return False


async def _check_syntax(
    file_path: Path,
    config: VerificationConfig,
    result: VerificationResult,
) -> bool:
    """Check Python syntax using py_compile."""
    if not file_path.suffix == ".py":
        result.syntax_valid = True
        result.syntax_output = f"Skipping syntax check for non-Python file: {file_path.suffix}"
        return True

    # Build command as list (safe from injection)
    if " " in config.python_executable:
        parts = config.python_executable.split()
        cmd = parts + ["-m", "py_compile", str(file_path)]
    else:
        cmd = [config.python_executable, "-m", "py_compile", str(file_path)]

    exit_code, stdout, stderr = await _run_command(
        cmd,
        cwd=config.working_dir,
        timeout=30,
    )

    if exit_code == 0:
        result.syntax_valid = True
        result.syntax_output = "Syntax check passed"
        return True
    else:
        result.syntax_valid = False
        result.syntax_output = stderr or stdout
        result.add_error(f"Syntax error: {stderr or stdout}")
        return False


async def _run_lint(
    file_path: Path,
    config: VerificationConfig,
    result: VerificationResult,
) -> bool:
    """Run ruff linting on a file."""
    if file_path.suffix not in (".py", ".pyi"):
        result.lint_valid = True
        result.lint_output = f"Skipping lint for non-Python file: {file_path.suffix}"
        return True

    cmd = ["ruff", "check", str(file_path)]

    if config.lint_fix:
        cmd.append("--fix")

    if config.lint_config:
        cmd.extend(["--config", config.lint_config])

    exit_code, stdout, stderr = await _run_command(
        cmd,
        cwd=config.working_dir,
        timeout=60,
    )

    output = stdout or stderr

    if exit_code == 0:
        result.lint_valid = True
        result.lint_output = output or "No lint issues found"
        return True
    else:
        result.lint_valid = False
        result.lint_output = output
        lines = output.strip().split("\n") if output else ["unknown error"]
        result.add_error(f"Lint failed: {lines[-1]}")
        return False


async def _run_typecheck(
    file_path: Path,
    config: VerificationConfig,
    result: VerificationResult,
) -> bool:
    """Run mypy type checking on a file."""
    if file_path.suffix not in (".py", ".pyi"):
        result.types_valid = True
        result.type_output = f"Skipping type check for non-Python file: {file_path.suffix}"
        return True

    cmd = ["mypy", str(file_path), "--ignore-missing-imports"]

    if config.type_strict:
        cmd.append("--strict")

    if config.type_config:
        cmd.extend(["--config-file", config.type_config])

    exit_code, stdout, stderr = await _run_command(
        cmd,
        cwd=config.working_dir,
        timeout=120,
    )

    output = stdout or stderr

    if exit_code == 0:
        result.types_valid = True
        result.type_output = output or "Type checking passed"
        return True
    else:
        result.types_valid = False
        result.type_output = output
        error_lines = [line for line in output.split("\n") if ": error:" in line]
        result.add_error(f"Type check failed: {len(error_lines)} error(s)")
        return False


async def _run_tests(
    file_path: Path,
    config: VerificationConfig,
    result: VerificationResult,
) -> bool:
    """Run pytest on related test files."""
    test_dir = config.test_directory
    if test_dir is None:
        working_dir = Path(config.working_dir) if config.working_dir else Path.cwd()
        for candidate in ["tests", "test", "."]:
            if (working_dir / candidate).exists():
                test_dir = candidate
                break
        else:
            test_dir = "tests"

    cmd = ["pytest", test_dir, "-v", "--tb=short"]

    if config.test_pattern:
        cmd.extend(config.test_pattern.split())

    cmd.extend(["--timeout", str(min(config.test_timeout, 300))])

    exit_code, stdout, stderr = await _run_command(
        cmd,
        cwd=config.working_dir,
        timeout=config.test_timeout + 30,
    )

    output = stdout or stderr

    if exit_code == 0:
        result.tests_pass = True
        result.test_output = output or "All tests passed"
        return True
    else:
        result.tests_pass = False
        result.test_output = output
        for line in output.split("\n"):
            if "failed" in line.lower() or "error" in line.lower():
                result.add_error(f"Tests failed: {line.strip()}")
                break
        else:
            result.add_error("Tests failed")
        return False


async def verify(
    file_path: str | Path,
    level: VerificationLevel = VerificationLevel.LINT,
    config: VerificationConfig | None = None,
    data: Any | None = None,
    schema_class: type[BaseModel] | None = None,
) -> VerificationResult:
    """Run tiered verification up to specified level.

    Verification runs from SCHEMA through the specified level,
    stopping at first failure if fail_fast is enabled.

    Args:
        file_path: Path to file to verify.
        level: Maximum verification level to run.
        config: Verification configuration (uses defaults if None).
        data: Optional data for schema validation.
        schema_class: Optional Pydantic model for schema validation.

    Returns:
        VerificationResult with details for each level executed.
    """
    import time

    start_time = time.monotonic()

    if config is None:
        config = VerificationConfig()

    file_path = Path(file_path)
    result = VerificationResult(level=level, passed=False)

    highest_passing: VerificationLevel | None = None

    # SCHEMA validation
    if level >= VerificationLevel.SCHEMA:
        passed = await _validate_schema(data, schema_class, result)
        if passed:
            highest_passing = VerificationLevel.SCHEMA
        elif config.fail_fast:
            result.duration_seconds = time.monotonic() - start_time
            result.highest_passing_level = highest_passing
            return result

    # SYNTAX check
    if level >= VerificationLevel.SYNTAX:
        passed = await _check_syntax(file_path, config, result)
        if passed:
            highest_passing = VerificationLevel.SYNTAX
        elif config.fail_fast:
            result.duration_seconds = time.monotonic() - start_time
            result.highest_passing_level = highest_passing
            return result

    # LINT check
    if level >= VerificationLevel.LINT:
        passed = await _run_lint(file_path, config, result)
        if passed:
            highest_passing = VerificationLevel.LINT
        elif config.fail_fast:
            result.duration_seconds = time.monotonic() - start_time
            result.highest_passing_level = highest_passing
            return result

    # TYPE check
    if level >= VerificationLevel.TYPE:
        passed = await _run_typecheck(file_path, config, result)
        if passed:
            highest_passing = VerificationLevel.TYPE
        elif config.fail_fast:
            result.duration_seconds = time.monotonic() - start_time
            result.highest_passing_level = highest_passing
            return result

    # TEST execution
    if level >= VerificationLevel.TEST:
        passed = await _run_tests(file_path, config, result)
        if passed:
            highest_passing = VerificationLevel.TEST

    result.highest_passing_level = highest_passing
    result.passed = highest_passing == level
    result.duration_seconds = time.monotonic() - start_time

    return result


async def verify_generated_code(
    code: str,
    level: VerificationLevel = VerificationLevel.LINT,
    config: VerificationConfig | None = None,
) -> VerificationResult:
    """Verify generated code without writing to a permanent file.

    Creates a temporary file for verification, useful for validating
    LLM-generated code before writing it to the target location.

    Args:
        code: Python source code to verify.
        level: Maximum verification level (TEST not supported).
        config: Verification configuration.

    Returns:
        VerificationResult with details for each level executed.
    """
    if level >= VerificationLevel.TEST:
        level = VerificationLevel.TYPE

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
    ) as f:
        f.write(code)
        temp_path = Path(f.name)

    try:
        return await verify(temp_path, level, config)
    finally:
        temp_path.unlink(missing_ok=True)
