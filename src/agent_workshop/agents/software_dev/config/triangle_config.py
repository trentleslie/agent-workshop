"""Project-level configuration for Triangle workflow.

This module provides a configuration system that allows each project to
customize Triangle's behavior via a `.triangle.toml` file. If no config
exists, sensible defaults are used.

Example `.triangle.toml`:

    [verification]
    fix_command = "./scripts/fix.sh"
    check_command = "./scripts/check.sh"

    [style]
    formatter = "black"
    guidelines_file = "CONTRIBUTING.md"

    [commits]
    link_pattern = "Closes #{issue}"
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class VerificationConfig(BaseModel):
    """Verification strategy configuration.

    Attributes:
        fix_command: Optional command to auto-fix issues (e.g., "./scripts/fix.sh")
        check_command: Optional command to run checks (e.g., "./scripts/check.sh")
        fallback_tools: Tools to use when no scripts exist
    """

    fix_command: Optional[str] = None
    check_command: Optional[str] = None
    fallback_tools: list[str] = Field(default=["ruff", "black", "pyright"])


class StyleConfig(BaseModel):
    """Code style configuration.

    Attributes:
        formatter: Code formatter name (e.g., "black", "ruff")
        linter: Linter name (e.g., "ruff", "flake8")
        type_checker: Type checker name (e.g., "pyright", "mypy")
        guidelines_file: Optional path to project guidelines (injected into prompts)
        line_length: Maximum line length for formatting
    """

    formatter: str = "black"
    linter: str = "ruff"
    type_checker: str = "pyright"
    guidelines_file: Optional[str] = None
    line_length: int = 88


class CommitConfig(BaseModel):
    """Commit message configuration.

    Attributes:
        convention: Commit message convention ("conventional", "angular", "none")
        link_pattern: Pattern for linking issues in PR body (e.g., "Closes #{issue}")
    """

    convention: str = "conventional"
    link_pattern: str = "Closes #{issue}"


class TriangleConfig(BaseModel):
    """Full Triangle workflow configuration.

    Aggregates all configuration sections for the Triangle workflow.
    If no `.triangle.toml` exists in a project, defaults are used.
    """

    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    style: StyleConfig = Field(default_factory=StyleConfig)
    commits: CommitConfig = Field(default_factory=CommitConfig)


# Cache to avoid re-reading config file on every call
_config_cache: dict[str, TriangleConfig] = {}


def load_triangle_config(working_dir: str | Path) -> TriangleConfig:
    """Load .triangle.toml from project root, or return defaults (cached).

    Args:
        working_dir: Path to the project root directory

    Returns:
        TriangleConfig with project settings or defaults

    Example:
        config = load_triangle_config("/path/to/project")
        if config.verification.check_command:
            # Use project's check script
            run(config.verification.check_command)
    """
    key = str(Path(working_dir).resolve())

    if key in _config_cache:
        return _config_cache[key]

    config_path = Path(working_dir) / ".triangle.toml"

    if not config_path.exists():
        config = TriangleConfig()  # Use defaults
    else:
        # tomllib is in stdlib for Python 3.11+
        try:
            import tomllib
        except ImportError:
            # Fallback for Python 3.10
            import tomli as tomllib  # type: ignore[import-not-found]

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        config = TriangleConfig(
            verification=VerificationConfig(**data.get("verification", {})),
            style=StyleConfig(**data.get("style", {})),
            commits=CommitConfig(**data.get("commits", {})),
        )

    _config_cache[key] = config
    return config


def clear_config_cache() -> None:
    """Clear the config cache.

    Useful for testing or when config files have been modified.
    """
    _config_cache.clear()
