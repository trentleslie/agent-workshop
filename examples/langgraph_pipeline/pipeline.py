"""
LangGraph Multi-Step Validation Pipeline Example

Demonstrates multi-step agent workflows with LangGraph.
Pattern: One input → Orchestrated steps → One output
"""

import asyncio
from typing import Any

from langgraph.graph import END, StateGraph

from agent_workshop import Config
from agent_workshop.workflows import LangGraphAgent


class ValidationPipeline(LangGraphAgent):
    """
    Multi-step validation pipeline using LangGraph.

    Workflow:
    1. Quick Scan - Fast check for obvious issues
    2. Deep Analysis - Thorough analysis based on scan
    3. Final Verification - Verify and generate report

    Each step is traced separately in Langfuse, allowing
    you to see cost and performance breakdown.
    """

    def build_graph(self) -> StateGraph:
        """
        Build the validation workflow graph.

        State keys:
        - content: Input content to validate
        - scan_result: Result from quick scan
        - analysis_result: Result from deep analysis
        - final_report: Final verification report
        """
        workflow = StateGraph(dict)

        # Define workflow steps
        workflow.add_node("quick_scan", self.quick_scan)
        workflow.add_node("deep_analysis", self.deep_analysis)
        workflow.add_node("final_verification", self.final_verification)

        # Define workflow flow
        workflow.add_edge("quick_scan", "deep_analysis")
        workflow.add_edge("deep_analysis", "final_verification")
        workflow.add_edge("final_verification", END)

        # Set entry point
        workflow.set_entry_point("quick_scan")

        return workflow.compile()

    async def quick_scan(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Step 1: Quick scan for obvious issues.

        Fast, high-level check to identify major problems.
        """
        content = state["content"]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are performing a quick scan for obvious issues. "
                    "Be fast and focus on major problems only."
                ),
            },
            {
                "role": "user",
                "content": f"""
Quick scan this deliverable for obvious issues:

{content}

Check for:
1. Missing critical sections
2. Obvious errors or typos
3. Formatting problems
4. Incomplete sentences

Provide brief findings.
""",
            },
        ]

        # LLM call (automatically traced)
        result = await self.provider.complete(messages, temperature=0.2, max_tokens=500)

        return {
            **state,
            "scan_result": result,
        }

    async def deep_analysis(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Step 2: Deep analysis based on scan results.

        Thorough analysis of areas identified in quick scan.
        """
        content = state["content"]
        scan_result = state["scan_result"]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are performing deep analysis of a deliverable. "
                    "Be thorough and analytical."
                ),
            },
            {
                "role": "user",
                "content": f"""
Perform deep analysis of this deliverable.

Quick Scan Results:
{scan_result}

Full Deliverable:
{content}

Analyze:
1. Technical accuracy and methodology
2. Logical flow and argumentation
3. Data quality and interpretation
4. Clarity and comprehensiveness

Provide detailed findings with specific examples.
""",
            },
        ]

        # LLM call (automatically traced)
        result = await self.provider.complete(
            messages, temperature=0.3, max_tokens=2000
        )

        return {
            **state,
            "analysis_result": result,
        }

    async def final_verification(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Step 3: Final verification and report generation.

        Synthesize findings and generate final report.
        """
        scan_result = state["scan_result"]
        analysis_result = state["analysis_result"]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are generating a final validation report. "
                    "Be clear, actionable, and conclusive."
                ),
            },
            {
                "role": "user",
                "content": f"""
Generate final validation report based on these findings:

Quick Scan:
{scan_result}

Deep Analysis:
{analysis_result}

Provide:
1. Executive Summary
2. Key Issues (prioritized)
3. Recommendations
4. Overall Assessment (PASS / NEEDS REVISION / FAIL)
5. Next Steps

Format as a clear, actionable report.
""",
            },
        ]

        # LLM call (automatically traced)
        result = await self.provider.complete(messages, temperature=0.3, max_tokens=1500)

        return {
            **state,
            "final_report": result,
        }


async def validate_with_pipeline():
    """
    Example: Validate a deliverable using multi-step pipeline.
    """
    print("=== Multi-Step Validation Pipeline ===\n")

    # Sample deliverable
    deliverable = """
    Research Analysis: Customer Retention Study

    We analyzed customer behavior over Q1-Q3 2024.

    Key findings:
    - Retention rate: 78%
    - Churn primarily in month 3
    - Support tickets correlate with churn

    The data shows customers who contact support are 2x more likely
    to churn within 30 days.

    Recommendation: Improve support response times.
    """

    # Create pipeline with auto-configured environment
    config = Config()
    pipeline = ValidationPipeline(config)

    print(f"Provider: {pipeline.provider_name}")
    print(f"Model: {pipeline.model_name}")
    print(f"Environment: {config.agent_workshop_env.value}\n")

    # Run workflow (single invocation, multiple steps internally)
    print("Running validation pipeline...")
    result = await pipeline.run({"content": deliverable})

    # Display results from each step
    print("\n" + "=" * 80)
    print("STEP 1: QUICK SCAN")
    print("=" * 80)
    print(result.get("scan_result", "No result"))

    print("\n" + "=" * 80)
    print("STEP 2: DEEP ANALYSIS")
    print("=" * 80)
    print(result.get("analysis_result", "No result"))

    print("\n" + "=" * 80)
    print("STEP 3: FINAL REPORT")
    print("=" * 80)
    print(result.get("final_report", "No result"))

    print("\n" + "=" * 80)
    print("\nWorkflow completed successfully!")
    print(f"\nView full workflow trace in Langfuse: {config.langfuse_host}")


class IterativeRefinementPipeline(LangGraphAgent):
    """
    Example: Iterative refinement workflow.

    Shows how to use conditional edges for dynamic routing.
    """

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(dict)

        workflow.add_node("generate", self.generate_draft)
        workflow.add_node("review", self.review_draft)
        workflow.add_node("refine", self.refine_draft)
        workflow.add_node("finalize", self.finalize_draft)

        # Conditional routing based on review
        def should_refine(state):
            review = state.get("review_result", "")
            return "needs improvement" in review.lower()

        workflow.add_edge("generate", "review")
        workflow.add_conditional_edges(
            "review", should_refine, {True: "refine", False: "finalize"}
        )
        workflow.add_edge("refine", "review")  # Loop back for re-review
        workflow.add_edge("finalize", END)

        workflow.set_entry_point("generate")

        return workflow.compile()

    async def generate_draft(self, state):
        prompt = state.get("prompt", "")
        previous_draft = state.get("refined_draft", "")

        if previous_draft:
            content = f"Refine this draft:\n{previous_draft}"
        else:
            content = f"Generate draft for:\n{prompt}"

        result = await self.provider.complete(
            [{"role": "user", "content": content}], max_tokens=1000
        )

        return {**state, "draft": result}

    async def review_draft(self, state):
        draft = state["draft"]
        result = await self.provider.complete(
            [
                {
                    "role": "user",
                    "content": f"Review this draft and identify improvements:\n{draft}",
                }
            ],
            max_tokens=500,
        )

        return {**state, "review_result": result}

    async def refine_draft(self, state):
        draft = state["draft"]
        review = state["review_result"]

        result = await self.provider.complete(
            [
                {
                    "role": "user",
                    "content": f"Refine this draft based on feedback:\n\nDraft:\n{draft}\n\nFeedback:\n{review}",
                }
            ],
            max_tokens=1000,
        )

        return {**state, "refined_draft": result, "draft": result}

    async def finalize_draft(self, state):
        draft = state["draft"]
        return {**state, "final_draft": draft, "status": "completed"}


async def main():
    """
    Run all pipeline examples.
    """
    # Example 1: Multi-step validation pipeline
    await validate_with_pipeline()

    # Add more examples as needed
    # await iterative_refinement_example()


if __name__ == "__main__":
    asyncio.run(main())
