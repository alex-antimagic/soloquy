"""
AI Service for Claude API Integration
Uses Claude Haiku for fast, cost-effective agent responses
"""
import os
import json
from anthropic import Anthropic
from typing import List, Dict, Optional


class AIService:
    """Service for interacting with Claude AI"""

    # Use Claude Haiku 4.5 for fast, efficient responses
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self):
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.client = Anthropic(api_key=api_key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 1.0
    ) -> str:
        """
        Send a chat message to Claude and get a response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: System prompt defining the agent's behavior
            model: Model to use (defaults to Haiku)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Returns:
            The AI's response text
        """
        if model is None:
            model = self.DEFAULT_MODEL

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages
            )

            # Extract text from response
            if response.content and len(response.content) > 0:
                return response.content[0].text

            return "I apologize, but I couldn't generate a response. Please try again."

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            raise

    def analyze_bug_screenshot(
        self,
        image_base64: str,
        image_media_type: str = "image/png",
        current_url: Optional[str] = None,
        tenant_name: Optional[str] = None,
        user_name: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Analyze a bug screenshot using Claude's vision capabilities.

        Args:
            image_base64: Base64 encoded image data (without data URI prefix)
            image_media_type: Image MIME type (e.g., 'image/png', 'image/jpeg')
            current_url: The URL where the bug occurred
            tenant_name: Name of the workspace/tenant
            user_name: Name of the user reporting the bug

        Returns:
            Dictionary with 'subject', 'description', and 'priority'
        """
        # Build context information
        context_parts = []
        if tenant_name:
            context_parts.append(f"Workspace: {tenant_name}")
        if user_name:
            context_parts.append(f"Reporter: {user_name}")
        if current_url:
            context_parts.append(f"Page URL: {current_url}")

        context = "\n".join(context_parts) if context_parts else "No additional context provided."

        system_prompt = f"""You are a helpful assistant analyzing screenshots for bug reports in the Soloquy application - a Slack-inspired team collaboration platform.

{context}

Analyze the screenshot and provide a structured bug report. Look for:
1. Error messages, broken UI elements, or unexpected behavior
2. Layout issues, misalignments, or styling problems
3. Missing or incorrect data display
4. Navigation or interaction problems

Respond ONLY with valid JSON in this exact format:
{{
  "subject": "Brief, clear title for the bug (max 80 chars)",
  "description": "Detailed description including:\\n- What you observe in the screenshot\\n- What appears to be wrong\\n- Any error messages visible\\n- Steps that likely led to this state (if discernible)",
  "priority": "low|medium|high|urgent"
}}

Priority guidelines:
- low: Cosmetic issues, minor text problems
- medium: Functionality works but has issues, has workarounds
- high: Major functionality broken, significantly impacts user experience
- urgent: Critical system failure, data loss, security issue, app completely broken"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",  # Use Sonnet for vision support
                max_tokens=1024,
                temperature=0.3,  # Lower temperature for more consistent analysis
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_media_type,
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": "Please analyze this screenshot and provide a bug report in the requested JSON format."
                        }
                    ]
                }]
            )

            # Extract text from response
            if response.content and len(response.content) > 0:
                response_text = response.content[0].text.strip()

                # Try to parse JSON from response
                # Sometimes Claude adds markdown code blocks, so we need to extract the JSON
                if "```json" in response_text:
                    # Extract JSON from markdown code block
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    # Extract from generic code block
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()

                # Parse the JSON
                result = json.loads(response_text)

                # Validate the response has required fields
                if not all(key in result for key in ['subject', 'description', 'priority']):
                    raise ValueError("AI response missing required fields")

                # Validate priority value
                if result['priority'] not in ['low', 'medium', 'high', 'urgent']:
                    result['priority'] = 'medium'  # Default to medium if invalid

                return result

            # Fallback if no response
            return {
                'subject': 'Bug Report from Screenshot',
                'description': 'Please review the attached screenshot and provide details about the issue.',
                'priority': 'medium'
            }

        except json.JSONDecodeError as e:
            print(f"Error parsing AI response as JSON: {e}")
            # Return fallback response
            return {
                'subject': 'Bug Report from Screenshot',
                'description': 'AI analysis encountered an error. Please describe the issue shown in the screenshot.',
                'priority': 'medium'
            }
        except Exception as e:
            print(f"Error analyzing screenshot with Claude API: {e}")
            raise

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 1.0
    ):
        """
        Stream a chat response from Claude.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: System prompt defining the agent's behavior
            model: Model to use (defaults to Haiku)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Yields:
            Text chunks as they arrive from the API
        """
        if model is None:
            model = self.DEFAULT_MODEL

        try:
            with self.client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            print(f"Error streaming from Claude API: {e}")
            raise


# Singleton instance
_ai_service = None

def get_ai_service() -> AIService:
    """Get or create the AI service singleton"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
