"""
AI Service for Claude API Integration
Uses Claude Haiku for fast, cost-effective agent responses
Supports Model Context Protocol (MCP) for external data access
"""
import os
import json
from anthropic import Anthropic
from typing import List, Dict, Optional, Any
from flask import current_app


class AIService:
    """Service for interacting with Claude AI"""

    # Use Claude Haiku 4.5 for fast, efficient responses
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self):
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.client = Anthropic(api_key=api_key)

    def _get_outlook_tools(self) -> List[Dict]:
        """
        Get static Outlook tool definitions for direct Graph API calls

        Returns:
            List of Outlook tool definitions
        """
        return [
            {
                "name": "outlook_list_emails",
                "description": "List recent emails from Outlook inbox",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of emails to return (default: 10)",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "outlook_read_email",
                "description": "Read the full content of a specific email by ID",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "The ID of the email to read"
                        }
                    },
                    "required": ["email_id"]
                }
            },
            {
                "name": "outlook_search_emails",
                "description": "Search emails by keyword in subject or body",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text"
                        },
                        "max_results": {
                            "type": "number",
                            "description": "Maximum results to return (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "outlook_send_email",
                "description": "Compose and send a new email",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of recipient email addresses"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content"
                        },
                        "cc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of CC recipients"
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "outlook_list_calendar_events",
                "description": "List upcoming calendar events from Outlook calendar",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of events to return (default: 10)",
                            "default": 10
                        },
                        "days_ahead": {
                            "type": "number",
                            "description": "Number of days ahead to look for events (default: 7)",
                            "default": 7
                        }
                    }
                }
            },
            {
                "name": "outlook_create_calendar_event",
                "description": "Create a new calendar event in Outlook calendar",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "subject": {
                            "type": "string",
                            "description": "Event title"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time in ISO format WITHOUT timezone (e.g., '2024-01-15T14:00:00'). The AI should convert user's local time to UTC before passing here."
                        },
                        "end": {
                            "type": "string",
                            "description": "End time in ISO format WITHOUT timezone. The AI should convert user's local time to UTC before passing here."
                        },
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of attendee email addresses"
                        },
                        "location": {
                            "type": "string",
                            "description": "Optional location string"
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional event description"
                        },
                        "is_online_meeting": {
                            "type": "boolean",
                            "description": "Whether to create a Teams online meeting (default: False)",
                            "default": False
                        }
                    },
                    "required": ["subject", "start", "end"]
                }
            },
            {
                "name": "outlook_get_free_busy",
                "description": "Check free/busy availability for one or more people",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of email addresses to check availability for"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time in ISO format"
                        },
                        "end": {
                            "type": "string",
                            "description": "End time in ISO format"
                        }
                    },
                    "required": ["emails", "start", "end"]
                }
            }
        ]

    def _get_website_tools(self) -> List[Dict]:
        """
        Get website builder tool definitions for AI agents

        Returns:
            List of website builder tool definitions
        """
        return [
            {
                "name": "website_generate",
                "description": "Generate a complete website from business context. Creates homepage, about page, and theme based on the tenant's business information.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "regenerate": {
                            "type": "boolean",
                            "description": "Force regeneration even if website exists (default: false)",
                            "default": False
                        }
                    }
                }
            },
            {
                "name": "website_create_page",
                "description": "Create a new page on the website",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "page_type": {
                            "type": "string",
                            "description": "Type of page: 'home', 'blog', 'landing', or 'custom'",
                            "enum": ["home", "blog", "landing", "custom"]
                        },
                        "slug": {
                            "type": "string",
                            "description": "URL slug for the page (e.g., 'about-us', 'pricing')"
                        },
                        "title": {
                            "type": "string",
                            "description": "Page title"
                        },
                        "content_description": {
                            "type": "string",
                            "description": "Description of what content should be on the page. The AI will generate appropriate sections."
                        },
                        "publish": {
                            "type": "boolean",
                            "description": "Publish the page immediately (default: false)",
                            "default": False
                        }
                    },
                    "required": ["page_type", "slug", "title", "content_description"]
                }
            },
            {
                "name": "website_update_theme",
                "description": "Update the website theme colors and fonts",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "primary_color": {
                            "type": "string",
                            "description": "Primary brand color (hex code, e.g., '#667eea')"
                        },
                        "secondary_color": {
                            "type": "string",
                            "description": "Secondary color (hex code)"
                        },
                        "background_color": {
                            "type": "string",
                            "description": "Background color (hex code)"
                        },
                        "text_color": {
                            "type": "string",
                            "description": "Text color (hex code)"
                        },
                        "heading_font": {
                            "type": "string",
                            "description": "Google Font name for headings (e.g., 'Inter', 'Roboto')"
                        },
                        "body_font": {
                            "type": "string",
                            "description": "Google Font name for body text"
                        }
                    }
                }
            },
            {
                "name": "website_publish",
                "description": "Publish or unpublish the website",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "publish": {
                            "type": "boolean",
                            "description": "True to publish, false to unpublish"
                        },
                        "is_indexable": {
                            "type": "boolean",
                            "description": "Allow search engines to index the website (default: true)",
                            "default": True
                        }
                    },
                    "required": ["publish"]
                }
            },
            {
                "name": "website_get_status",
                "description": "Get the current status and details of the website",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def _get_competitive_analysis_tools(self) -> List[Dict]:
        """
        Get competitive analysis tool definitions for AI agents

        Returns:
            List of competitive analysis tool definitions
        """
        return [
            {
                "name": "competitive_analysis_suggest_competitors",
                "description": "Suggest competitor companies based on workspace business context",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of competitors to suggest (default: 10)",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "competitive_analysis_analyze",
                "description": "Run comprehensive competitive analysis comparing workspace against specified competitors",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "competitor_ids": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "CompetitorProfile IDs to analyze (use after suggesting competitors)"
                        },
                        "analysis_type": {
                            "type": "string",
                            "enum": ["comprehensive", "website", "marketing"],
                            "description": "Type of analysis to perform",
                            "default": "comprehensive"
                        }
                    },
                    "required": ["competitor_ids"]
                }
            },
            {
                "name": "competitive_analysis_get_status",
                "description": "Get status and results of the most recent competitive analysis",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def _get_similar_lead_discovery_tools(self) -> List[Dict]:
        """
        Get similar lead discovery tool definitions for AI agents

        Returns:
            List of similar lead discovery tool definitions
        """
        return [
            {
                "name": "similar_leads_discover",
                "description": "Find potential leads similar to an existing customer company. Returns similar companies that match the customer's profile and can be added as leads.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "reference_company_id": {
                            "type": "number",
                            "description": "ID of the reference customer company to find similar leads for"
                        },
                        "reference_company_name": {
                            "type": "string",
                            "description": "Name of the reference company (for lookup if ID not known)"
                        },
                        "criteria": {
                            "type": "object",
                            "description": "Similarity criteria to match",
                            "properties": {
                                "industry": {"type": "boolean", "default": True},
                                "business_model": {"type": "boolean", "default": True},
                                "tech_stack": {"type": "boolean", "default": True},
                                "company_size": {"type": "boolean", "default": True}
                            }
                        },
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of similar leads to discover (default: 20)",
                            "default": 20
                        }
                    }
                }
            },
            {
                "name": "similar_leads_get_status",
                "description": "Get the status and results of a similar lead discovery job",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "discovery_id": {
                            "type": "number",
                            "description": "ID of the discovery job to check. If not provided, returns most recent discovery."
                        }
                    }
                }
            },
            {
                "name": "similar_leads_list_discoveries",
                "description": "List recent similar lead discovery jobs for this workspace",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "number",
                            "description": "Number of recent discoveries to return (default: 10)",
                            "default": 10
                        }
                    }
                }
            }
        ]

    def _get_file_generation_tools(self) -> List[Dict]:
        """
        Get file generation tool definitions for AI agents

        Returns:
            List of file generation tool definitions
        """
        return [
            {
                "name": "generate_pdf_report",
                "description": "Generate a PDF report with formatted content including tables, headings, and paragraphs",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Report title"
                        },
                        "content_blocks": {
                            "type": "array",
                            "description": "List of content blocks (headings, paragraphs, tables, spacers)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["heading", "paragraph", "table", "spacer"],
                                        "description": "Type of content block"
                                    },
                                    "content": {
                                        "description": "Content for the block. For tables, use {headers: [...], data: [[...]]}. For text/headings, use string."
                                    },
                                    "level": {
                                        "type": "number",
                                        "description": "Heading level (1-3, only for heading type)"
                                    },
                                    "height": {
                                        "type": "number",
                                        "description": "Height in inches (only for spacer type)"
                                    }
                                }
                            }
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["title", "content_blocks"]
                }
            },
            {
                "name": "export_to_csv",
                "description": "Export tabular data to a CSV file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "headers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Column headers"
                        },
                        "data": {
                            "type": "array",
                            "description": "Array of rows, where each row is an array of values",
                            "items": {
                                "type": "array"
                            }
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["headers", "data"]
                }
            },
            {
                "name": "create_spreadsheet",
                "description": "Create an Excel spreadsheet (.xlsx) with one or more sheets",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sheets": {
                            "type": "array",
                            "description": "Array of sheet definitions",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Sheet name"
                                    },
                                    "headers": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Column headers"
                                    },
                                    "data": {
                                        "type": "array",
                                        "description": "Array of rows",
                                        "items": {"type": "array"}
                                    }
                                }
                            }
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["sheets"]
                }
            },
            {
                "name": "create_markdown_document",
                "description": "Create a Markdown document (.md) with formatted text, headers, lists, code blocks, and tables",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content including headers (##), lists (- or 1.), bold (**text**), code blocks (```), tables, etc."
                        },
                        "title": {
                            "type": "string",
                            "description": "Optional document title (will be added as H1 at the top)"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["content"]
                }
            },
            {
                "name": "create_word_document",
                "description": "Create a Word document (.docx) with formatted content including headings, paragraphs, bullet lists, numbered lists, and tables",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Document title"
                        },
                        "content_blocks": {
                            "type": "array",
                            "description": "List of content blocks",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["heading", "paragraph", "bullet_list", "numbered_list", "table"],
                                        "description": "Type of content block"
                                    },
                                    "content": {
                                        "description": "Content for the block. For lists, use array of strings. For tables, use {headers: [...], data: [[...]]}. For text/headings, use string."
                                    },
                                    "level": {
                                        "type": "number",
                                        "description": "Heading level (1-3, only for heading type)"
                                    }
                                }
                            }
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["title", "content_blocks"]
                }
            }
        ]

    def _get_hr_tools(self) -> List[Dict]:
        """
        Get HR management tool definitions for AI agents

        Returns:
            List of HR tool definitions
        """
        return [
            # ===== RECRUITMENT TOOLS =====
            {
                "name": "hr_search_candidates",
                "description": "Search candidates with filters for job position, status, minimum score, and required skills",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "job_position": {
                            "type": "string",
                            "description": "Filter by job position (partial match)"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["applied", "screening", "interviewing", "offer_extended", "hired", "rejected"],
                            "description": "Filter by candidate status"
                        },
                        "min_score": {
                            "type": "number",
                            "description": "Minimum applicant score (0-100)"
                        },
                        "skills": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of required skills"
                        },
                        "max_results": {
                            "type": "number",
                            "description": "Maximum results to return (default: 20)",
                            "default": 20
                        }
                    }
                }
            },
            {
                "name": "hr_get_candidate_details",
                "description": "Get detailed information about a specific candidate including application history and interview records",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {
                            "type": "number",
                            "description": "Candidate ID"
                        }
                    },
                    "required": ["candidate_id"]
                }
            },
            {
                "name": "hr_score_candidate",
                "description": "Update candidate scoring with overall score and category-specific scores",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {
                            "type": "number",
                            "description": "Candidate ID"
                        },
                        "overall_score": {
                            "type": "number",
                            "description": "Overall score (0-100)"
                        },
                        "category_scores": {
                            "type": "object",
                            "description": "Category-specific scores (e.g., {technical: 85, communication: 90})"
                        },
                        "note": {
                            "type": "string",
                            "description": "Assessment note to add"
                        }
                    },
                    "required": ["candidate_id"]
                }
            },
            {
                "name": "hr_schedule_interview",
                "description": "Schedule an interview for a candidate",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {
                            "type": "number",
                            "description": "Candidate ID"
                        },
                        "interview_type": {
                            "type": "string",
                            "enum": ["phone_screen", "technical", "behavioral", "panel", "final"],
                            "description": "Type of interview"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Interview start time (ISO 8601 format, e.g., 2025-12-15T10:00:00)"
                        },
                        "duration_minutes": {
                            "type": "number",
                            "description": "Interview duration in minutes (default: 60)",
                            "default": 60
                        },
                        "interviewers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of interviewer email addresses"
                        },
                        "location": {
                            "type": "string",
                            "description": "Interview location or video link"
                        },
                        "notes": {
                            "type": "string",
                            "description": "Interview preparation notes"
                        }
                    },
                    "required": ["candidate_id", "interview_type", "start_time", "interviewers"]
                }
            },
            {
                "name": "hr_move_candidate_stage",
                "description": "Move candidate to a different stage in the recruitment pipeline",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {
                            "type": "number",
                            "description": "Candidate ID"
                        },
                        "new_status": {
                            "type": "string",
                            "enum": ["applied", "screening", "interviewing", "offer_extended", "hired", "rejected"],
                            "description": "New candidate status"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Optional reason for status change (especially for rejection)"
                        },
                        "send_notification": {
                            "type": "boolean",
                            "description": "Send email notification to candidate (default: true)",
                            "default": true
                        }
                    },
                    "required": ["candidate_id", "new_status"]
                }
            },

            # ===== ONBOARDING TOOLS =====
            {
                "name": "hr_create_onboarding_plan",
                "description": "Create an onboarding plan for a new hire with tasks from a template or custom tasks",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {
                            "type": "number",
                            "description": "Employee ID"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date (ISO format: YYYY-MM-DD)"
                        },
                        "template": {
                            "type": "string",
                            "enum": ["standard", "engineering", "sales", "manager"],
                            "description": "Onboarding template to use (default: standard)",
                            "default": "standard"
                        },
                        "custom_tasks": {
                            "type": "array",
                            "description": "Additional custom tasks to include",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "description": {"type": "string"},
                                    "due_days": {"type": "number"},
                                    "assigned_to": {"type": "string"}
                                }
                            }
                        },
                        "buddy_email": {
                            "type": "string",
                            "description": "Optional buddy/mentor email"
                        }
                    },
                    "required": ["employee_id", "start_date"]
                }
            },
            {
                "name": "hr_get_onboarding_status",
                "description": "Get onboarding plan status and task progress for an employee",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {
                            "type": "number",
                            "description": "Employee ID"
                        }
                    },
                    "required": ["employee_id"]
                }
            },
            {
                "name": "hr_send_onboarding_reminder",
                "description": "Send reminder emails for overdue onboarding tasks",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {
                            "type": "number",
                            "description": "Employee ID"
                        },
                        "include_manager": {
                            "type": "boolean",
                            "description": "Also send reminder to manager (default: false)",
                            "default": false
                        }
                    },
                    "required": ["employee_id"]
                }
            },

            # ===== EMPLOYEE RECORDS TOOLS =====
            {
                "name": "hr_search_employees",
                "description": "Search employees with filters for department, status, role, and name/email",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "department": {
                            "type": "string",
                            "description": "Filter by department name"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["active", "on_leave", "terminated"],
                            "description": "Filter by employment status"
                        },
                        "role": {
                            "type": "string",
                            "description": "Filter by role (partial match)"
                        },
                        "search_query": {
                            "type": "string",
                            "description": "Search by name or email"
                        },
                        "max_results": {
                            "type": "number",
                            "description": "Maximum results to return (default: 50)",
                            "default": 50
                        }
                    }
                }
            },
            {
                "name": "hr_get_employee_record",
                "description": "Get detailed employee record including compensation, PTO balance, and employment history",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {
                            "type": "number",
                            "description": "Employee ID"
                        }
                    },
                    "required": ["employee_id"]
                }
            },
            {
                "name": "hr_add_employee_note",
                "description": "Add a confidential HR note to an employee's record",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {
                            "type": "number",
                            "description": "Employee ID"
                        },
                        "note": {
                            "type": "string",
                            "description": "Note content"
                        },
                        "note_type": {
                            "type": "string",
                            "enum": ["general", "performance", "disciplinary", "compensation", "leave"],
                            "description": "Type of note (default: general)",
                            "default": "general"
                        }
                    },
                    "required": ["employee_id", "note"]
                }
            },

            # ===== TIME OFF TOOLS =====
            {
                "name": "hr_get_pto_balance",
                "description": "Get PTO balance and usage for an employee",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {
                            "type": "number",
                            "description": "Employee ID"
                        }
                    },
                    "required": ["employee_id"]
                }
            },
            {
                "name": "hr_view_team_calendar",
                "description": "View team PTO calendar showing approved and pending time off",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "department": {
                            "type": "string",
                            "description": "Filter by department (optional)"
                        },
                        "days_ahead": {
                            "type": "number",
                            "description": "Days ahead to view (default: 30)",
                            "default": 30
                        },
                        "include_pending": {
                            "type": "boolean",
                            "description": "Include pending requests (default: true)",
                            "default": true
                        }
                    }
                }
            },
            {
                "name": "hr_review_pto_request",
                "description": "Approve or deny a PTO request",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "request_id": {
                            "type": "number",
                            "description": "PTO request ID"
                        },
                        "action": {
                            "type": "string",
                            "enum": ["approve", "deny"],
                            "description": "Action to take"
                        },
                        "reviewer_name": {
                            "type": "string",
                            "description": "Name of person approving/denying"
                        },
                        "denial_reason": {
                            "type": "string",
                            "description": "Reason for denial (required if action is deny)"
                        }
                    },
                    "required": ["request_id", "action", "reviewer_name"]
                }
            }
        ]

    def _get_cross_applet_query_tools(self) -> List[Dict]:
        """Get read-only query tools for all applets"""
        tools = []
        tools.extend(self._get_crm_query_tools())
        tools.extend(self._get_files_query_tools())
        tools.extend(self._get_hr_query_tools())
        tools.extend(self._get_support_query_tools())
        tools.extend(self._get_projects_query_tools())
        return tools

    def _get_crm_query_tools(self) -> List[Dict]:
        """4 read-only CRM tools"""
        return [
            {
                "name": "query_crm_companies",
                "description": "Search companies with filters (READ-ONLY - cannot modify companies)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search_query": {"type": "string", "description": "Search by company name"},
                        "industry": {"type": "string", "description": "Filter by industry"},
                        "status": {"type": "string", "enum": ["active", "inactive", "prospect", "customer"], "description": "Filter by status"},
                        "max_results": {"type": "number", "default": 20, "description": "Maximum number of results to return"}
                    }
                }
            },
            {
                "name": "query_crm_contacts",
                "description": "Search contacts with filters (READ-ONLY - cannot modify contacts)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search_query": {"type": "string", "description": "Search by name or email"},
                        "company_id": {"type": "number", "description": "Filter by company ID"},
                        "max_results": {"type": "number", "default": 20, "description": "Maximum number of results to return"}
                    }
                }
            },
            {
                "name": "query_crm_deals",
                "description": "Search deals/opportunities with filters (READ-ONLY - cannot modify deals)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["open", "won", "lost"], "description": "Filter by deal status"},
                        "min_amount": {"type": "number", "description": "Minimum deal amount"},
                        "company_id": {"type": "number", "description": "Filter by company ID"},
                        "max_results": {"type": "number", "default": 20, "description": "Maximum number of results to return"}
                    }
                }
            },
            {
                "name": "query_crm_deal_details",
                "description": "Get detailed information about a specific deal including contacts and activities (READ-ONLY)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "deal_id": {"type": "number", "description": "Deal ID to retrieve"}
                    },
                    "required": ["deal_id"]
                }
            }
        ]

    def _get_files_query_tools(self) -> List[Dict]:
        """3 read-only Files query tools"""
        return [
            {
                "name": "query_files_workspace",
                "description": "Search all files in the workspace (READ-ONLY - cannot modify or delete files)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_type": {"type": "string", "enum": ["pdf", "csv", "xlsx", "all"], "description": "Filter by file type"},
                        "search_query": {"type": "string", "description": "Search by filename"},
                        "max_results": {"type": "number", "default": 50, "description": "Maximum number of results to return"}
                    }
                }
            },
            {
                "name": "query_files_by_user",
                "description": "Get files requested by a specific user (READ-ONLY - cannot modify or delete files)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "number", "description": "User ID to filter by"},
                        "file_type": {"type": "string", "enum": ["pdf", "csv", "xlsx", "all"], "description": "Filter by file type"},
                        "max_results": {"type": "number", "default": 50, "description": "Maximum number of results to return"}
                    },
                    "required": ["user_id"]
                }
            },
            {
                "name": "query_files_by_agent",
                "description": "Get files generated by a specific agent (READ-ONLY - cannot modify or delete files)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "number", "description": "Agent ID to filter by"},
                        "file_type": {"type": "string", "enum": ["pdf", "csv", "xlsx", "all"], "description": "Filter by file type"},
                        "max_results": {"type": "number", "default": 50, "description": "Maximum number of results to return"}
                    },
                    "required": ["agent_id"]
                }
            }
        ]

    def _get_hr_query_tools(self) -> List[Dict]:
        """5 read-only HR tools (excluding sensitive data like compensation)"""
        return [
            {
                "name": "query_hr_employees",
                "description": "Search employees with filters (READ-ONLY - excludes compensation data, cannot modify employee records)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "department": {"type": "string", "description": "Filter by department name"},
                        "status": {"type": "string", "enum": ["active", "on_leave", "terminated"], "description": "Filter by employment status"},
                        "search_query": {"type": "string", "description": "Search by name or email"},
                        "max_results": {"type": "number", "default": 50, "description": "Maximum number of results to return"}
                    }
                }
            },
            {
                "name": "query_hr_candidates",
                "description": "Search job candidates with filters (READ-ONLY - cannot schedule interviews or change status)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "job_position": {"type": "string", "description": "Filter by position being recruited for"},
                        "status": {"type": "string", "description": "Filter by candidate status (applied, screening, interviewing, offer_extended, hired, rejected)"},
                        "max_results": {"type": "number", "default": 20, "description": "Maximum number of results to return"}
                    }
                }
            },
            {
                "name": "query_hr_employee_record",
                "description": "Get employee details including role, department, hire date (READ-ONLY - excludes compensation and confidential notes)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "number", "description": "Employee ID to retrieve"}
                    },
                    "required": ["employee_id"]
                }
            },
            {
                "name": "query_hr_pto_calendar",
                "description": "View team PTO/time-off calendar (READ-ONLY - cannot approve or deny requests)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "department": {"type": "string", "description": "Filter by department"},
                        "days_ahead": {"type": "number", "default": 30, "description": "Number of days to look ahead"}
                    }
                }
            },
            {
                "name": "query_hr_pto_balance",
                "description": "Get PTO balance for an employee (READ-ONLY - view only)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "number", "description": "Employee ID to retrieve balance for"}
                    },
                    "required": ["employee_id"]
                }
            }
        ]

    def _get_support_query_tools(self) -> List[Dict]:
        """3 read-only Support tools"""
        return [
            {
                "name": "query_support_tickets",
                "description": "Search support tickets with filters (READ-ONLY - cannot assign, update status, or add comments)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "Filter by status (new, open, pending, on_hold, resolved, closed)"},
                        "priority": {"type": "string", "description": "Filter by priority (low, medium, high, urgent)"},
                        "search_query": {"type": "string", "description": "Search ticket number, subject, or description"},
                        "max_results": {"type": "number", "default": 25, "description": "Maximum number of results to return"}
                    }
                }
            },
            {
                "name": "query_support_ticket_details",
                "description": "Get detailed ticket information including comments and attachments (READ-ONLY)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "number", "description": "Ticket ID to retrieve"}
                    },
                    "required": ["ticket_id"]
                }
            },
            {
                "name": "query_support_metrics",
                "description": "Get support ticket metrics and statistics (READ-ONLY)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "department_id": {"type": "number", "description": "Filter by department (optional)"}
                    }
                }
            }
        ]

    def _get_projects_query_tools(self) -> List[Dict]:
        """3 read-only Project tools"""
        return [
            {
                "name": "query_project_tasks",
                "description": "Search tasks with filters (READ-ONLY - cannot create, update, or assign tasks)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "number", "description": "Filter by project ID"},
                        "status": {"type": "string", "description": "Filter by task status (pending, in_progress, completed)"},
                        "assigned_to_id": {"type": "number", "description": "Filter by assigned user ID"},
                        "max_results": {"type": "number", "default": 50, "description": "Maximum number of results to return"}
                    }
                }
            },
            {
                "name": "query_project_details",
                "description": "Get project information including members, status columns, and task summary (READ-ONLY)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "number", "description": "Project ID to retrieve"}
                    },
                    "required": ["project_id"]
                }
            },
            {
                "name": "query_projects_list",
                "description": "List all projects with filters (READ-ONLY)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "is_archived": {"type": "boolean", "default": False, "description": "Include archived projects"},
                        "max_results": {"type": "number", "default": 20, "description": "Maximum number of results to return"}
                    }
                }
            }
        ]

    def _get_agent_delegation_tools(self, orchestrator_agent, user) -> List[Dict]:
        """
        Generate delegation tools for orchestrator agents.
        Each specialist agent becomes a callable tool for Oscar.
        """
        from app.models.agent import Agent
        from app.models.department import Department

        # Get all specialist agents in the same tenant as the orchestrator
        specialist_agents = Agent.query.join(Department).filter(
            Department.tenant_id == orchestrator_agent.department.tenant_id,
            Agent.agent_type == 'specialist',
            Agent.is_active == True
        ).all()

        tools = []
        for specialist in specialist_agents:
            # Check if user has access to this specialist
            if not specialist.can_user_access(user):
                continue

            tool = {
                "name": f"consult_{specialist.name.lower()}",
                "description": (
                    f"Consult with {specialist.name}, specialist in {specialist.department.name}. "
                    f"{specialist.description or ''}"
                    f"Use this when the user's question relates to {specialist.department.name.lower()} matters."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The specific question or task to ask this specialist"
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context from the user's original question (optional)"
                        }
                    },
                    "required": ["query"]
                }
            }
            tools.append(tool)

        return tools

    def _execute_agent_delegation_tool(self, tool_name, tool_input, orchestrator_agent, user, db_message):
        """
        Execute a delegation to a specialist agent.

        Args:
            tool_name: Name of the tool (e.g., "consult_maya")
            tool_input: The tool input parameters
            orchestrator_agent: The orchestrator agent making the delegation
            user: The user asking the question
            db_message: The database message object

        Returns:
            Dictionary with specialist response or error
        """
        from app.models.agent import Agent
        from app.models.agent_delegation import AgentDelegation
        from app.models.department import Department

        # Extract specialist name from tool name: "consult_maya" -> "maya"
        specialist_name = tool_name.replace('consult_', '')

        # Find the specialist agent in the same tenant
        specialist = Agent.query.join(Department).filter(
            Department.tenant_id == orchestrator_agent.department.tenant_id,
            db.func.lower(Agent.name) == specialist_name.lower(),
            Agent.agent_type == 'specialist',
            Agent.is_active == True
        ).first()

        if not specialist:
            return {"error": f"Specialist agent '{specialist_name}' not found or not available"}

        # Build the query for the specialist
        specialist_query = tool_input.get('query', '')
        context = tool_input.get('context', '')

        # Construct specialist prompt with context
        full_query = specialist_query
        if context:
            full_query = f"Context: {context}\n\nQuestion: {specialist_query}"

        # Get business context for specialist
        business_context = specialist.build_system_prompt_with_context(
            tenant=orchestrator_agent.department.tenant,
            user=user
        )

        # Call specialist agent
        try:
            # Create messages list for specialist
            specialist_messages = [{
                "role": "user",
                "content": full_query
            }]

            # Get tools for specialist
            specialist_tools = []
            if specialist.enable_cross_applet_data_access:
                specialist_tools.extend(self._get_cross_applet_query_tools())
            if specialist.enable_file_generation:
                specialist_tools.extend(self._get_file_generation_tools())
            if specialist.enable_quickbooks:
                specialist_tools.extend(self._get_quickbooks_tools())
            if specialist.enable_hr_management:
                specialist_tools.extend(self._get_hr_tools())

            # Call the specialist's chat method
            response = self._call_claude_with_tools(
                messages=specialist_messages,
                system_prompt=business_context,
                tools=specialist_tools,
                model=specialist.model,
                agent=specialist,
                user=user,
                db_message=db_message
            )

            # Log delegation for analytics
            delegation = AgentDelegation(
                orchestrator_id=orchestrator_agent.id,
                specialist_id=specialist.id,
                message_id=db_message.id if db_message else None,
                user_query=specialist_query,
                delegation_reasoning=f"Orchestrator delegated {specialist.department.name} query"
            )
            db.session.add(delegation)
            db.session.commit()

            # Extract text response
            if isinstance(response, dict) and 'content' in response:
                response_text = response['content'][0]['text'] if response['content'] else str(response)
            else:
                response_text = str(response)

            return {
                "specialist": specialist.name,
                "department": specialist.department.name,
                "response": response_text
            }

        except Exception as e:
            return {
                "error": f"Failed to consult {specialist.name}: {str(e)}"
            }

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 1.0,
        agent=None,
        user=None
    ) -> str:
        """
        Send a chat message to Claude and get a response.
        Supports MCP tool calling for external data access.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: System prompt defining the agent's behavior
            model: Model to use (defaults to Haiku)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            agent: Agent model (for MCP integration support)
            user: User model (for MCP integration support)

        Returns:
            The AI's response text
        """
        if model is None:
            model = self.DEFAULT_MODEL

        try:
            # Build API call parameters
            api_params = {
                'model': model,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'system': system_prompt,
                'messages': messages
            }

            # Get tools if agent has integrations enabled
            tools = []
            if agent and user:
                if agent.enable_outlook:
                    print(f"[OUTLOOK] Getting Outlook tools for agent {agent.id}")
                    outlook_tools = self._get_outlook_tools()
                    print(f"[OUTLOOK] Got {len(outlook_tools)} Outlook tools")
                    tools.extend(outlook_tools)

                if agent.enable_website_builder:
                    print(f"[WEBSITE] Getting Website tools for agent {agent.id}")
                    website_tools = self._get_website_tools()
                    print(f"[WEBSITE] Got {len(website_tools)} Website tools")
                    tools.extend(website_tools)

                if agent.enable_file_generation:
                    print(f"[FILE_GEN] Getting File Generation tools for agent {agent.id}")
                    file_gen_tools = self._get_file_generation_tools()
                    print(f"[FILE_GEN] Got {len(file_gen_tools)} File Generation tools")
                    tools.extend(file_gen_tools)

                if agent.enable_competitive_analysis:
                    print(f"[COMPETITIVE] Getting Competitive Analysis tools for agent {agent.id}")
                    competitive_tools = self._get_competitive_analysis_tools()
                    print(f"[COMPETITIVE] Got {len(competitive_tools)} Competitive Analysis tools")
                    tools.extend(competitive_tools)

                if agent.enable_similar_lead_discovery:
                    print(f"[SIMILAR_LEADS] Getting Similar Lead Discovery tools for agent {agent.id}")
                    similar_lead_tools = self._get_similar_lead_discovery_tools()
                    print(f"[SIMILAR_LEADS] Got {len(similar_lead_tools)} Similar Lead Discovery tools")
                    tools.extend(similar_lead_tools)

                if agent.enable_hr_management:
                    print(f"[HR] Getting HR tools for agent {agent.id}")
                    hr_tools = self._get_hr_tools()
                    print(f"[HR] Got {len(hr_tools)} HR tools")
                    tools.extend(hr_tools)

                if agent.enable_cross_applet_data_access:
                    print(f"[CROSS_APPLET] Getting cross-applet query tools for agent {agent.id}")
                    cross_applet_tools = self._get_cross_applet_query_tools()
                    print(f"[CROSS_APPLET] Got {len(cross_applet_tools)} cross-applet query tools")
                    tools.extend(cross_applet_tools)

                # Add delegation tools for orchestrator agents
                if agent.is_orchestrator():
                    print(f"[DELEGATION] Getting agent delegation tools for orchestrator {agent.name}")
                    delegation_tools = self._get_agent_delegation_tools(agent, user)
                    print(f"[DELEGATION] Got {len(delegation_tools)} delegation tools")
                    tools.extend(delegation_tools)

                if tools:
                    api_params['tools'] = tools
                    current_app.logger.info(f"Agent {agent.name} has {len(tools)} tools available")

            # Call Claude API (potentially multiple times for tool use)
            response = self.client.messages.create(**api_params)
            print(f"[MCP DEBUG] Claude response stop_reason: {response.stop_reason}")

            # Handle tool use loop
            while response.stop_reason == "tool_use":
                # Extract tool calls from response
                tool_uses = [block for block in response.content if block.type == "tool_use"]
                print(f"[MCP DEBUG] Claude wants to use {len(tool_uses)} tools")

                if not tool_uses:
                    break

                # Add assistant's response to message history
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Execute tools and collect results
                tool_results = []
                for tool_use in tool_uses:
                    print(f"[TOOL] Executing tool: {tool_use.name} with input: {tool_use.input}")
                    try:
                        # Route to appropriate tool executor
                        if tool_use.name.startswith('outlook_'):
                            result = self._execute_outlook_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name.startswith('website_'):
                            result = self._execute_website_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name in ['generate_pdf_report', 'export_to_csv', 'create_spreadsheet', 'create_markdown_document', 'create_word_document']:
                            result = self._execute_file_generation_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name.startswith('competitive_analysis_'):
                            result = self._execute_competitive_analysis_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name.startswith('similar_leads_'):
                            result = self._execute_similar_lead_discovery_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name.startswith('hr_'):
                            result = self._execute_hr_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name.startswith('query_'):
                            result = self._execute_cross_applet_query_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name.startswith('consult_'):
                            # Handle agent delegation (Oscar consulting specialists)
                            result = self._execute_agent_delegation_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                orchestrator_agent=agent,
                                user=user,
                                db_message=None  # We don't have db_message in this context
                            )
                        else:
                            result = {"error": f"Unknown tool: {tool_use.name}"}

                        print(f"[TOOL] Tool {tool_use.name} returned: {result}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(result) if not isinstance(result, str) else result
                        })
                        current_app.logger.info(f"Tool {tool_use.name} executed successfully")
                    except Exception as e:
                        print(f"[TOOL] Tool {tool_use.name} failed with error: {e}")
                        current_app.logger.error(f"Tool {tool_use.name} failed: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "is_error": True,
                            "content": f"Error executing tool: {str(e)}"
                        })

                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                # Update api_params with new messages
                api_params['messages'] = messages

                # Get next response from Claude
                response = self.client.messages.create(**api_params)

            # Extract final text response
            text_blocks = [block.text for block in response.content if hasattr(block, 'text')]
            if text_blocks:
                return "\n".join(text_blocks)

            return "I apologize, but I couldn't generate a response. Please try again."

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            raise

    def _execute_outlook_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute Outlook tool using direct Microsoft Graph API

        Args:
            tool_name: Name of the tool (outlook_list_emails, etc.)
            tool_input: Tool input parameters
            agent: Agent making the request
            user: User context

        Returns:
            Tool execution result
        """
        from app.services.outlook_service import OutlookGraphService
        from app.models.integration import Integration

        print(f"[OUTLOOK] Executing tool: {tool_name} with input: {tool_input}")

        # Find Outlook integration
        integration = None
        if agent.created_by_id == user.id:
            integration = Integration.query.filter_by(
                integration_type='outlook',
                owner_type='user',
                owner_id=user.id,
                is_active=True
            ).first()

        if not integration:
            integration = Integration.query.filter_by(
                integration_type='outlook',
                owner_type='tenant',
                owner_id=agent.department.tenant_id,
                is_active=True
            ).first()

        if not integration or not integration.access_token:
            return {"error": "Outlook not connected. Please connect your Outlook account in Settings > Integrations."}

        # Check if token needs refresh
        if integration.needs_refresh():
            try:
                print(f"[OUTLOOK] Token needs refresh for integration {integration.id}")
                OutlookGraphService.refresh_access_token(integration)
                print(f"[OUTLOOK] Token refreshed successfully")
            except Exception as e:
                error_msg = f"Failed to refresh Outlook token: {str(e)}"
                print(f"[OUTLOOK] {error_msg}")
                return {"error": error_msg}

        # Create Outlook service with access token and integration for auto-refresh
        outlook = OutlookGraphService(integration.access_token, integration=integration)

        try:
            # Route to appropriate method
            if tool_name == 'outlook_list_emails':
                max_results = tool_input.get('max_results', 10)
                emails = outlook.list_emails(max_results=max_results)
                return {"emails": emails, "count": len(emails)}

            elif tool_name == 'outlook_read_email':
                email_id = tool_input.get('email_id')
                if not email_id:
                    return {"error": "email_id parameter is required"}
                email = outlook.read_email(email_id)
                return {"email": email}

            elif tool_name == 'outlook_search_emails':
                query = tool_input.get('query')
                if not query:
                    return {"error": "query parameter is required"}
                max_results = tool_input.get('max_results', 10)
                emails = outlook.search_emails(query, max_results=max_results)
                return {"emails": emails, "count": len(emails)}

            elif tool_name == 'outlook_send_email':
                to = tool_input.get('to', [])
                subject = tool_input.get('subject', '')
                body = tool_input.get('body', '')
                cc = tool_input.get('cc')

                if not to or not isinstance(to, list):
                    return {"error": "to parameter must be a list of email addresses"}

                result = outlook.send_email(to, subject, body, cc=cc)
                return result

            elif tool_name == 'outlook_list_calendar_events':
                max_results = tool_input.get('max_results', 10)
                days_ahead = tool_input.get('days_ahead', 7)
                events = outlook.list_calendar_events(max_results=max_results, days_ahead=days_ahead)
                return {"events": events, "count": len(events)}

            elif tool_name == 'outlook_create_calendar_event':
                subject = tool_input.get('subject')
                start = tool_input.get('start')
                end = tool_input.get('end')
                attendees = tool_input.get('attendees')
                location = tool_input.get('location')
                body = tool_input.get('body')
                is_online_meeting = tool_input.get('is_online_meeting', False)

                if not all([subject, start, end]):
                    return {"error": "subject, start, and end parameters are required"}

                result = outlook.create_calendar_event(
                    subject=subject,
                    start=start,
                    end=end,
                    attendees=attendees,
                    location=location,
                    body=body,
                    is_online_meeting=is_online_meeting
                )
                return result

            elif tool_name == 'outlook_get_free_busy':
                emails = tool_input.get('emails', [])
                start = tool_input.get('start')
                end = tool_input.get('end')

                if not emails or not isinstance(emails, list):
                    return {"error": "emails parameter must be a list of email addresses"}

                if not all([start, end]):
                    return {"error": "start and end parameters are required"}

                result = outlook.get_free_busy(emails=emails, start=start, end=end)
                return {"availability": result}

            else:
                return {"error": f"Unknown Outlook tool: {tool_name}"}

        except Exception as e:
            current_app.logger.error(f"Error executing Outlook tool {tool_name}: {e}")
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}

    def _execute_website_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute website builder tool

        Args:
            tool_name: Name of the tool (website_generate, etc.)
            tool_input: Tool input parameters
            agent: Agent making the request
            user: User context

        Returns:
            Tool execution result
        """
        from app.services.website_generator_service import website_generator
        from app.models.website import Website, WebsitePage, WebsiteTheme
        from app.models.tenant import Tenant
        from app import db
        from datetime import datetime

        print(f"[WEBSITE] Executing tool: {tool_name} with input: {tool_input}")

        # Get tenant from agent's department
        tenant = agent.department.tenant

        try:
            # Route to appropriate method
            if tool_name == 'website_generate':
                regenerate = tool_input.get('regenerate', False)

                # Check if website exists
                existing = Website.query.filter_by(tenant_id=tenant.id).first()
                if existing and not regenerate:
                    return {
                        "success": False,
                        "message": "Website already exists. Use regenerate=true to force regeneration.",
                        "website_url": f"/w/{tenant.slug}"
                    }

                # Generate website
                website = website_generator.generate_website_for_tenant(tenant, agent_id=agent.id)
                db.session.commit()

                return {
                    "success": True,
                    "message": "Website generated successfully",
                    "website_url": f"/w/{tenant.slug}",
                    "pages_created": website.pages.count(),
                    "is_published": website.is_published
                }

            elif tool_name == 'website_create_page':
                page_type = tool_input.get('page_type')
                slug = tool_input.get('slug')
                title = tool_input.get('title')
                content_description = tool_input.get('content_description')
                publish = tool_input.get('publish', False)

                # Validate inputs
                if not all([page_type, slug, title, content_description]):
                    return {"error": "Missing required parameters"}

                # Get or create website
                website = Website.query.filter_by(tenant_id=tenant.id).first()
                if not website:
                    return {"error": "No website found. Use website_generate first."}

                # Check if slug already exists
                existing = WebsitePage.query.filter_by(website_id=website.id, slug=slug).first()
                if existing:
                    return {"error": f"Page with slug '{slug}' already exists"}

                # Generate page content using AI
                prompt = f"""Create page content for: {title}

Page Type: {page_type}
Description: {content_description}

Generate a JSON structure with appropriate sections for this page type.
For landing pages, include hero, features, and CTA sections.
For blog posts, include title, author, date, content sections.
For custom pages, create relevant content sections based on the description.

Return ONLY valid JSON in this format:
{{
    "sections": [
        {{"type": "hero", "heading": "...", "subheading": "...", "cta_text": "...", "cta_url": "..."}},
        {{"type": "text", "heading": "...", "content": "<p>HTML content</p>"}}
    ]
}}"""

                response = self.client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2000,
                    temperature=0.8,
                    messages=[{"role": "user", "content": prompt}]
                )

                # Extract JSON from response
                content = response.content[0].text
                if '{' in content and '}' in content:
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    json_str = content[json_start:json_end]
                    content_json = json.loads(json_str)
                else:
                    content_json = {"sections": [{"type": "text", "heading": title, "content": f"<p>{content_description}</p>"}]}

                # Create page
                page = WebsitePage(
                    website_id=website.id,
                    page_type=page_type,
                    slug=slug,
                    title=title,
                    meta_description=content_description[:160],
                    content_json=content_json,
                    is_published=publish,
                    agent_id=agent.id,
                    created_by_id=user.id
                )

                if publish:
                    page.published_at = datetime.utcnow()

                db.session.add(page)
                db.session.commit()

                return {
                    "success": True,
                    "message": f"Page '{title}' created successfully",
                    "page_url": f"/w/{tenant.slug}/{slug}" if slug else f"/w/{tenant.slug}",
                    "is_published": publish
                }

            elif tool_name == 'website_update_theme':
                # Get website
                website = Website.query.filter_by(tenant_id=tenant.id).first()
                if not website:
                    return {"error": "No website found. Use website_generate first."}

                # Get or create theme
                if not website.theme:
                    theme = WebsiteTheme(website=website)
                    db.session.add(theme)
                else:
                    theme = website.theme

                # Update theme properties
                if 'primary_color' in tool_input:
                    theme.primary_color = tool_input['primary_color']
                if 'secondary_color' in tool_input:
                    theme.secondary_color = tool_input['secondary_color']
                if 'background_color' in tool_input:
                    theme.background_color = tool_input['background_color']
                if 'text_color' in tool_input:
                    theme.text_color = tool_input['text_color']
                if 'heading_font' in tool_input:
                    theme.heading_font = tool_input['heading_font']
                if 'body_font' in tool_input:
                    theme.body_font = tool_input['body_font']

                db.session.commit()

                return {
                    "success": True,
                    "message": "Theme updated successfully",
                    "theme": {
                        "primary_color": theme.primary_color,
                        "secondary_color": theme.secondary_color,
                        "background_color": theme.background_color,
                        "text_color": theme.text_color,
                        "heading_font": theme.heading_font,
                        "body_font": theme.body_font
                    }
                }

            elif tool_name == 'website_publish':
                publish = tool_input.get('publish')
                is_indexable = tool_input.get('is_indexable', True)

                if publish is None:
                    return {"error": "publish parameter is required"}

                # Get website
                website = Website.query.filter_by(tenant_id=tenant.id).first()
                if not website:
                    return {"error": "No website found. Use website_generate first."}

                # Update publishing status
                website.is_published = publish
                website.is_indexable = is_indexable

                if publish and not website.published_at:
                    website.published_at = datetime.utcnow()

                db.session.commit()

                return {
                    "success": True,
                    "message": f"Website {'published' if publish else 'unpublished'} successfully",
                    "is_published": website.is_published,
                    "is_indexable": website.is_indexable,
                    "website_url": f"/w/{tenant.slug}"
                }

            elif tool_name == 'website_get_status':
                # Get website
                website = Website.query.filter_by(tenant_id=tenant.id).first()

                if not website:
                    return {
                        "exists": False,
                        "message": "No website found. Use website_generate to create one."
                    }

                # Get pages
                pages = website.pages.all()
                published_pages = [p for p in pages if p.is_published]

                return {
                    "exists": True,
                    "is_published": website.is_published,
                    "is_indexable": website.is_indexable,
                    "website_url": f"/w/{tenant.slug}",
                    "total_pages": len(pages),
                    "published_pages": len(published_pages),
                    "pages": [
                        {
                            "title": p.title,
                            "slug": p.slug,
                            "type": p.page_type,
                            "is_published": p.is_published,
                            "views": p.view_count
                        }
                        for p in pages
                    ],
                    "theme": {
                        "primary_color": website.theme.primary_color if website.theme else None,
                        "secondary_color": website.theme.secondary_color if website.theme else None
                    } if website.theme else None
                }

            else:
                return {"error": f"Unknown website tool: {tool_name}"}

        except Exception as e:
            current_app.logger.error(f"Error executing website tool {tool_name}: {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}

    def _execute_file_generation_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute file generation tool

        Args:
            tool_name: Name of the tool (generate_pdf_report, export_to_csv, create_spreadsheet, create_markdown_document, create_word_document)
            tool_input: Tool input parameters
            agent: Agent model
            user: User model

        Returns:
            Result dictionary with file URL and metadata or error
        """
        from app.services.file_generation_service import FileGenerationService
        from app.models.generated_file import GeneratedFile
        from app import db

        print(f"[FILE_GEN] Executing tool: {tool_name}")
        print(f"[FILE_GEN] Input keys: {list(tool_input.keys())}")

        try:
            # Get tenant from agent's department
            if not agent or not agent.department:
                print(f"[FILE_GEN] ERROR: No workspace context available")
                return {"error": "No workspace context available"}

            tenant = agent.department.tenant
            print(f"[FILE_GEN] Tenant: {tenant.name} (ID: {tenant.id})")
            file_gen_service = FileGenerationService()

            if tool_name == "generate_pdf_report":
                # Generate PDF report
                title = tool_input.get('title')
                content_blocks = tool_input.get('content_blocks', [])
                filename = tool_input.get('filename')

                result = file_gen_service.generate_pdf(
                    title=title,
                    content_blocks=content_blocks,
                    tenant_id=tenant.id,
                    filename=filename
                )

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='report',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"PDF report '{result['filename']}' generated successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to generate PDF')}

            elif tool_name == "export_to_csv":
                # Export to CSV
                headers = tool_input.get('headers', [])
                data = tool_input.get('data', [])
                filename = tool_input.get('filename')

                print(f"[FILE_GEN] Generating CSV with {len(headers)} headers and {len(data)} rows")
                print(f"[FILE_GEN] Filename: {filename}")

                result = file_gen_service.generate_csv(
                    headers=headers,
                    data=data,
                    tenant_id=tenant.id,
                    filename=filename
                )

                print(f"[FILE_GEN] CSV generation result: success={result.get('success')}")

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='export',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"CSV file '{result['filename']}' exported successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to export CSV')}

            elif tool_name == "create_spreadsheet":
                # Create Excel spreadsheet
                sheets = tool_input.get('sheets', [])
                filename = tool_input.get('filename')

                result = file_gen_service.generate_excel(
                    sheets=sheets,
                    tenant_id=tenant.id,
                    filename=filename
                )

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='export',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"Excel file '{result['filename']}' created successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to create spreadsheet')}

            elif tool_name == "create_markdown_document":
                # Create Markdown document
                content = tool_input.get('content', '')
                title = tool_input.get('title')
                filename = tool_input.get('filename')

                result = file_gen_service.generate_markdown(
                    content=content,
                    tenant_id=tenant.id,
                    filename=filename,
                    title=title
                )

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='document',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"Markdown document '{result['filename']}' created successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to create Markdown document')}

            elif tool_name == "create_word_document":
                # Create Word document
                title = tool_input.get('title', 'Document')
                content_blocks = tool_input.get('content_blocks', [])
                filename = tool_input.get('filename')

                result = file_gen_service.generate_docx(
                    title=title,
                    content_blocks=content_blocks,
                    tenant_id=tenant.id,
                    filename=filename
                )

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='document',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"Word document '{result['filename']}' created successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to create Word document')}

            else:
                return {"error": f"Unknown file generation tool: {tool_name}"}

        except Exception as e:
            error_msg = f"Error executing file generation tool {tool_name}: {str(e)}"
            print(f"[FILE_GEN] ERROR: {error_msg}")
            current_app.logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to generate file: {str(e)}. Please check the file format and try again."}

    def _execute_competitive_analysis_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute competitive analysis tool

        Args:
            tool_name: Name of the tool (competitive_analysis_suggest_competitors, competitive_analysis_analyze, competitive_analysis_get_status)
            tool_input: Tool input parameters
            agent: Agent model
            user: User model

        Returns:
            Result dictionary with competitive analysis data or error
        """
        from app.services.competitive_analysis_service import competitive_analysis_service
        from app.services.competitor_identification_service import competitor_identification_service
        from app.models.competitor_profile import CompetitorProfile
        from app import db

        print(f"[COMPETITIVE] Executing tool: {tool_name}")
        print(f"[COMPETITIVE] Input: {tool_input}")

        try:
            # Get tenant and website from agent's department
            if not agent or not agent.department:
                return {"error": "No workspace context available"}

            tenant = agent.department.tenant
            website = tenant.website

            if not website:
                return {"error": "No website configured for this workspace. Please set up a website first."}

            print(f"[COMPETITIVE] Tenant: {tenant.name}, Website ID: {website.id}")

            if tool_name == "competitive_analysis_suggest_competitors":
                # Suggest competitors based on workspace context
                limit = tool_input.get('limit', 10)

                suggestions = competitor_identification_service.suggest_competitors(
                    tenant_id=tenant.id,
                    limit=limit
                )

                # Create CompetitorProfile records for suggestions
                created_count = 0
                for suggestion in suggestions:
                    existing = CompetitorProfile.query.filter_by(
                        website_id=website.id,
                        domain=suggestion['website']
                    ).first()

                    if not existing:
                        competitor = CompetitorProfile(
                            website_id=website.id,
                            company_name=suggestion['name'],
                            domain=suggestion['website'],
                            is_confirmed=False,
                            suggested_by_agent=True,
                            confidence_score=suggestion.get('confidence', 0.8),
                            source=suggestion.get('source', 'ai_suggested')
                        )
                        db.session.add(competitor)
                        created_count += 1

                db.session.commit()

                # Get all competitors for this website
                all_competitors = CompetitorProfile.query.filter_by(website_id=website.id).all()
                competitor_list = [
                    {
                        'id': c.id,
                        'name': c.company_name,
                        'domain': c.domain,
                        'confidence': c.confidence_score,
                        'is_confirmed': c.is_confirmed
                    }
                    for c in all_competitors
                ]

                return {
                    "success": True,
                    "message": f"Found {len(suggestions)} potential competitors. Created {created_count} new competitor profiles.",
                    "competitors": competitor_list,
                    "total_count": len(competitor_list)
                }

            elif tool_name == "competitive_analysis_analyze":
                # Run competitive analysis
                competitor_ids = tool_input.get('competitor_ids', [])
                analysis_type = tool_input.get('analysis_type', 'comprehensive')

                if not competitor_ids:
                    return {"error": "Please provide at least one competitor ID to analyze"}

                # Create and run analysis
                analysis = competitive_analysis_service.create_analysis(
                    website_id=website.id,
                    competitor_ids=competitor_ids,
                    analysis_type=analysis_type,
                    agent_id=agent.id
                )

                # Check if analysis completed
                if analysis.status == 'completed':
                    return {
                        "success": True,
                        "status": "completed",
                        "analysis_id": analysis.id,
                        "message": f"Competitive analysis completed successfully. Analyzed {analysis.competitor_count} competitors.",
                        "executive_summary": analysis.executive_summary,
                        "strengths_count": len(json.loads(analysis.strengths)) if analysis.strengths else 0,
                        "gaps_count": len(json.loads(analysis.gaps)) if analysis.gaps else 0,
                        "opportunities_count": len(json.loads(analysis.opportunities)) if analysis.opportunities else 0
                    }
                elif analysis.status == 'failed':
                    return {
                        "success": False,
                        "status": "failed",
                        "message": f"Analysis failed: {analysis.executive_summary}"
                    }
                else:
                    return {
                        "success": True,
                        "status": analysis.status,
                        "analysis_id": analysis.id,
                        "message": "Analysis is in progress. This may take 5-10 minutes."
                    }

            elif tool_name == "competitive_analysis_get_status":
                # Get latest analysis status
                analysis = competitive_analysis_service.get_latest_analysis(website.id)

                if not analysis:
                    return {
                        "success": True,
                        "status": "not_started",
                        "message": "No competitive analysis has been run yet."
                    }

                if analysis.status == 'completed':
                    import json
                    strengths = json.loads(analysis.strengths) if analysis.strengths else []
                    gaps = json.loads(analysis.gaps) if analysis.gaps else []
                    opportunities = json.loads(analysis.opportunities) if analysis.opportunities else []

                    return {
                        "success": True,
                        "status": "completed",
                        "analysis_id": analysis.id,
                        "created_at": analysis.created_at.isoformat(),
                        "competitor_count": analysis.competitor_count,
                        "executive_summary": analysis.executive_summary,
                        "strengths": strengths[:3],  # Top 3 strengths
                        "gaps": gaps[:3],  # Top 3 gaps
                        "opportunities": opportunities[:3]  # Top 3 opportunities
                    }
                else:
                    return {
                        "success": True,
                        "status": analysis.status,
                        "analysis_id": analysis.id,
                        "message": f"Analysis is currently {analysis.status}"
                    }

            else:
                return {"error": f"Unknown competitive analysis tool: {tool_name}"}

        except Exception as e:
            error_msg = f"Error executing competitive analysis tool {tool_name}: {str(e)}"
            print(f"[COMPETITIVE] ERROR: {error_msg}")
            current_app.logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def _execute_similar_lead_discovery_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute similar lead discovery tool

        Args:
            tool_name: Name of the tool (similar_leads_discover, similar_leads_get_status, similar_leads_list_discoveries)
            tool_input: Tool input parameters
            agent: Agent model
            user: User model

        Returns:
            Result dictionary with discovery data or error
        """
        from app.services.similar_lead_discovery_service import SimilarLeadDiscoveryService
        from app.models.similar_lead_discovery import SimilarLeadDiscovery
        from app.models.company import Company
        from app import db

        print(f"[SIMILAR_LEADS] Executing tool: {tool_name}")
        print(f"[SIMILAR_LEADS] Input: {tool_input}")

        try:
            # Get tenant from agent's department
            if not agent or not agent.department:
                return {"error": "No workspace context available"}

            tenant = agent.department.tenant
            service = SimilarLeadDiscoveryService()

            if tool_name == "similar_leads_discover":
                # Start discovery process
                reference_company_id = tool_input.get('reference_company_id')
                reference_company_name = tool_input.get('reference_company_name')

                # Look up company by ID or name
                if reference_company_id:
                    reference_company = Company.query.filter_by(
                        id=reference_company_id,
                        tenant_id=tenant.id
                    ).first()
                elif reference_company_name:
                    reference_company = Company.query.filter_by(
                        tenant_id=tenant.id
                    ).filter(Company.name.ilike(f'%{reference_company_name}%')).first()
                else:
                    return {"error": "Please provide either reference_company_id or reference_company_name"}

                if not reference_company:
                    return {"error": f"Reference company not found in your CRM"}

                # Parse criteria
                criteria = tool_input.get('criteria', {
                    'industry': True,
                    'business_model': True,
                    'tech_stack': True,
                    'company_size': True
                })

                max_results = tool_input.get('max_results', 20)

                # Create and start discovery
                discovery = service.create_discovery(
                    tenant_id=tenant.id,
                    reference_company_id=reference_company.id,
                    criteria=criteria,
                    max_results=max_results,
                    initiated_by='agent',
                    user_id=user.id if user else None,
                    agent_id=agent.id
                )

                return {
                    "success": True,
                    "discovery_id": discovery.id,
                    "reference_company": reference_company.name,
                    "status": "processing",
                    "message": f"Started discovering leads similar to {reference_company.name}. This may take 5-10 minutes.",
                    "estimated_time": "5-10 minutes"
                }

            elif tool_name == "similar_leads_get_status":
                # Get discovery status
                discovery_id = tool_input.get('discovery_id')

                if not discovery_id:
                    # Get most recent discovery for this tenant
                    discovery = SimilarLeadDiscovery.query.filter_by(
                        tenant_id=tenant.id
                    ).order_by(SimilarLeadDiscovery.created_at.desc()).first()
                else:
                    discovery = SimilarLeadDiscovery.query.filter_by(
                        id=discovery_id,
                        tenant_id=tenant.id
                    ).first()

                if not discovery:
                    return {
                        "success": True,
                        "status": "not_found",
                        "message": "No similar lead discovery found"
                    }

                response = {
                    "success": True,
                    "discovery_id": discovery.id,
                    "reference_company": discovery.reference_company_name,
                    "status": discovery.status,
                    "progress_percentage": discovery.progress_percentage,
                    "progress_message": discovery.progress_message
                }

                if discovery.status == 'completed':
                    response.update({
                        "discovered_count": discovery.discovered_count,
                        "leads_created": discovery.leads_created,
                        "summary": discovery.discovery_summary,
                        "completed_at": discovery.completed_at.isoformat() if discovery.completed_at else None
                    })
                elif discovery.status == 'failed':
                    response.update({
                        "error": discovery.error_message
                    })

                return response

            elif tool_name == "similar_leads_list_discoveries":
                # List recent discoveries
                limit = tool_input.get('limit', 10)

                discoveries = SimilarLeadDiscovery.query.filter_by(
                    tenant_id=tenant.id
                ).order_by(SimilarLeadDiscovery.created_at.desc()).limit(limit).all()

                return {
                    "success": True,
                    "discoveries": [
                        {
                            "id": d.id,
                            "reference_company": d.reference_company_name,
                            "status": d.status,
                            "discovered_count": d.discovered_count,
                            "leads_created": d.leads_created,
                            "created_at": d.created_at.isoformat()
                        }
                        for d in discoveries
                    ]
                }

            else:
                return {"error": f"Unknown similar lead discovery tool: {tool_name}"}

        except Exception as e:
            error_msg = f"Error executing similar lead discovery tool {tool_name}: {str(e)}"
            print(f"[SIMILAR_LEADS] ERROR: {error_msg}")
            current_app.logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def _execute_hr_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute HR management tool

        Args:
            tool_name: Name of the tool (hr_search_candidates, hr_schedule_interview, etc.)
            tool_input: Tool input parameters
            agent: Agent model
            user: User model

        Returns:
            Result dictionary with HR data or error
        """
        from app.services.hr_service import hr_service
        from app.services.email_service import email_service
        from app.models.candidate import Candidate
        from app.models.interview import Interview
        from app.models.employee import Employee
        from app.models.onboarding_plan import OnboardingPlan, OnboardingTask
        from app.models.pto_request import PTORequest
        from app import db
        from datetime import datetime, date

        print(f"[HR] Executing tool: {tool_name}")
        print(f"[HR] Input: {tool_input}")

        try:
            # Get tenant from agent's department
            if not agent or not agent.department:
                return {"error": "No workspace context available"}

            tenant = agent.department.tenant

            # ===== RECRUITMENT TOOLS =====
            if tool_name == 'hr_search_candidates':
                candidates = hr_service.search_candidates(
                    tenant_id=tenant.id,
                    job_position=tool_input.get('job_position'),
                    status=tool_input.get('status'),
                    min_score=tool_input.get('min_score'),
                    skills=tool_input.get('skills'),
                    max_results=tool_input.get('max_results', 20)
                )

                return {
                    "success": True,
                    "count": len(candidates),
                    "candidates": [
                        {
                            "id": c.id,
                            "name": c.full_name,
                            "email": c.email,
                            "position": c.position,
                            "status": c.status,
                            "overall_score": c.overall_score,
                            "applied_date": c.applied_date.isoformat(),
                            "experience_years": c.experience_years
                        }
                        for c in candidates
                    ]
                }

            elif tool_name == 'hr_get_candidate_details':
                candidate_id = tool_input.get('candidate_id')
                candidate = Candidate.query.filter_by(
                    id=candidate_id,
                    tenant_id=tenant.id
                ).first()

                if not candidate:
                    return {"error": f"Candidate {candidate_id} not found"}

                # Get interview history
                interviews = Interview.query.filter_by(
                    candidate_id=candidate.id
                ).order_by(Interview.scheduled_date.desc()).all()

                return {
                    "success": True,
                    "candidate": {
                        "id": candidate.id,
                        "name": candidate.full_name,
                        "email": candidate.email,
                        "phone": candidate.phone,
                        "position": candidate.position,
                        "status": candidate.status,
                        "applied_date": candidate.applied_date.isoformat(),
                        "overall_score": candidate.overall_score,
                        "category_scores": candidate.get_category_scores(),
                        "skills": candidate.get_skills_list(),
                        "experience_years": candidate.experience_years,
                        "resume_url": candidate.resume_url,
                        "linkedin_url": candidate.linkedin_url,
                        "notes": candidate.get_notes(),
                        "interviews": [
                            {
                                "id": i.id,
                                "type": i.interview_type,
                                "scheduled_date": i.scheduled_date.isoformat(),
                                "duration_minutes": i.duration_minutes,
                                "status": i.status,
                                "interviewers": i.interviewers_list,
                                "score": i.score
                            }
                            for i in interviews
                        ]
                    }
                }

            elif tool_name == 'hr_score_candidate':
                candidate_id = tool_input.get('candidate_id')
                candidate = Candidate.query.filter_by(
                    id=candidate_id,
                    tenant_id=tenant.id
                ).first()

                if not candidate:
                    return {"error": f"Candidate {candidate_id} not found"}

                # Update scores
                if 'overall_score' in tool_input:
                    candidate.overall_score = tool_input['overall_score']

                if 'category_scores' in tool_input:
                    candidate.update_category_scores(tool_input['category_scores'])

                if 'note' in tool_input:
                    candidate.add_assessment_note(
                        note=tool_input['note'],
                        scored_by=user.full_name if user else agent.name
                    )

                db.session.commit()

                return {
                    "success": True,
                    "message": "Candidate scoring updated",
                    "candidate_id": candidate.id,
                    "overall_score": candidate.overall_score,
                    "category_scores": candidate.get_category_scores()
                }

            elif tool_name == 'hr_schedule_interview':
                candidate_id = tool_input.get('candidate_id')
                candidate = Candidate.query.filter_by(
                    id=candidate_id,
                    tenant_id=tenant.id
                ).first()

                if not candidate:
                    return {"error": f"Candidate {candidate_id} not found"}

                # Schedule interview
                interview = hr_service.schedule_interview(
                    candidate=candidate,
                    interview_type=tool_input['interview_type'],
                    start_time=tool_input['start_time'],
                    duration_minutes=tool_input.get('duration_minutes', 60),
                    interviewers=tool_input['interviewers'],
                    location=tool_input.get('location'),
                    notes=tool_input.get('notes')
                )

                db.session.commit()

                # Calculate end time for response
                end_time = hr_service.calculate_end_time(
                    tool_input['start_time'],
                    interview.duration_minutes
                )

                # Send invitation email
                email_service.send_interview_invitation(candidate, interview)

                return {
                    "success": True,
                    "message": "Interview scheduled successfully",
                    "interview_id": interview.id,
                    "candidate_name": candidate.full_name,
                    "interview_type": interview.interview_type,
                    "start_time": interview.scheduled_date.isoformat(),
                    "end_time": end_time,
                    "interviewers": interview.interviewers_list,
                    "location": interview.location
                }

            elif tool_name == 'hr_move_candidate_stage':
                candidate_id = tool_input.get('candidate_id')
                candidate = Candidate.query.filter_by(
                    id=candidate_id,
                    tenant_id=tenant.id
                ).first()

                if not candidate:
                    return {"error": f"Candidate {candidate_id} not found"}

                old_status = candidate.status
                new_status = tool_input['new_status']
                reason = tool_input.get('reason')
                send_notification = tool_input.get('send_notification', True)

                # Update status
                candidate.update_status(new_status, reason)
                db.session.commit()

                # Send notification if requested
                if send_notification:
                    email_service.send_candidate_status_update(
                        candidate, old_status, new_status, reason
                    )

                return {
                    "success": True,
                    "message": f"Candidate moved from {old_status} to {new_status}",
                    "candidate_id": candidate.id,
                    "candidate_name": candidate.full_name,
                    "old_status": old_status,
                    "new_status": new_status,
                    "notification_sent": send_notification
                }

            # ===== ONBOARDING TOOLS =====
            elif tool_name == 'hr_create_onboarding_plan':
                employee_id = tool_input.get('employee_id')
                employee = Employee.query.filter_by(
                    id=employee_id,
                    tenant_id=tenant.id
                ).first()

                if not employee:
                    return {"error": f"Employee {employee_id} not found"}

                # Check if plan already exists
                existing_plan = OnboardingPlan.query.filter_by(
                    employee_id=employee.id
                ).first()

                if existing_plan:
                    return {
                        "error": "Onboarding plan already exists for this employee",
                        "plan_id": existing_plan.id
                    }

                # Create onboarding plan
                plan = hr_service.create_onboarding_plan(
                    employee=employee,
                    start_date=tool_input['start_date'],
                    template=tool_input.get('template', 'standard'),
                    custom_tasks=tool_input.get('custom_tasks'),
                    buddy_email=tool_input.get('buddy_email')
                )

                db.session.commit()

                # Send welcome email
                email_service.send_onboarding_welcome(employee, plan)

                return {
                    "success": True,
                    "message": "Onboarding plan created successfully",
                    "plan_id": plan.id,
                    "employee_name": employee.full_name,
                    "start_date": plan.start_date.isoformat(),
                    "template": plan.template,
                    "task_count": plan.tasks.count(),
                    "buddy_email": plan.buddy_email
                }

            elif tool_name == 'hr_get_onboarding_status':
                employee_id = tool_input.get('employee_id')
                employee = Employee.query.filter_by(
                    id=employee_id,
                    tenant_id=tenant.id
                ).first()

                if not employee:
                    return {"error": f"Employee {employee_id} not found"}

                plan = employee.onboarding_plan
                if not plan:
                    return {
                        "success": True,
                        "status": "not_started",
                        "message": "No onboarding plan exists for this employee"
                    }

                # Get task summary
                summary = plan.get_tasks_summary()
                overdue_tasks = plan.get_overdue_tasks()

                return {
                    "success": True,
                    "plan_id": plan.id,
                    "employee_name": employee.full_name,
                    "start_date": plan.start_date.isoformat(),
                    "template": plan.template,
                    "completion_percentage": plan.completion_percentage,
                    "total_tasks": summary['total'],
                    "completed_tasks": summary['completed'],
                    "pending_tasks": summary['pending'],
                    "overdue_count": len(overdue_tasks),
                    "overdue_tasks": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "due_date": t.due_date.isoformat(),
                            "category": t.category
                        }
                        for t in overdue_tasks
                    ]
                }

            elif tool_name == 'hr_send_onboarding_reminder':
                employee_id = tool_input.get('employee_id')
                employee = Employee.query.filter_by(
                    id=employee_id,
                    tenant_id=tenant.id
                ).first()

                if not employee:
                    return {"error": f"Employee {employee_id} not found"}

                plan = employee.onboarding_plan
                if not plan:
                    return {"error": "No onboarding plan exists for this employee"}

                # Get overdue tasks
                overdue_tasks = plan.get_overdue_tasks()
                if not overdue_tasks:
                    return {
                        "success": True,
                        "message": "No overdue tasks to remind about"
                    }

                # Send reminder
                include_manager = tool_input.get('include_manager', False)
                email_service.send_onboarding_reminders(
                    employee, overdue_tasks, include_manager
                )

                return {
                    "success": True,
                    "message": "Onboarding reminders sent",
                    "employee_name": employee.full_name,
                    "overdue_count": len(overdue_tasks),
                    "manager_notified": include_manager
                }

            # ===== EMPLOYEE RECORDS TOOLS =====
            elif tool_name == 'hr_search_employees':
                employees = hr_service.search_employees(
                    tenant_id=tenant.id,
                    department=tool_input.get('department'),
                    status=tool_input.get('status'),
                    role=tool_input.get('role'),
                    search_query=tool_input.get('search_query'),
                    max_results=tool_input.get('max_results', 50)
                )

                return {
                    "success": True,
                    "count": len(employees),
                    "employees": [
                        {
                            "id": e.id,
                            "employee_number": e.employee_number,
                            "name": e.full_name,
                            "email": e.email,
                            "department": e.department_name,
                            "role": e.role,
                            "status": e.status,
                            "hire_date": e.hire_date.isoformat()
                        }
                        for e in employees
                    ]
                }

            elif tool_name == 'hr_get_employee_record':
                employee_id = tool_input.get('employee_id')
                employee = Employee.query.filter_by(
                    id=employee_id,
                    tenant_id=tenant.id
                ).first()

                if not employee:
                    return {"error": f"Employee {employee_id} not found"}

                return {
                    "success": True,
                    "employee": {
                        "id": employee.id,
                        "employee_number": employee.employee_number,
                        "name": employee.full_name,
                        "email": employee.email,
                        "phone": employee.phone,
                        "department": employee.department_name,
                        "role": employee.role,
                        "manager": employee.manager_name,
                        "status": employee.status,
                        "hire_date": employee.hire_date.isoformat(),
                        "termination_date": employee.termination_date.isoformat() if employee.termination_date else None,
                        "salary": float(employee.salary) if employee.salary else None,
                        "salary_currency": employee.salary_currency,
                        "bonus_target_percentage": employee.bonus_target_percentage,
                        "pto_balance": employee.pto_balance,
                        "pto_used_this_year": employee.pto_used_this_year,
                        "sick_days_balance": employee.sick_days_balance
                    }
                }

            elif tool_name == 'hr_add_employee_note':
                employee_id = tool_input.get('employee_id')
                employee = Employee.query.filter_by(
                    id=employee_id,
                    tenant_id=tenant.id
                ).first()

                if not employee:
                    return {"error": f"Employee {employee_id} not found"}

                # Add note
                employee.add_hr_note(
                    note=tool_input['note'],
                    note_type=tool_input.get('note_type', 'general'),
                    created_by=user.full_name if user else agent.name
                )

                db.session.commit()

                return {
                    "success": True,
                    "message": "Note added to employee record",
                    "employee_id": employee.id,
                    "employee_name": employee.full_name,
                    "note_type": tool_input.get('note_type', 'general')
                }

            # ===== TIME OFF TOOLS =====
            elif tool_name == 'hr_get_pto_balance':
                employee_id = tool_input.get('employee_id')
                employee = Employee.query.filter_by(
                    id=employee_id,
                    tenant_id=tenant.id
                ).first()

                if not employee:
                    return {"error": f"Employee {employee_id} not found"}

                # Get upcoming PTO
                upcoming_pto = PTORequest.query.filter(
                    PTORequest.employee_id == employee.id,
                    PTORequest.start_date >= date.today(),
                    PTORequest.status == 'approved'
                ).order_by(PTORequest.start_date).all()

                return {
                    "success": True,
                    "employee_name": employee.full_name,
                    "pto_balance": employee.pto_balance,
                    "pto_used_this_year": employee.pto_used_this_year,
                    "sick_days_balance": employee.sick_days_balance,
                    "upcoming_pto": [
                        {
                            "id": pto.id,
                            "start_date": pto.start_date.isoformat(),
                            "end_date": pto.end_date.isoformat(),
                            "total_days": pto.total_days,
                            "request_type": pto.request_type
                        }
                        for pto in upcoming_pto
                    ]
                }

            elif tool_name == 'hr_view_team_calendar':
                calendar_entries = hr_service.get_team_pto_calendar(
                    tenant_id=tenant.id,
                    department=tool_input.get('department'),
                    days_ahead=tool_input.get('days_ahead', 30),
                    include_pending=tool_input.get('include_pending', True)
                )

                return {
                    "success": True,
                    "entries": calendar_entries,
                    "count": len(calendar_entries)
                }

            elif tool_name == 'hr_review_pto_request':
                request_id = tool_input.get('request_id')
                pto_request = PTORequest.query.filter_by(
                    id=request_id,
                    tenant_id=tenant.id
                ).first()

                if not pto_request:
                    return {"error": f"PTO request {request_id} not found"}

                if pto_request.status != 'pending':
                    return {
                        "error": f"Cannot review request - status is already {pto_request.status}"
                    }

                action = tool_input['action']
                reviewer_name = tool_input['reviewer_name']

                if action == 'approve':
                    pto_request.approve(reviewer_name)
                    db.session.commit()

                    # Send notification
                    email_service.send_pto_decision_notification(
                        pto_request, 'approved', None
                    )

                    return {
                        "success": True,
                        "message": "PTO request approved",
                        "request_id": pto_request.id,
                        "employee_name": pto_request.employee.full_name,
                        "start_date": pto_request.start_date.isoformat(),
                        "end_date": pto_request.end_date.isoformat(),
                        "total_days": pto_request.total_days,
                        "new_pto_balance": pto_request.employee.pto_balance
                    }

                elif action == 'deny':
                    denial_reason = tool_input.get('denial_reason')
                    if not denial_reason:
                        return {"error": "denial_reason is required when denying a request"}

                    pto_request.deny(reviewer_name, denial_reason)
                    db.session.commit()

                    # Send notification
                    email_service.send_pto_decision_notification(
                        pto_request, 'denied', denial_reason
                    )

                    return {
                        "success": True,
                        "message": "PTO request denied",
                        "request_id": pto_request.id,
                        "employee_name": pto_request.employee.full_name,
                        "denial_reason": denial_reason
                    }

                else:
                    return {"error": f"Invalid action: {action}"}

            else:
                return {"error": f"Unknown HR tool: {tool_name}"}

        except Exception as e:
            error_msg = f"Error executing HR tool {tool_name}: {str(e)}"
            print(f"[HR] ERROR: {error_msg}")
            current_app.logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def _execute_cross_applet_query_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """Execute read-only cross-applet query tools"""
        if not agent or not agent.department:
            return {"error": "No workspace context available"}

        tenant = agent.department.tenant

        # Route to appropriate handler
        try:
            if tool_name.startswith('query_crm_'):
                return self._execute_crm_query(tool_name, tool_input, tenant)
            elif tool_name.startswith('query_files_'):
                return self._execute_files_query(tool_name, tool_input, tenant)
            elif tool_name.startswith('query_hr_'):
                return self._execute_hr_query(tool_name, tool_input, tenant)
            elif tool_name.startswith('query_support_'):
                return self._execute_support_query(tool_name, tool_input, tenant)
            elif tool_name.startswith('query_project'):
                return self._execute_project_query(tool_name, tool_input, tenant)
            else:
                return {"error": f"Unknown query tool: {tool_name}"}
        except Exception as e:
            error_msg = f"Error executing query tool {tool_name}: {str(e)}"
            print(f"[CROSS_APPLET] ERROR: {error_msg}")
            current_app.logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def _execute_crm_query(self, tool_name: str, tool_input: Dict, tenant) -> Any:
        """Execute CRM query tools"""
        from app.models.company import Company
        from app.models.contact import Contact
        from app.models.deal import Deal

        if tool_name == 'query_crm_companies':
            companies = Company.query.filter_by(tenant_id=tenant.id)
            if tool_input.get('search_query'):
                companies = companies.filter(Company.name.ilike(f"%{tool_input['search_query']}%"))
            if tool_input.get('status'):
                companies = companies.filter_by(status=tool_input['status'])
            if tool_input.get('industry'):
                companies = companies.filter(Company.industry.ilike(f"%{tool_input['industry']}%"))
            companies = companies.limit(tool_input.get('max_results', 20)).all()
            return {"companies": [c.to_dict() for c in companies]}

        elif tool_name == 'query_crm_contacts':
            contacts = Contact.query.filter_by(tenant_id=tenant.id)
            if tool_input.get('search_query'):
                query = f"%{tool_input['search_query']}%"
                contacts = contacts.filter(
                    (Contact.first_name.ilike(query)) | (Contact.last_name.ilike(query)) | (Contact.email.ilike(query))
                )
            if tool_input.get('company_id'):
                contacts = contacts.filter_by(company_id=tool_input['company_id'])
            contacts = contacts.limit(tool_input.get('max_results', 20)).all()
            return {"contacts": [c.to_dict() for c in contacts]}

        elif tool_name == 'query_crm_deals':
            deals = Deal.query.filter_by(tenant_id=tenant.id)
            if tool_input.get('status'):
                deals = deals.filter_by(status=tool_input['status'])
            if tool_input.get('min_amount'):
                deals = deals.filter(Deal.amount >= tool_input['min_amount'])
            if tool_input.get('company_id'):
                deals = deals.filter_by(company_id=tool_input['company_id'])
            deals = deals.limit(tool_input.get('max_results', 20)).all()
            return {"deals": [d.to_dict() for d in deals]}

        elif tool_name == 'query_crm_deal_details':
            deal = Deal.query.filter_by(tenant_id=tenant.id, id=tool_input['deal_id']).first()
            if not deal:
                return {"error": "Deal not found"}
            return {"deal": deal.to_dict(include_relationships=True)}

        return {"error": f"Unknown CRM query tool: {tool_name}"}

    def _execute_files_query(self, tool_name: str, tool_input: Dict, tenant) -> Any:
        """Execute Files query tools"""
        from app.models.generated_file import GeneratedFile

        if tool_name == 'query_files_workspace':
            files = GeneratedFile.query.filter_by(tenant_id=tenant.id)

            # Filter by file type
            if tool_input.get('file_type') and tool_input['file_type'] != 'all':
                files = files.filter_by(file_type=tool_input['file_type'])

            # Search by filename
            if tool_input.get('search_query'):
                files = files.filter(GeneratedFile.filename.ilike(f"%{tool_input['search_query']}%"))

            files = files.order_by(GeneratedFile.created_at.desc()).limit(tool_input.get('max_results', 50)).all()
            return {"files": [f.to_dict() for f in files], "count": len(files)}

        elif tool_name == 'query_files_by_user':
            files = GeneratedFile.query.filter_by(tenant_id=tenant.id, user_id=tool_input['user_id'])

            # Filter by file type
            if tool_input.get('file_type') and tool_input['file_type'] != 'all':
                files = files.filter_by(file_type=tool_input['file_type'])

            files = files.order_by(GeneratedFile.created_at.desc()).limit(tool_input.get('max_results', 50)).all()
            return {"files": [f.to_dict() for f in files], "count": len(files)}

        elif tool_name == 'query_files_by_agent':
            files = GeneratedFile.query.filter_by(agent_id=tool_input['agent_id'])

            # Filter by file type
            if tool_input.get('file_type') and tool_input['file_type'] != 'all':
                files = files.filter_by(file_type=tool_input['file_type'])

            files = files.order_by(GeneratedFile.created_at.desc()).limit(tool_input.get('max_results', 50)).all()
            return {"files": [f.to_dict() for f in files], "count": len(files)}

        return {"error": f"Unknown Files query tool: {tool_name}"}

    def _execute_hr_query(self, tool_name: str, tool_input: Dict, tenant) -> Any:
        """Execute HR query tools (excludes sensitive data like compensation)"""
        from app.models.employee import Employee
        from app.models.candidate import Candidate
        from app.models.pto_request import PTORequest
        from app.services.hr_service import hr_service

        if tool_name == 'query_hr_employees':
            employees = hr_service.search_employees(tenant.id, tool_input)
            # Exclude sensitive data
            return {"employees": [
                {k: v for k, v in e.to_dict().items()
                 if k not in ['salary', 'bonus_target_percentage', 'notes']}
                for e in employees
            ]}

        elif tool_name == 'query_hr_candidates':
            candidates = hr_service.search_candidates(tenant.id, tool_input)
            return {"candidates": [c.to_dict() for c in candidates]}

        elif tool_name == 'query_hr_employee_record':
            employee = Employee.query.filter_by(tenant_id=tenant.id, id=tool_input['employee_id']).first()
            if not employee:
                return {"error": "Employee not found"}
            # Exclude sensitive fields
            data = employee.to_dict()
            for field in ['salary', 'bonus_target_percentage', 'notes']:
                data.pop(field, None)
            return {"employee": data}

        elif tool_name == 'query_hr_pto_calendar':
            calendar = hr_service.get_team_pto_calendar(
                tenant.id,
                tool_input.get('department'),
                tool_input.get('days_ahead', 30)
            )
            return {"pto_calendar": calendar}

        elif tool_name == 'query_hr_pto_balance':
            employee = Employee.query.filter_by(tenant_id=tenant.id, id=tool_input['employee_id']).first()
            if not employee:
                return {"error": "Employee not found"}
            return {
                "employee_name": employee.full_name,
                "pto_balance": employee.pto_balance,
                "pto_used_this_year": employee.pto_used_this_year
            }

        return {"error": f"Unknown HR query tool: {tool_name}"}

    def _execute_support_query(self, tool_name: str, tool_input: Dict, tenant) -> Any:
        """Execute Support query tools"""
        from app.models.ticket import Ticket
        from sqlalchemy import func

        if tool_name == 'query_support_tickets':
            tickets = Ticket.query.filter_by(tenant_id=tenant.id)
            if tool_input.get('status'):
                tickets = tickets.filter_by(status=tool_input['status'])
            if tool_input.get('priority'):
                tickets = tickets.filter_by(priority=tool_input['priority'])
            if tool_input.get('search_query'):
                query = f"%{tool_input['search_query']}%"
                tickets = tickets.filter(
                    (Ticket.subject.ilike(query)) | (Ticket.description.ilike(query))
                )
            tickets = tickets.limit(tool_input.get('max_results', 25)).all()
            return {"tickets": [t.to_dict() for t in tickets]}

        elif tool_name == 'query_support_ticket_details':
            ticket = Ticket.query.filter_by(tenant_id=tenant.id, id=tool_input['ticket_id']).first()
            if not ticket:
                return {"error": "Ticket not found"}
            return {"ticket": ticket.to_dict(include_comments=True)}

        elif tool_name == 'query_support_metrics':
            from app import db
            tickets = Ticket.query.filter_by(tenant_id=tenant.id)
            if tool_input.get('department_id'):
                tickets = tickets.filter_by(department_id=tool_input['department_id'])

            status_counts = dict(
                db.session.query(Ticket.status, func.count(Ticket.id))
                .filter(Ticket.tenant_id == tenant.id)
                .group_by(Ticket.status)
                .all()
            )
            return {"metrics": {"status_counts": status_counts, "total": sum(status_counts.values())}}

        return {"error": f"Unknown Support query tool: {tool_name}"}

    def _execute_project_query(self, tool_name: str, tool_input: Dict, tenant) -> Any:
        """Execute Project query tools"""
        from app.models.project import Project, Task

        if tool_name == 'query_project_tasks':
            tasks = Task.query.join(Project).filter(Project.tenant_id == tenant.id)
            if tool_input.get('project_id'):
                tasks = tasks.filter(Task.project_id == tool_input['project_id'])
            if tool_input.get('status'):
                tasks = tasks.filter(Task.status == tool_input['status'])
            if tool_input.get('assigned_to_id'):
                tasks = tasks.filter(Task.assigned_to_id == tool_input['assigned_to_id'])
            tasks = tasks.limit(tool_input.get('max_results', 50)).all()
            return {"tasks": [t.to_dict() for t in tasks]}

        elif tool_name == 'query_project_details':
            project = Project.query.filter_by(tenant_id=tenant.id, id=tool_input['project_id']).first()
            if not project:
                return {"error": "Project not found"}
            return {"project": project.to_dict(include_tasks=True)}

        elif tool_name == 'query_projects_list':
            projects = Project.query.filter_by(tenant_id=tenant.id)
            if not tool_input.get('is_archived', False):
                projects = projects.filter_by(is_archived=False)
            projects = projects.limit(tool_input.get('max_results', 20)).all()
            return {"projects": [p.to_dict() for p in projects]}

        return {"error": f"Unknown Project query tool: {tool_name}"}

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

    def detect_long_running_task(self, task_description: str, task_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Detect if a task requires special long-running orchestration.

        DISABLED: All tasks for AI agents execute immediately through normal chat.
        AI agents complete tasks in seconds/minutes, not hours. The multi-step
        worker system is only needed for truly long-running operations that
        require pausing/resuming (e.g., processing 10,000+ records with rate limits).

        Args:
            task_description: The task description to analyze
            task_context: Optional context (assigned_to, due_date, etc.)

        Returns:
            Dictionary with:
                - is_long_running: bool (always False)
                - estimated_duration_seconds: int
                - reasoning: str
                - complexity_score: int (1-10)
        """
        # DISABLED: All tasks execute immediately for AI agents
        # AI agents complete work in seconds/minutes, not hours
        # The complex multi-step worker system was over-engineering
        return {
            'is_long_running': False,
            'estimated_duration_seconds': 30,  # Typical AI response time
            'reasoning': 'AI agents execute tasks immediately through chat (disabled long-running detection)',
            'complexity_score': 5
        }

    def generate_execution_plan(
        self,
        task_description: str,
        task_id: int,
        agent_name: str,
        tenant_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate a detailed execution plan for a long-running task.
        Uses Sonnet for high-quality planning.

        Args:
            task_description: The task to plan
            task_id: ID of the task being planned
            agent_name: Name of the agent that will execute
            tenant_context: Optional tenant/workspace context

        Returns:
            Dictionary with:
                - steps: List[Dict] with step details
                - estimated_duration_minutes: int
                - requires_approval: bool
                - approval_reasoning: str
                - risks: List[str]
                - success_criteria: List[str]
        """
        context_str = "No additional context provided."
        if tenant_context:
            context_parts = []
            if tenant_context.get('tenant_name'):
                context_parts.append(f"Workspace: {tenant_context['tenant_name']}")
            if tenant_context.get('industry'):
                context_parts.append(f"Industry: {tenant_context['industry']}")
            if tenant_context.get('user_name'):
                context_parts.append(f"Requested by: {tenant_context['user_name']}")
            context_str = "\n".join(context_parts)

        system_prompt = f"""You are {agent_name}, an AI agent creating a detailed execution plan for a long-running task.

{context_str}

Your job is to:
1. Break down the task into clear, sequential steps
2. Estimate how long the entire task will take
3. Determine if user approval is needed before execution
4. Identify potential risks or issues
5. Define clear success criteria

Require approval for tasks that:
- Modify critical business data (financial records, customer data)
- Send external communications (emails, API calls to 3rd parties)
- Make irreversible changes (deletions, production deployments)
- Involve sensitive information or compliance concerns
- Have high business impact or cost implications

Do NOT require approval for:
- Read-only analysis and reporting
- Internal document generation
- Data aggregation and visualization
- Research and information gathering
- Development/testing tasks in non-production

Respond ONLY with valid JSON in this format:
{{
  "steps": [
    {{
      "step_number": 1,
      "title": "Brief step title",
      "description": "What will be done in this step",
      "estimated_duration_seconds": <number>,
      "dependencies": []
    }}
  ],
  "estimated_duration_minutes": <total minutes>,
  "requires_approval": true/false,
  "approval_reasoning": "Why approval is/isn't needed",
  "risks": ["risk 1", "risk 2"],
  "success_criteria": ["criterion 1", "criterion 2"]
}}"""

        prompt = f"""Create a detailed execution plan for this task:

Task ID: {task_id}
Task Description: {task_description}

Provide your plan in the requested JSON format."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",  # Use Sonnet for planning
                max_tokens=2000,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract and parse JSON response
            response_text = response.content[0].text.strip()

            # Handle markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            result = json.loads(response_text)

            # Validate required fields
            required_fields = ['steps', 'estimated_duration_minutes', 'requires_approval', 'approval_reasoning', 'risks', 'success_criteria']
            if not all(field in result for field in required_fields):
                raise ValueError("AI response missing required fields")

            return result

        except Exception as e:
            print(f"Error generating execution plan: {e}")
            import traceback
            traceback.print_exc()
            # Return a basic fallback plan
            return {
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Execute task',
                        'description': task_description,
                        'estimated_duration_seconds': 60,
                        'dependencies': []
                    }
                ],
                'estimated_duration_minutes': 1,
                'requires_approval': True,  # Conservative default
                'approval_reasoning': 'Error during planning, requiring approval for safety',
                'risks': ['Unable to generate detailed plan'],
                'success_criteria': ['Task completed without errors']
            }

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 1.0,
        agent=None,
        user=None
    ):
        """
        Stream a chat response from Claude.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: System prompt defining the agent's behavior
            model: Model to use (defaults to Haiku)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            agent: Agent model (for MCP integration support)
            user: User model (for MCP integration support)

        Yields:
            Text chunks as they arrive from the API
        """
        if model is None:
            model = self.DEFAULT_MODEL

        try:
            # Build API call parameters
            stream_params = {
                'model': model,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'system': system_prompt,
                'messages': messages
            }

            with self.client.messages.stream(**stream_params) as stream:
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
