#!/usr/bin/env python3
"""
Example: Generate agents from blueprints.

This example demonstrates the AgentBuilder meta-agent that generates
Python agent code from YAML blueprint specifications.

Usage:
    # Run with default example blueprint
    uv run python examples/blueprint_usage/generate_agent.py

    # Run with a specific blueprint
    uv run python examples/blueprint_usage/generate_agent.py blueprints/specs/software_dev_code_reviewer.yaml

    # Generate and write to file
    uv run python examples/blueprint_usage/generate_agent.py blueprints/specs/software_dev_code_reviewer.yaml --output generated_agent.py

Requirements:
    - agent-workshop package installed
    - YAML blueprints in blueprints/specs/
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent_workshop import Config
from agent_workshop.blueprints import (
    AgentBuilder,
    generate_agent_from_blueprint,
    load_blueprint,
    validate_blueprint,
    CodeGenerator,
    InlineCodeGenerator,
)


async def example_load_and_validate(blueprint_path: str):
    """Example: Load and validate a blueprint."""
    print("=" * 60)
    print("Example 1: Load and Validate Blueprint")
    print("=" * 60)

    try:
        # Load blueprint from YAML
        blueprint = load_blueprint(blueprint_path)
        print(f"Loaded blueprint: {blueprint.blueprint.name}")
        print(f"  Domain: {blueprint.blueprint.domain}")
        print(f"  Type: {blueprint.blueprint.type}")
        print(f"  Description: {blueprint.blueprint.description[:80]}...")

        # Validate blueprint semantics
        validation = validate_blueprint(blueprint)
        print(f"\nValidation result: {'PASS' if validation.valid else 'FAIL'}")

        if validation.errors:
            print(f"  Errors: {validation.errors}")
        if validation.warnings:
            print(f"  Warnings: {validation.warnings}")

        return blueprint

    except FileNotFoundError as e:
        print(f"ERROR: Blueprint not found: {e}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


async def example_generate_code_inline(blueprint_path: str):
    """Example: Generate code using inline templates."""
    print("\n" + "=" * 60)
    print("Example 2: Generate Code (Inline Templates)")
    print("=" * 60)

    try:
        # Load blueprint
        blueprint = load_blueprint(blueprint_path)

        # Generate using inline templates (no Jinja2 files needed)
        generator = InlineCodeGenerator()
        code = generator.generate(blueprint)

        print(f"Generated {len(code)} characters of Python code")
        print(f"\nFirst 500 characters:")
        print("-" * 40)
        print(code[:500])
        print("...")

        return code

    except Exception as e:
        print(f"ERROR: {e}")
        return None


async def example_generate_code_jinja2(blueprint_path: str):
    """Example: Generate code using Jinja2 templates."""
    print("\n" + "=" * 60)
    print("Example 3: Generate Code (Jinja2 Templates)")
    print("=" * 60)

    try:
        # Load blueprint
        blueprint = load_blueprint(blueprint_path)

        # Generate using Jinja2 templates
        generator = CodeGenerator()
        code = generator.generate(blueprint)

        print(f"Generated {len(code)} characters of Python code")
        print(f"\nFirst 500 characters:")
        print("-" * 40)
        print(code[:500])
        print("...")

        return code

    except FileNotFoundError:
        print("Jinja2 templates not found - using inline generator instead")
        return await example_generate_code_inline(blueprint_path)
    except Exception as e:
        print(f"ERROR: {e}")
        return None


async def example_agent_builder(blueprint_path: str, output_path: str | None = None):
    """Example: Use AgentBuilder meta-agent for full pipeline."""
    print("\n" + "=" * 60)
    print("Example 4: AgentBuilder Meta-Agent")
    print("=" * 60)

    try:
        # Create AgentBuilder
        config = Config()
        builder = AgentBuilder(config)

        # Run the full pipeline
        input_data = {
            "blueprint_path": blueprint_path,
            "use_inline_generator": True,  # Use inline for demo (no template deps)
        }

        if output_path:
            input_data["output_path"] = output_path
            input_data["overwrite"] = True

        print(f"Running AgentBuilder pipeline...")
        result = await builder.run(input_data)

        # Report results
        print(f"\nResult:")
        print(f"  Success: {result['success']}")

        if result["error"]:
            print(f"  Error: {result['error']}")

        if result["validation"]:
            v = result["validation"]
            print(f"  Blueprint validation: {'PASS' if v.valid else 'FAIL'}")
            if v.warnings:
                print(f"    Warnings: {v.warnings}")

        if result["code_validation"]:
            cv = result["code_validation"]
            print(f"  Code validation: {'PASS' if cv.valid else 'FAIL'}")
            if cv.warnings:
                print(f"    Warnings: {cv.warnings}")

        if result["written_path"]:
            print(f"  Written to: {result['written_path']}")

        if result["code"]:
            print(f"  Generated code length: {len(result['code'])} chars")

        return result

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def example_convenience_function(blueprint_path: str, output_path: str | None = None):
    """Example: Use convenience function for simple generation."""
    print("\n" + "=" * 60)
    print("Example 5: Convenience Function")
    print("=" * 60)

    try:
        result = await generate_agent_from_blueprint(
            blueprint_path=blueprint_path,
            output_path=output_path,
            overwrite=True,
        )

        print(f"Success: {result['success']}")
        if result['code']:
            print(f"Generated {len(result['code'])} characters")

        return result

    except Exception as e:
        print(f"ERROR: {e}")
        return None


async def main():
    """Run all examples."""
    # Determine blueprint path
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        blueprint_path = sys.argv[1]
    else:
        # Default to code_reviewer blueprint
        blueprint_path = "blueprints/specs/software_dev_code_reviewer.yaml"

    # Check for output path argument
    output_path = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    print(f"Blueprint: {blueprint_path}")
    if output_path:
        print(f"Output: {output_path}")

    # Verify blueprint exists
    if not Path(blueprint_path).exists():
        print(f"\nERROR: Blueprint file not found: {blueprint_path}")
        print("\nAvailable blueprints:")
        blueprints_dir = Path("blueprints/specs")
        if blueprints_dir.exists():
            for f in blueprints_dir.glob("*.yaml"):
                print(f"  - {f}")
        sys.exit(1)

    # Run examples
    await example_load_and_validate(blueprint_path)
    await example_generate_code_inline(blueprint_path)
    await example_generate_code_jinja2(blueprint_path)
    await example_agent_builder(blueprint_path, output_path)

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
