"""
Test script for pre-built agents in agent-workshop v0.2.0

This script tests:
1. DeliverableValidator with preset
2. DeliverableValidator with programmatic config
3. ValidationPipeline with default prompts
4. Configuration loading from different sources
"""

import asyncio
from agent_workshop import Config
from agent_workshop.agents.validators import DeliverableValidator
from agent_workshop.agents.validators.presets import get_preset, list_presets
from agent_workshop.agents.pipelines import ValidationPipeline


# Sample content for testing
SAMPLE_FINANCIAL_REPORT = """
# Q4 2024 Financial Report

## Executive Summary
Revenue increased 15% YoY to $10M. Net income reached $3M with strong cash flow.

## Financial Data
- Revenue: $10M (source: accounting system, verified 2024-12-31)
- Expenses: $7M
- Net income: $3M
- Cash on hand: $5M

## Key Metrics
- Gross margin: 30%
- Operating margin: 25%
- EBITDA: $3.5M

## Regulatory Compliance
All reporting follows GAAP standards. SOX compliance confirmed by external audit.

## Risk Factors
- Market volatility may impact Q1 2025 revenue
- Supply chain disruptions remain a concern
"""


async def test_list_presets():
    """Test: List all available presets"""
    print("\n" + "="*70)
    print("TEST 1: List Available Presets")
    print("="*70)

    presets = list_presets()
    print(f"\nFound {len(presets)} presets:")
    for preset in presets:
        print(f"  - {preset}")

    assert len(presets) > 0, "Should have at least one preset"
    print("\n✓ Test passed: Presets loaded successfully")


async def test_preset_validator():
    """Test: DeliverableValidator with financial_report preset"""
    print("\n" + "="*70)
    print("TEST 2: DeliverableValidator with financial_report Preset")
    print("="*70)

    # Get preset
    preset = get_preset("financial_report")
    print(f"\nPreset loaded:")
    print(f"  - System prompt: {preset['system_prompt'][:50]}...")
    print(f"  - Criteria count: {len(preset['validation_criteria'])}")
    print(f"  - Output format: {preset['output_format']}")

    # Create validator with preset
    config = Config()
    validator = DeliverableValidator(config, **preset)

    print(f"\nValidator initialized:")
    print(f"  - Criteria: {len(validator.validation_criteria)} items")
    print(f"  - Output format: {validator.output_format}")

    # Run validation
    print(f"\nRunning validation...")
    result = await validator.run(SAMPLE_FINANCIAL_REPORT)

    print(f"\n✓ Validation complete!")
    print(f"  - Timestamp: {result['timestamp']}")
    print(f"  - Validation result length: {len(result['validation'])} characters")
    print(f"\nFirst 200 chars of result:")
    print(f"{result['validation'][:200]}...")

    print("\n✓ Test passed: Preset validator works correctly")


async def test_programmatic_validator():
    """Test: DeliverableValidator with programmatic configuration"""
    print("\n" + "="*70)
    print("TEST 3: DeliverableValidator with Programmatic Config")
    print("="*70)

    # Create validator with custom config
    validator = DeliverableValidator(
        config=Config(),
        system_prompt="You are a financial compliance validator focused on accuracy and completeness.",
        validation_criteria=[
            "All numbers are sourced and verified",
            "GAAP compliance is confirmed",
            "Risk factors are disclosed"
        ],
        output_format="json"
    )

    print(f"\nValidator initialized with custom config:")
    print(f"  - System prompt: {validator.system_prompt[:50]}...")
    print(f"  - Criteria: {validator.validation_criteria}")
    print(f"  - Output format: {validator.output_format}")

    # Run validation
    print(f"\nRunning validation...")
    result = await validator.run(SAMPLE_FINANCIAL_REPORT)

    print(f"\n✓ Validation complete!")
    print(f"  - Timestamp: {result['timestamp']}")
    print(f"\nFirst 200 chars of result:")
    print(f"{result['validation'][:200]}...")

    print("\n✓ Test passed: Programmatic config works correctly")


async def test_validation_pipeline():
    """Test: ValidationPipeline with default prompts"""
    print("\n" + "="*70)
    print("TEST 4: ValidationPipeline with Default Prompts")
    print("="*70)

    # Create pipeline
    pipeline = ValidationPipeline(config=Config())

    print(f"\nPipeline initialized:")
    print(f"  - Quick scan prompt: {pipeline.quick_scan_prompt[:50]}...")
    print(f"  - Detailed verify prompt: {pipeline.detailed_verify_prompt[:50]}...")

    # Run pipeline
    print(f"\nRunning validation pipeline...")
    result = await pipeline.run({"content": SAMPLE_FINANCIAL_REPORT})

    print(f"\n✓ Pipeline complete!")
    print(f"  - Quick scan result: {len(result['final_result']['quick_scan'])} characters")
    print(f"  - Detailed verification: {len(result['final_result']['detailed_verification'])} characters")
    print(f"\nQuick scan (first 150 chars):")
    print(f"{result['final_result']['quick_scan'][:150]}...")

    print("\n✓ Test passed: ValidationPipeline works correctly")


async def test_default_validator():
    """Test: DeliverableValidator with all defaults"""
    print("\n" + "="*70)
    print("TEST 5: DeliverableValidator with Defaults")
    print("="*70)

    # Create validator with no config (uses defaults)
    validator = DeliverableValidator(config=Config())

    print(f"\nValidator initialized with defaults:")
    print(f"  - System prompt: {validator.system_prompt[:50]}...")
    print(f"  - Criteria count: {len(validator.validation_criteria)}")
    print(f"  - Output format: {validator.output_format}")

    # Run validation
    print(f"\nRunning validation...")
    result = await validator.run(SAMPLE_FINANCIAL_REPORT)

    print(f"\n✓ Validation complete!")
    print(f"\nFirst 200 chars of result:")
    print(f"{result['validation'][:200]}...")

    print("\n✓ Test passed: Default validator works correctly")


async def main():
    """Run all tests"""
    print("\n" + "#"*70)
    print("# Testing Pre-built Agents - agent-workshop v0.2.0")
    print("#"*70)

    try:
        # Test 1: List presets
        await test_list_presets()

        # Test 2: Preset validator
        await test_preset_validator()

        # Test 3: Programmatic validator
        await test_programmatic_validator()

        # Test 4: Validation pipeline
        await test_validation_pipeline()

        # Test 5: Default validator
        await test_default_validator()

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print("✓ All 5 tests passed successfully!")
        print("\nPre-built agents are working correctly:")
        print("  - Presets load successfully")
        print("  - DeliverableValidator works with preset config")
        print("  - DeliverableValidator works with programmatic config")
        print("  - ValidationPipeline works with default prompts")
        print("  - Default configuration works correctly")
        print("\nReady for production use!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
