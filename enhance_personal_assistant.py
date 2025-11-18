#!/usr/bin/env python3
"""
Personal Assistant Enhancement
Generates enhanced configuration for the Personal Assistant agent.
"""

import os
import json
from anthropic import Anthropic

# Load API key from environment
API_KEY = os.getenv('ANTHROPIC_API_KEY')
if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set")

client = Anthropic(api_key=API_KEY)

# Current Personal Assistant configuration
PERSONAL_ASSISTANT = {
    "name": "Assistant",
    "department": "General",
    "icon": "🏠",
    "color": "#8B5CF6",
    "current_description": "General purpose assistant for personal and family tasks",
    "current_prompt": "You are a friendly general-purpose assistant helping with personal and family tasks."
}

print("🔍 Researching Personal Assistant best practices...\n")

research_prompt = f"""You are an expert AI agent designer researching personal productivity and family organization.

Current Agent Configuration:
- Name: {PERSONAL_ASSISTANT['name']}
- Department: {PERSONAL_ASSISTANT['department']}
- Current Description: {PERSONAL_ASSISTANT['current_description']}
- Current System Prompt: {PERSONAL_ASSISTANT['current_prompt']}

Your task is to research and enhance this Personal Assistant agent in THREE areas:

1. **ENHANCED DESCRIPTION** (2-3 sentences)
   - Research what modern personal assistants and family organizers typically handle
   - Write a compelling, comprehensive description that captures the full scope
   - Make it clear what value they provide to individuals and families
   - Focus on: personal productivity, family coordination, life management

2. **ENHANCED SYSTEM PROMPT** (detailed, 4-6 paragraphs)
   - Research current best practices for personal and family organization
   - Create a comprehensive system prompt that:
     * Defines their personality and expertise (friendly, supportive, organized)
     * Lists specific capabilities and knowledge areas
     * Includes modern tools and frameworks (GTD, bullet journaling, habit tracking, etc.)
     * Specifies how they should interact (warm, personal, empathetic)
     * Covers diverse life areas: productivity, family, health, finance, home, relationships
     * Includes when to encourage healthy boundaries and self-care
   - Make it actionable and specific to real-world personal/family needs

3. **DEFAULT TASK TEMPLATES** (10 tasks)
   - Research common personal and family management workflows
   - Create a diverse set of default tasks covering:
     * Daily planning/review tasks
     * Weekly family coordination tasks
     * Monthly life management tasks
     * Special occasion tasks (birthdays, holidays, trips)
   - Each task should have:
     * Clear title (40 chars max)
     * Detailed description of what needs to be done
     * Realistic priority (high/medium/low)

Use your extensive knowledge of personal productivity systems (GTD, time blocking, habit tracking),
family organization methods, and life management best practices.

Output your results in this EXACT JSON format:

{{
  "enhanced_description": "Your enhanced 2-3 sentence description here",
  "enhanced_system_prompt": "Your detailed multi-paragraph system prompt here",
  "default_tasks": [
    {{
      "title": "Task title here",
      "description": "Detailed task description",
      "priority": "high|medium|low"
    }}
  ],
  "research_summary": "Brief summary of key findings from your research"
}}

Focus on making this Personal Assistant genuinely useful for real individuals and families managing their daily lives."""

try:
    # Call Claude API for enhancement
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": research_prompt
        }]
    )

    # Extract the response text
    response_text = response.content[0].text

    # Parse JSON from response
    if "```json" in response_text:
        json_start = response_text.find("```json") + 7
        json_end = response_text.find("```", json_start)
        json_text = response_text[json_start:json_end].strip()
    elif "```" in response_text:
        json_start = response_text.find("```") + 3
        json_end = response_text.find("```", json_start)
        json_text = response_text[json_start:json_end].strip()
    else:
        json_text = response_text.strip()

    enhancements = json.loads(json_text)

    # Combine with original data
    result = {
        **PERSONAL_ASSISTANT,
        **enhancements
    }

    # Write to file
    output_file = "personal_assistant_enhanced.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"✅ Personal Assistant enhancement complete!")
    print(f"📄 Output saved to: {output_file}\n")
    print(f"Enhanced Description: {result['enhanced_description'][:100]}...")
    print(f"Tasks created: {len(result['default_tasks'])}")

except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
