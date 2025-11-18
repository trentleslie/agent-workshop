"""
Preset configurations for DeliverableValidator.

This module provides pre-configured validation setups for common use cases.
Each preset includes system prompts, validation criteria, and output format settings.

Available Presets:
    - financial_report: For financial reports and statements
    - research_paper: For academic research papers
    - technical_spec: For technical documentation and specifications
    - general: General-purpose validation (same as defaults)
"""

from typing import Dict

PRESETS: Dict[str, Dict] = {
    "financial_report": {
        "system_prompt": """You are a financial report validator with expertise in:
- GAAP/IFRS accounting standards
- Financial statement accuracy and completeness
- Regulatory compliance requirements (SEC, SOX, etc.)
- Financial data verification and reconciliation

Provide thorough, compliance-focused feedback that ensures regulatory standards are met.""",

        "validation_criteria": [
            "Executive summary clearly states financial position and key metrics",
            "All financial data includes verifiable sources and is reconciled",
            "Calculations are accurate, documented, and follow accounting standards",
            "Regulatory compliance statements and disclosures are present",
            "Risk factors and material events are disclosed appropriately",
            "Financial statements follow required format (Balance Sheet, Income Statement, Cash Flow)",
        ],

        "output_format": "json"
    },

    "research_paper": {
        "system_prompt": """You are an academic research validator with expertise in:
- Research methodology and scientific rigor
- Citation standards (APA, MLA, Chicago, etc.)
- Academic writing conventions
- Reproducibility and transparency
- Peer review standards

Provide constructive feedback that improves research quality and academic integrity.""",

        "validation_criteria": [
            "Abstract summarizes research question, methods, findings, and implications clearly",
            "Literature review is comprehensive and properly cited",
            "Methodology is detailed, reproducible, and scientifically sound",
            "Results are presented clearly with appropriate statistical analysis",
            "Discussion interprets findings and acknowledges limitations",
            "References are complete, properly formatted, and support claims",
            "Figures and tables are clear, labeled, and referenced in text",
        ],

        "output_format": "detailed"
    },

    "technical_spec": {
        "system_prompt": """You are a technical documentation validator with expertise in:
- Software architecture and system design
- API documentation standards
- Technical writing best practices
- Security and compliance requirements
- Software development lifecycle (SDLC)

Provide technical feedback that ensures specifications are clear, complete, and implementable.""",

        "validation_criteria": [
            "Requirements are specific, measurable, and testable (SMART criteria)",
            "Architecture diagrams are included, accurate, and explain system components",
            "API documentation is complete with endpoints, parameters, and examples",
            "Security considerations, authentication, and authorization are addressed",
            "Error handling, edge cases, and failure modes are documented",
            "Performance requirements and scalability considerations are specified",
            "Dependencies, integrations, and third-party services are listed",
        ],

        "output_format": "detailed"
    },

    "marketing_content": {
        "system_prompt": """You are a marketing content validator with expertise in:
- Brand voice and messaging consistency
- Target audience alignment
- SEO best practices
- Call-to-action (CTA) effectiveness
- Compliance with advertising standards

Provide marketing-focused feedback that improves engagement and conversion.""",

        "validation_criteria": [
            "Message aligns with brand voice and positioning",
            "Content addresses target audience pain points and needs",
            "Value proposition is clear and compelling",
            "Call-to-action (CTA) is present, clear, and actionable",
            "SEO keywords are naturally integrated",
            "Content is scannable with clear headers and bullet points",
            "Claims are supported and compliant with advertising standards",
        ],

        "output_format": "detailed"
    },

    "legal_document": {
        "system_prompt": """You are a legal document validator with expertise in:
- Legal writing standards and conventions
- Contract structure and clarity
- Regulatory compliance
- Risk identification
- Plain language drafting

Provide legal-focused feedback that improves clarity, completeness, and enforceability.""",

        "validation_criteria": [
            "Document purpose and parties are clearly identified",
            "All defined terms are used consistently throughout",
            "Rights, obligations, and remedies are clearly stated",
            "Governing law and jurisdiction are specified",
            "Signature and execution requirements are present",
            "Compliance with relevant regulations is addressed",
            "Potential ambiguities or conflicts are minimized",
        ],

        "output_format": "detailed"
    },

    "general": {
        "system_prompt": """You are an expert deliverable validator.
Your role is to assess documents for completeness, clarity, and quality.
Provide constructive, actionable feedback.""",

        "validation_criteria": [
            "Clarity and structure",
            "Completeness of information",
            "Grammar and formatting",
        ],

        "output_format": "detailed"
    },
}


def get_preset(preset_name: str) -> Dict:
    """
    Get a preset configuration by name.

    Args:
        preset_name: Name of the preset to retrieve

    Returns:
        Dictionary with system_prompt, validation_criteria, and output_format

    Raises:
        ValueError: If preset_name is not found

    Example:
        >>> from agent_workshop.agents.validators.presets import get_preset
        >>> preset = get_preset("financial_report")
        >>> print(preset["system_prompt"])
        You are a financial report validator...
    """
    if preset_name not in PRESETS:
        raise ValueError(
            f"Unknown preset: '{preset_name}'. "
            f"Available presets: {', '.join(PRESETS.keys())}"
        )
    return PRESETS[preset_name].copy()  # Return a copy to avoid mutations


def list_presets() -> list[str]:
    """
    List all available preset names.

    Returns:
        List of preset names

    Example:
        >>> from agent_workshop.agents.validators.presets import list_presets
        >>> print(list_presets())
        ['financial_report', 'research_paper', 'technical_spec', ...]
    """
    return list(PRESETS.keys())


def get_preset_info(preset_name: str) -> Dict[str, str]:
    """
    Get information about a preset without loading the full configuration.

    Args:
        preset_name: Name of the preset

    Returns:
        Dictionary with preset information

    Example:
        >>> info = get_preset_info("financial_report")
        >>> print(info["criteria_count"])
        6
    """
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown preset: '{preset_name}'")

    preset = PRESETS[preset_name]
    return {
        "name": preset_name,
        "criteria_count": len(preset["validation_criteria"]),
        "output_format": preset["output_format"],
        "first_criterion": preset["validation_criteria"][0] if preset["validation_criteria"] else None,
    }
