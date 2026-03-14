from typing import Optional
import anthropic
from structlog import get_logger

logger = get_logger()

class LLMClient:
    """Interface for the LLM used for code reasoning and fix generation."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20240620"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate_fix(self, context: str, message: str, issue_type: str) -> Optional[str]:
        """Generates a code fix based on context and finding message."""
        logger.info("Generating fix via LLM", model=self.model, type=issue_type)
        
        prompt = f"""
You are an expert software engineer specializing in security and code quality.
You are tasked with fixing a {issue_type} in the following code snippet.

FINDING MESSAGE:
{message}

CODE CONTEXT:
```
{context}
```

INSTRUCTIONS:
1. Analyze the finding and the code.
2. Provide ONLY the corrected code for the snippet provided.
3. Do not include any explanations or markdown formatting other than the code itself.
4. Ensure the fix follows best practices and doesn't introduce new issues.

FIXED CODE:
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            # Extracted content (simplified)
            fixed_code = response.content[0].text.strip()
            # Basic cleanup if model includes markdown
            if "```" in fixed_code:
                fixed_code = fixed_code.split("```")[1].strip()
                if fixed_code.startswith("python") or fixed_code.startswith("javascript"):
                    fixed_code = "\n".join(fixed_code.split("\n")[1:])
            
            return fixed_code
        except Exception as e:
            logger.error("LLM fix generation failed", error=str(e))
            return None
