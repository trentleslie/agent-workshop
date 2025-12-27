"""
Mock LLM responses for testing software_dev agents.

These fixtures simulate the JSON responses that LLMs return,
including various formats (plain JSON, markdown blocks, malformed).
"""

import json

# =============================================================================
# CodeReviewer Mock Responses
# =============================================================================

# Clean code - approved
MOCK_CODE_REVIEWER_APPROVED = json.dumps({
    "approved": True,
    "issues": [],
    "suggestions": [
        "Consider adding type hints for better maintainability",
        "A docstring would help document the function's purpose"
    ],
    "summary": "Code is clean and follows best practices. No security issues or critical problems found."
})

# Code with issues - rejected
MOCK_CODE_REVIEWER_REJECTED = json.dumps({
    "approved": False,
    "issues": [
        {
            "severity": "medium",
            "category": "code_quality",
            "line": 5,
            "message": "Function is too long and should be split into smaller functions"
        },
        {
            "severity": "low",
            "category": "style",
            "line": 12,
            "message": "Variable name 'x' is not descriptive"
        }
    ],
    "suggestions": [
        "Break down the function into smaller, single-purpose functions",
        "Use more descriptive variable names"
    ],
    "summary": "Code has quality issues that should be addressed before merging."
})

# Security issue detected - rejected
MOCK_CODE_REVIEWER_SECURITY_ISSUE = json.dumps({
    "approved": False,
    "issues": [
        {
            "severity": "critical",
            "category": "security",
            "line": 3,
            "message": "Hardcoded API key detected - this is a security vulnerability"
        }
    ],
    "suggestions": [
        "Move the API key to environment variables",
        "Use a secrets management system"
    ],
    "summary": "CRITICAL: Hardcoded credentials detected. Do not merge until resolved."
})

# Markdown-wrapped JSON response (common LLM behavior)
MOCK_CODE_REVIEWER_MARKDOWN_WRAPPED = """```json
{
    "approved": true,
    "issues": [],
    "suggestions": ["Good code overall"],
    "summary": "Clean code with no issues."
}
```"""

# Plain markdown block (no json specifier)
MOCK_CODE_REVIEWER_PLAIN_MARKDOWN = """```
{
    "approved": true,
    "issues": [],
    "suggestions": [],
    "summary": "Looks good."
}
```"""

# Malformed JSON response
MOCK_CODE_REVIEWER_MALFORMED = """
I've reviewed the code and here's my analysis:
{approved: true, issues: []}
This is not valid JSON but some LLMs might produce it.
"""

# Response with extra text before/after JSON
MOCK_CODE_REVIEWER_WITH_PREAMBLE = """
Here's my code review:

```json
{
    "approved": false,
    "issues": [{"severity": "high", "category": "security", "line": 1, "message": "Issue found"}],
    "suggestions": ["Fix the issue"],
    "summary": "Issues found"
}
```

Let me know if you have questions!
"""

# =============================================================================
# PRPipeline Mock Responses (for each step)
# =============================================================================

# Security scan step response
MOCK_PR_SECURITY_SCAN = json.dumps({
    "vulnerabilities": [
        {
            "severity": "high",
            "type": "sql_injection",
            "location": "db_query.py:45",
            "description": "User input passed directly to SQL query without sanitization"
        }
    ],
    "security_score": 3,
    "recommendations": [
        "Use parameterized queries instead of string concatenation",
        "Add input validation layer"
    ]
})

# Security scan - clean
MOCK_PR_SECURITY_SCAN_CLEAN = json.dumps({
    "vulnerabilities": [],
    "security_score": 9,
    "recommendations": [
        "Continue following secure coding practices"
    ]
})

# Quality review step response
MOCK_PR_QUALITY_REVIEW = json.dumps({
    "quality_score": 7,
    "code_smells": [
        {
            "type": "long_method",
            "location": "handler.py:100-200",
            "suggestion": "Break into smaller functions"
        }
    ],
    "test_coverage_concerns": [
        "New code paths lack unit tests"
    ],
    "maintainability_notes": [
        "Good separation of concerns",
        "Consider adding more inline comments for complex logic"
    ]
})

# Quality review - clean
MOCK_PR_QUALITY_REVIEW_CLEAN = json.dumps({
    "quality_score": 9,
    "code_smells": [],
    "test_coverage_concerns": [],
    "maintainability_notes": [
        "Excellent code structure",
        "Well documented"
    ]
})

