#!/usr/bin/env python3
"""
Agent Enhancement Orchestrator
Researches and enhances department agent configurations using parallel AI sub-agents.
Uses Claude Sonnet 4.5's extensive knowledge of business best practices.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any
from anthropic import Anthropic

# Load API key from environment
API_KEY = os.getenv('ANTHROPIC_API_KEY')
if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set")

client = Anthropic(api_key=API_KEY)

# Current department agent definitions from default_departments.py
CURRENT_AGENTS = [
    {
        "name": "Evan",
        "department": "Executive",
        "icon": "👔",
        "color": "#8B5CF6",
        "current_description": "Strategic planning and business analysis expert",
        "current_prompt": "You are Evan, the Executive department assistant. Help with strategic planning, business analysis, leadership coaching, and OKR management."
    },
    {
        "name": "Fiona",
        "department": "Finance",
        "icon": "💰",
        "color": "#10B981",
        "current_description": "Financial analysis and planning specialist",
        "current_prompt": "You are Fiona, the Finance department assistant. Help with financial modeling, budgeting, ROI analysis, and cash flow management."
    },
    {
        "name": "Maya",
        "department": "Marketing",
        "icon": "📢",
        "color": "#EC4899",
        "current_description": "Marketing and growth strategist",
        "current_prompt": "You are Maya, the Marketing department assistant. Help with marketing campaigns, content strategy, SEO, social media, and growth initiatives."
    },
    {
        "name": "Sam",
        "department": "Sales",
        "icon": "💼",
        "color": "#3B82F6",
        "current_description": "Sales optimization and pipeline expert",
        "current_prompt": "You are Sam, the Sales department assistant. Help with sales pipeline management, deal closing strategies, prospecting, and CRM optimization."
    },
    {
        "name": "Sarah",
        "department": "Support",
        "icon": "🎧",
        "color": "#F59E0B",
        "current_description": "Customer support and service specialist",
        "current_prompt": "You are Sarah, the Support department assistant. Help with customer service, troubleshooting, ticket management, and support process optimization."
    },
    {
        "name": "Parker",
        "department": "Product",
        "icon": "🎯",
        "color": "#6366F1",
        "current_description": "Product strategy and development expert",
        "current_prompt": "You are Parker, the Product department assistant. Help with product roadmapping, user stories, feature prioritization, and UX principles."
    },
    {
        "name": "Larry",
        "department": "Legal",
        "icon": "⚖️",
        "color": "#EF4444",
        "current_description": "Legal compliance and contracts specialist",
        "current_prompt": "You are Larry, the Legal department assistant. Help with contracts review, compliance issues, intellectual property, risk assessment, and privacy law."
    },
    {
        "name": "Hannah",
        "department": "HR",
        "icon": "👥",
        "color": "#06B6D4",
        "current_description": "HR and people operations specialist",
        "current_prompt": "You are Hannah, the HR/People department assistant. Help with recruitment, onboarding, performance management, and fostering positive company culture."
    },
    {
        "name": "Ian",
        "department": "IT",
        "icon": "💻",
        "color": "#64748B",
        "current_description": "IT infrastructure and engineering expert",
        "current_prompt": "You are Ian, the IT/Engineering department assistant. Help with system architecture, cloud services, DevOps practices, security protocols, and database design."
    }
]


async def research_and_enhance_agent(agent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Research a single department and generate enhanced configuration.
    Uses Claude with web search to research best practices.
    """
    print(f"🔍 Researching {agent['name']} ({agent['department']})...")

    research_prompt = f"""You are an expert AI agent designer researching the {agent['department']} department.

Current Agent Configuration:
- Name: {agent['name']}
- Department: {agent['department']}
- Current Description: {agent['current_description']}
- Current System Prompt: {agent['current_prompt']}

Your task is to research and enhance this agent in THREE areas:

1. **ENHANCED DESCRIPTION** (2-3 sentences)
   - Research what a modern {agent['department']} department typically handles
   - Write a compelling, comprehensive description that captures their full scope
   - Make it clear what value they provide to the organization

2. **ENHANCED SYSTEM PROMPT** (detailed, 4-6 paragraphs)
   - Research current best practices and responsibilities for {agent['department']} roles
   - Create a comprehensive system prompt that:
     * Defines their personality and expertise
     * Lists specific capabilities and knowledge areas
     * Includes modern tools, frameworks, and methodologies they should know
     * Specifies how they should interact (tone, approach, detail level)
     * Covers edge cases and when to escalate/defer
   - Make it actionable and specific to real-world {agent['department']} work

3. **DEFAULT TASK TEMPLATES** (7-10 tasks)
   - Research common workflows and responsibilities in {agent['department']}
   - Create a diverse set of default tasks covering:
     * Daily/routine tasks
     * Monthly/periodic tasks
     * Strategic/planning tasks
     * Crisis/reactive tasks
   - Each task should have:
     * Clear title (40 chars max)
     * Detailed description of what needs to be done
     * Realistic priority (high/medium/low)

Use your comprehensive knowledge of modern business practices, industry standards, and {agent['department']} department operations to output your results in this EXACT JSON format:

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

Draw on your extensive knowledge of {agent['department']} best practices. Focus on making this agent genuinely useful for a real {agent['department']} department."""

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

        # Parse JSON from response (handle markdown code blocks)
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

        print(f"✅ Completed {agent['name']} ({agent['department']})")

        return {
            **agent,
            **enhancements
        }

    except Exception as e:
        print(f"❌ Error researching {agent['name']}: {e}")
        return {
            **agent,
            "error": str(e),
            "enhanced_description": agent['current_description'],
            "enhanced_system_prompt": agent['current_prompt'],
            "default_tasks": [],
            "research_summary": f"Error occurred: {e}"
        }


async def orchestrate_enhancements():
    """
    Main orchestrator - runs all agent enhancements in parallel.
    """
    print(f"\n{'='*60}")
    print("🚀 Agent Enhancement Orchestrator Starting")
    print(f"{'='*60}\n")
    print(f"Enhancing {len(CURRENT_AGENTS)} department agents...")
    print(f"Using model: claude-sonnet-4-5-20250929\n")

    # Run all agent enhancements in parallel
    tasks = [research_and_enhance_agent(agent) for agent in CURRENT_AGENTS]
    enhanced_agents = await asyncio.gather(*tasks)

    # Build output structure
    output = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "agent_count": len(enhanced_agents),
            "model_used": "claude-sonnet-4-5-20250929",
            "enhancement_type": "system_prompts_descriptions_tasks"
        },
        "agents": enhanced_agents
    }

    # Write to JSON file
    output_file = "enhanced_agents.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"✨ Enhancement Complete!")
    print(f"{'='*60}\n")
    print(f"📄 Output saved to: {output_file}")
    print(f"📊 Enhanced {len(enhanced_agents)} agents")
    print(f"\nNext steps:")
    print(f"1. Review {output_file}")
    print(f"2. Run: python import_enhanced_agents.py")
    print(f"   (This will apply the enhancements to your database)\n")

    return output


def main():
    """Entry point for the orchestrator."""
    # Run the async orchestrator
    asyncio.run(orchestrate_enhancements())


if __name__ == "__main__":
    main()
