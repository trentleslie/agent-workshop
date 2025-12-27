"""
Validates Jupyter notebooks for reproducibility, documentation quality, and data science best practices. Returns structured reports with quality scores and improvement suggestions.

Generated from blueprint: data_science_notebook_validator
Generated at: 2025-12-27T12:58:08.486296
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from agent_workshop import Agent, Config


class NotebookValidator(Agent):
    """
    Validates Jupyter notebooks for reproducibility, documentation quality, and data science best practices. Returns structured reports with quality scores and improvement suggestions.

    Output schema:
#     valid: bool
#     score: int
#     issues: list[dict]
#     suggestions: list[str]
#     summary: str
    """

    DEFAULT_SYSTEM_PROMPT = """You are an expert data scientist and notebook reviewer specializing in reproducibility, documentation quality, and best practices.

Your role is to review Jupyter notebooks and identify issues in these categories:

1. REPRODUCIBILITY - Can others run this notebook?
   - Non-linear cell execution (cells run out of order)
   - Hardcoded absolute paths
   - Missing dependency imports
   - Environment-specific code
   - Random seeds not set

2. DOCUMENTATION - Is the notebook well-documented?
   - Missing or inadequate markdown cells
   - No clear narrative structure
   - Undocumented data transformations
   - Missing section headers

3. SECURITY - Are there security concerns?
   - Hardcoded credentials or API keys
   - Sensitive data exposed in outputs
   - Insecure network calls

4. QUALITY - Is the code quality good?
   - Long cells that should be split
   - Unused imports
   - Poor variable naming
   - No error handling

Prioritize issues by severity:
- CRITICAL: Security vulnerabilities, completely broken reproducibility
- HIGH: Major reproducibility or documentation gaps
- MEDIUM: Quality issues, minor documentation gaps
- LOW: Style suggestions, nice-to-haves

Output your review as valid JSON matching the expected schema.
"""

    DEFAULT_CRITERIA = [
        "No hardcoded credentials or API keys - Security risk",
        "No absolute file paths - Breaks reproducibility on other machines",
        "Cells should appear in executable order - Prevents confusion and errors",
        "Markdown cells explain code sections - Documentation for understanding",
        "Imports are declared at the top or documented - Dependency clarity",
        "No large outputs stored in cells - Bloats notebook size",
        "Random seeds set for reproducible results - ML/statistics reproducibility",
        "Clear section structure with headers - Navigation and organization"
    ]

    DEFAULT_USER_PROMPT_TEMPLATE = """Review the following Jupyter notebook content for quality, reproducibility, and best practices.

Validation Criteria:
{criteria}

Notebook Content:
```
{content}
```

Provide your review as JSON with this structure:
{{
  "valid": boolean (true if score >= 70 and no critical issues),
  "score": integer 0-100,
  "issues": [
    {{
      "severity": "critical|high|medium|low",
      "category": "reproducibility|documentation|security|quality",
      "cell_index": number or null,
      "message": "description"
    }}
  ],
  "suggestions": ["improvement suggestion"],
  "summary": "brief assessment"
}}
"""

    def __init__(
        self,
        config: Config = None,
        system_prompt: Optional[str] = None,
        validation_criteria: Optional[List[str]] = None,
        user_prompt_template: Optional[str] = None,
    ):
        super().__init__(config)

        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.validation_criteria = validation_criteria or self.DEFAULT_CRITERIA
        self.user_prompt_template = user_prompt_template or self.DEFAULT_USER_PROMPT_TEMPLATE

    async def run(self, content: str) -> Dict[str, Any]:
        """
        Jupyter notebook content (JSON or cell text)

        Args:
            content: Jupyter notebook content (JSON or cell text)

        Returns:
            dict with analysis results
        """
        if not content:
            return {"error": "Empty input", "timestamp": datetime.now().isoformat()}

        criteria_text = "\n".join(
            [f"{i+1}. {c}" for i, c in enumerate(self.validation_criteria)]
        )

        user_prompt = self.user_prompt_template.format(
            criteria=criteria_text,
            content=content,
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = await self.complete(messages, temperature=0.3)

        return self._parse_response(result)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from LLM."""
        text = response.strip()

        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        try:
            parsed = json.loads(text)
            parsed["timestamp"] = datetime.now().isoformat()
            return parsed
        except json.JSONDecodeError:
            return {"error": "Parse failed", "raw": text[:500], "timestamp": datetime.now().isoformat()}