# Summary generation step response
MOCK_PR_SUMMARY = json.dumps({
    "overall_recommendation": "request_changes",
    "summary": "This PR introduces a SQL injection vulnerability that must be fixed before merging. Code quality is acceptable but could benefit from some refactoring.",
    "critical_issues": [
        "SQL injection vulnerability in db_query.py"
    ],
    "action_items": [
        "Fix SQL injection by using parameterized queries",
        "Add unit tests for new code paths",
        "Consider breaking down long methods"
    ],
    "approval_status": False
})

# Summary - approved
MOCK_PR_SUMMARY_APPROVED = json.dumps({
    "recommendation": "approve",
    "summary": "This PR looks good! No security issues found and code quality is excellent.",
    "blocking_issues": 0,
    "approved": True
})

# =============================================================================
# Test Code Samples
# =============================================================================

# Clean Python code for testing
SAMPLE_CLEAN_CODE = '''
def calculate_area(width: float, height: float) -> float:
    """Calculate the area of a rectangle.

    Args:
        width: The width of the rectangle
        height: The height of the rectangle

    Returns:
        The area of the rectangle
    """
    if width < 0 or height < 0:
        raise ValueError("Dimensions must be non-negative")
    return width * height
'''

# Code with hardcoded secret
SAMPLE_CODE_WITH_SECRET = '''
import requests

API_KEY = "sk-1234567890abcdef"
DATABASE_PASSWORD = "super_secret_password"

def call_api():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    return requests.get("https://api.example.com", headers=headers)
'''

# Code with quality issues
SAMPLE_CODE_WITH_ISSUES = '''
def process(x):
    # TODO: fix this later
    result = []
    for i in range(len(x)):
        if x[i] > 0:
            temp = x[i] * 2
            if temp > 10:
                result.append(temp)
            else:
                result.append(x[i])
        else:
            result.append(0)
    return result
'''

# SQL injection vulnerable code
SAMPLE_SQL_INJECTION = '''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)
'''

# =============================================================================
# PRCommentProcessor Mock Responses
# =============================================================================

# Mock analysis response - can auto-fix
MOCK_COMMENT_ANALYSIS_CAN_FIX = json.dumps({
    "understood": True,
    "change_type": "refactor",
    "description": "Add type hints to function parameters",
    "affected_lines": [1, 2],
    "complexity": "simple",
    "can_auto_fix": True,
    "skip_reason": None
})

# Mock analysis response - cannot auto-fix
MOCK_COMMENT_ANALYSIS_SKIP = json.dumps({
    "understood": True,
    "change_type": "refactor",
    "description": "Major architectural change needed",
    "affected_lines": [1, 2, 3, 4, 5],
    "complexity": "complex",
    "can_auto_fix": False,
    "skip_reason": "Requires manual architectural decisions"
})

# Mock fix generation - success
MOCK_FIX_GENERATED = json.dumps({
    "success": True,
    "full_file_content": "def calculate(width: float, height: float) -> float:\n    return width * height\n",
    "changes_summary": "Added type hints to parameters and return type",
    "lines_changed": 1
})

# Mock fix generation - failure
MOCK_FIX_FAILED = json.dumps({
    "success": False,
    "skip_reason": "Unable to determine correct fix"
})

# Mock summary generation
MOCK_COMMENT_SUMMARY = json.dumps({
    "total_comments": 2,
    "applied": 1,
    "skipped": 1,
    "failed": 0,
    "summary": "Processed 2 comments from PR #123. Applied 1 fix and skipped 1 comment that required manual intervention.",
    "files_modified": ["src/utils.py"],
    "next_steps": ["Run tests", "Review applied changes", "Commit if satisfied"]
})

# Sample PR comments (simulating Greptile MCP output)
SAMPLE_PR_COMMENTS = [
    {
        "id": "comment_1",
        "body": "Please add type hints to this function",
        "path": "src/utils.py",
        "line": 1,
        "addressed": False,
        "author": "reviewer1",
        "created_at": "2024-01-15T10:00:00Z"
    },
    {
        "id": "comment_2",
        "body": "This needs major refactoring - consider using a class here",
        "path": "src/processor.py",
        "line": 50,
        "addressed": False,
        "author": "reviewer2",
        "created_at": "2024-01-15T11:00:00Z"
    },
]

# Comment without file path (should be skipped)
SAMPLE_COMMENT_NO_PATH = {
    "id": "comment_3",
    "body": "General comment about the PR",
    "path": None,
    "line": None,
    "addressed": False,
    "author": "reviewer3",
    "created_at": "2024-01-15T12:00:00Z"
}

# Sample file content for testing
SAMPLE_FILE_CONTENT = """def calculate(width, height):
    return width * height
"""
