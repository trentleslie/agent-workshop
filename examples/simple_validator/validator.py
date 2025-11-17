"""
Simple Deliverable Validator Example

Demonstrates basic usage of agent-workshop for automated validation.
Pattern: Single-message (input → output)
"""

import asyncio
from typing import Any

from agent_workshop import Agent, Config


class DeliverableValidator(Agent):
    """
    Simple validator for research deliverables.

    Validates:
    - Reports
    - Analysis documents
    - Research findings
    - Data summaries

    Returns structured validation results.
    """

    async def run(self, content: str, validation_type: str = "general") -> dict[str, Any]:
        """
        Validate a deliverable.

        Args:
            content: Deliverable content to validate
            validation_type: Type of validation (general, technical, statistical)

        Returns:
            Validation results dictionary
        """
        # Customize prompt based on validation type
        prompts = {
            "general": self._general_validation_prompt(content),
            "technical": self._technical_validation_prompt(content),
            "statistical": self._statistical_validation_prompt(content),
        }

        prompt = prompts.get(validation_type, prompts["general"])

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert validator for research deliverables. "
                    "Provide structured, actionable feedback."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        # Single LLM call (automatically traced with Langfuse)
        result = await self.complete(messages, temperature=0.3)

        return {
            "validation_result": result,
            "validation_type": validation_type,
            "status": "completed",
            "provider": self.provider_name,
            "model": self.model_name,
        }

    def _general_validation_prompt(self, content: str) -> str:
        """Generate general validation prompt."""
        return f"""
Please validate this deliverable and provide feedback on:

1. **Clarity**: Is the content clear and well-organized?
2. **Completeness**: Are all necessary sections included?
3. **Accuracy**: Are there any obvious errors or inconsistencies?
4. **Quality**: Overall quality assessment

Deliverable:
{content}

Provide your validation in the following format:
- Issues Found: [list any issues]
- Strengths: [list strengths]
- Recommendations: [list recommendations]
- Overall Assessment: [pass/needs revision/fail]
"""

    def _technical_validation_prompt(self, content: str) -> str:
        """Generate technical validation prompt."""
        return f"""
Please perform technical validation of this deliverable, focusing on:

1. **Technical Accuracy**: Are technical claims correct?
2. **Methodology**: Is the approach sound?
3. **Assumptions**: Are assumptions clearly stated and reasonable?
4. **Reproducibility**: Can findings be reproduced?

Deliverable:
{content}

Provide detailed technical feedback.
"""

    def _statistical_validation_prompt(self, content: str) -> str:
        """Generate statistical validation prompt."""
        return f"""
Please validate the statistical analysis in this deliverable:

1. **Statistical Methods**: Are appropriate methods used?
2. **Data Quality**: Is the data sufficient?
3. **Results Interpretation**: Are results correctly interpreted?
4. **Significance**: Are p-values and confidence intervals appropriate?

Deliverable:
{content}

Provide statistical validation feedback.
"""


async def validate_single_deliverable():
    """
    Example: Validate a single deliverable.
    """
    print("=== Single Deliverable Validation ===\n")

    # Sample deliverable content
    deliverable = """
    Research Report: AI Agent Performance Analysis

    Executive Summary:
    We analyzed 1,000 AI agent interactions across 3 different models.
    Performance varied significantly by task type.

    Key Findings:
    - Model A: 85% accuracy on simple tasks, 60% on complex tasks
    - Model B: 75% accuracy on simple tasks, 70% on complex tasks
    - Model C: 90% accuracy on simple tasks, 55% on complex tasks

    Methodology:
    Random sampling of production interactions over 30 days.
    Tasks categorized by complexity using automated classification.

    Conclusion:
    Model selection should be based on expected task complexity.
    Model C recommended for simple, high-volume tasks.
    Model B recommended for complex, varied workloads.
    """

    # Create validator with auto-configured environment
    config = Config()
    validator = DeliverableValidator(config)

    print(f"Provider: {validator.provider_name}")
    print(f"Model: {validator.model_name}")
    print(f"Environment: {config.agent_workshop_env.value}\n")

    # Perform validation
    result = await validator.run(deliverable, validation_type="general")

    print("Validation Result:")
    print("-" * 80)
    print(result["validation_result"])
    print("-" * 80)
    print(f"\nStatus: {result['status']}")
    print(f"Type: {result['validation_type']}")

    # Show cost estimation (for development mode)
    if validator.provider_name == "claude_sdk":
        input_tokens = validator.estimate_tokens(deliverable)
        output_tokens = validator.estimate_tokens(result["validation_result"])
        estimated_cost = validator.estimate_cost(input_tokens, output_tokens)
        print(f"\nProjected API Cost: ${estimated_cost:.6f}")


async def batch_validate_deliverables():
    """
    Example: Batch validate multiple deliverables.

    Perfect for:
    - CI/CD pipelines
    - Scheduled validation jobs
    - Processing queues
    """
    print("\n\n=== Batch Validation ===\n")

    deliverables = [
        ("Report A", "Brief analysis of customer churn rates..."),
        ("Report B", "Statistical analysis of A/B test results..."),
        ("Report C", "Technical documentation for API endpoints..."),
    ]

    config = Config()
    validator = DeliverableValidator(config)

    for name, content in deliverables:
        print(f"Validating: {name}...")
        result = await validator.run(content, validation_type="general")
        print(f"  Status: {result['status']}")
        print()

    print("Batch validation completed!")
    print("\nView full traces in Langfuse dashboard:")
    print(f"  {config.langfuse_host}")


async def main():
    """
    Run all examples.
    """
    # Example 1: Single validation
    await validate_single_deliverable()

    # Example 2: Batch validation
    await batch_validate_deliverables()


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
