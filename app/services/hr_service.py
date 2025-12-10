"""
HR Service
Handles HR management operations for candidates, employees, onboarding, and PTO
"""
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict
from app import db
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.onboarding_plan import OnboardingPlan, OnboardingTask
from app.models.interview import Interview
from app.models.pto_request import PTORequest


class HRService:
    """Service for HR management operations"""

    # ===== RECRUITMENT METHODS =====

    def search_candidates(
        self,
        tenant_id: int,
        job_position: Optional[str] = None,
        status: Optional[str] = None,
        min_score: Optional[float] = None,
        skills: Optional[List[str]] = None,
        max_results: int = 20
    ) -> List[Candidate]:
        """
        Search candidates with filters

        Args:
            tenant_id: Tenant ID
            job_position: Filter by job position
            status: Filter by status
            min_score: Minimum applicant score
            skills: List of required skills
            max_results: Maximum results to return

        Returns:
            List of Candidate objects
        """
        query = Candidate.query.filter_by(tenant_id=tenant_id)

        if job_position:
            query = query.filter(Candidate.position.ilike(f'%{job_position}%'))

        if status:
            query = query.filter_by(status=status)

        if min_score is not None:
            query = query.filter(Candidate.overall_score >= min_score)

        if skills:
            # Filter by skills (skills stored as JSON array)
            for skill in skills:
                query = query.filter(Candidate.skills.contains(skill))

        return query.order_by(Candidate.overall_score.desc()).limit(max_results).all()

    def schedule_interview(
        self,
        candidate: Candidate,
        interview_type: str,
        start_time: str,
        duration_minutes: int,
        interviewers: List[str],
        location: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Interview:
        """
        Schedule an interview for a candidate

        Args:
            candidate: Candidate object
            interview_type: Type of interview
            start_time: ISO format start time
            duration_minutes: Duration in minutes
            interviewers: List of interviewer emails
            location: Interview location or video link
            notes: Optional notes

        Returns:
            Interview object
        """
        from dateutil import parser

        scheduled_date = parser.parse(start_time)

        interview = Interview(
            candidate_id=candidate.id,
            tenant_id=candidate.tenant_id,
            interview_type=interview_type,
            scheduled_date=scheduled_date,
            duration_minutes=duration_minutes,
            location=location,
            notes=notes,
            status='scheduled'
        )

        # Set interviewers list
        interview.set_interviewers(interviewers)

        db.session.add(interview)
        db.session.flush()

        return interview

    def calculate_end_time(self, start_time: str, duration_minutes: int) -> str:
        """
        Calculate end time for calendar events

        Args:
            start_time: ISO format start time
            duration_minutes: Duration in minutes

        Returns:
            ISO format end time
        """
        from dateutil import parser

        start = parser.parse(start_time)
        end = start + timedelta(minutes=duration_minutes)
        return end.isoformat()

    # ===== ONBOARDING METHODS =====

    def create_onboarding_plan(
        self,
        employee: Employee,
        start_date: str,
        template: str = 'standard',
        custom_tasks: Optional[List[Dict]] = None,
        buddy_email: Optional[str] = None
    ) -> OnboardingPlan:
        """
        Create an onboarding plan for a new hire

        Args:
            employee: Employee object
            start_date: ISO format start date
            template: Template to use
            custom_tasks: Additional custom tasks
            buddy_email: Optional buddy/mentor email

        Returns:
            OnboardingPlan object
        """
        from dateutil import parser

        start = parser.parse(start_date).date()

        plan = OnboardingPlan(
            employee_id=employee.id,
            tenant_id=employee.tenant_id,
            start_date=start,
            template=template,
            buddy_email=buddy_email
        )

        db.session.add(plan)
        db.session.flush()

        # Add template tasks
        template_tasks = self._get_template_tasks(template)
        for position, task_data in enumerate(template_tasks):
            task = OnboardingTask(
                plan_id=plan.id,
                title=task_data['title'],
                description=task_data['description'],
                due_date=start + timedelta(days=task_data['due_days']),
                assigned_to_email=task_data.get('assigned_to'),
                category=task_data.get('category', 'general'),
                position=position
            )
            db.session.add(task)

        # Add custom tasks
        if custom_tasks:
            for position, task_data in enumerate(custom_tasks, start=len(template_tasks)):
                task = OnboardingTask(
                    plan_id=plan.id,
                    title=task_data['title'],
                    description=task_data.get('description'),
                    due_date=start + timedelta(days=task_data['due_days']),
                    assigned_to_email=task_data.get('assigned_to'),
                    category='custom',
                    position=position
                )
                db.session.add(task)

        return plan

    def _get_template_tasks(self, template: str) -> List[Dict]:
        """
        Get template task definitions

        Args:
            template: Template name

        Returns:
            List of task definitions
        """
        templates = {
            'standard': [
                {
                    'title': 'Complete new hire paperwork',
                    'description': 'Fill out tax forms, direct deposit, emergency contacts',
                    'due_days': 1,
                    'category': 'admin'
                },
                {
                    'title': 'Set up workstation and accounts',
                    'description': 'Computer, email, Slack, necessary software',
                    'due_days': 1,
                    'category': 'it'
                },
                {
                    'title': 'Meet with manager for orientation',
                    'description': 'Review role, expectations, team structure',
                    'due_days': 2,
                    'category': 'orientation'
                },
                {
                    'title': 'Complete company training modules',
                    'description': 'Security awareness, code of conduct, benefits overview',
                    'due_days': 5,
                    'category': 'training'
                },
                {
                    'title': 'Shadow team members',
                    'description': 'Observe workflows and processes',
                    'due_days': 7,
                    'category': 'training'
                },
                {
                    'title': '30-day check-in with HR',
                    'description': 'Discuss onboarding experience and answer questions',
                    'due_days': 30,
                    'category': 'feedback'
                }
            ],
            'engineering': [
                {
                    'title': 'Complete new hire paperwork',
                    'description': 'Fill out tax forms, direct deposit, emergency contacts',
                    'due_days': 1,
                    'category': 'admin'
                },
                {
                    'title': 'Set up development environment',
                    'description': 'Install IDE, clone repos, configure tools',
                    'due_days': 1,
                    'category': 'technical'
                },
                {
                    'title': 'Review codebase and architecture',
                    'description': 'Meet with tech lead for system overview',
                    'due_days': 3,
                    'category': 'technical'
                },
                {
                    'title': 'Complete security and compliance training',
                    'description': 'Security awareness, code review process',
                    'due_days': 5,
                    'category': 'training'
                },
                {
                    'title': 'Complete first code review',
                    'description': 'Submit and review a small pull request',
                    'due_days': 7,
                    'category': 'technical'
                },
                {
                    'title': 'Deploy to production',
                    'description': 'Complete first production deployment with mentor',
                    'due_days': 14,
                    'category': 'technical'
                },
                {
                    'title': '30-day check-in',
                    'description': 'Review progress and feedback',
                    'due_days': 30,
                    'category': 'feedback'
                }
            ],
            'sales': [
                {
                    'title': 'Complete new hire paperwork',
                    'description': 'Fill out tax forms, direct deposit, emergency contacts',
                    'due_days': 1,
                    'category': 'admin'
                },
                {
                    'title': 'Product training',
                    'description': 'Learn product features, value props, and demos',
                    'due_days': 3,
                    'category': 'training'
                },
                {
                    'title': 'CRM and sales tools setup',
                    'description': 'Access to CRM, email tools, sales materials',
                    'due_days': 2,
                    'category': 'it'
                },
                {
                    'title': 'Shadow senior sales rep',
                    'description': 'Observe customer calls and presentations',
                    'due_days': 5,
                    'category': 'training'
                },
                {
                    'title': 'First customer call',
                    'description': 'Lead first customer discovery call with mentor',
                    'due_days': 10,
                    'category': 'milestone'
                },
                {
                    'title': '30-day review',
                    'description': 'Performance review and pipeline review',
                    'due_days': 30,
                    'category': 'feedback'
                }
            ],
            'manager': [
                {
                    'title': 'Complete new hire paperwork',
                    'description': 'Fill out tax forms, direct deposit, emergency contacts',
                    'due_days': 1,
                    'category': 'admin'
                },
                {
                    'title': 'Meet with leadership team',
                    'description': 'Introduction to company leadership and strategy',
                    'due_days': 2,
                    'category': 'orientation'
                },
                {
                    'title': 'Review team structure and responsibilities',
                    'description': 'Understand team roles, projects, and goals',
                    'due_days': 3,
                    'category': 'orientation'
                },
                {
                    'title': 'One-on-ones with direct reports',
                    'description': 'Meet individually with each team member',
                    'due_days': 7,
                    'category': 'orientation'
                },
                {
                    'title': 'Management training',
                    'description': 'Company policies, performance management, conflict resolution',
                    'due_days': 14,
                    'category': 'training'
                },
                {
                    'title': '30-day strategy review',
                    'description': 'Present 30-60-90 day plan to leadership',
                    'due_days': 30,
                    'category': 'milestone'
                }
            ]
        }

        return templates.get(template, templates['standard'])

    # ===== EMPLOYEE RECORDS METHODS =====

    def search_employees(
        self,
        tenant_id: int,
        department: Optional[str] = None,
        status: Optional[str] = None,
        role: Optional[str] = None,
        search_query: Optional[str] = None,
        max_results: int = 50
    ) -> List[Employee]:
        """
        Search employees with filters

        Args:
            tenant_id: Tenant ID
            department: Filter by department
            status: Filter by status
            role: Filter by role
            search_query: Search by name or email
            max_results: Maximum results to return

        Returns:
            List of Employee objects
        """
        query = Employee.query.filter_by(tenant_id=tenant_id)

        if department:
            query = query.filter_by(department_name=department)

        if status:
            query = query.filter_by(status=status)

        if role:
            query = query.filter(Employee.role.ilike(f'%{role}%'))

        if search_query:
            search = f'%{search_query}%'
            query = query.filter(
                db.or_(
                    Employee.first_name.ilike(search),
                    Employee.last_name.ilike(search),
                    Employee.email.ilike(search)
                )
            )

        return query.order_by(Employee.last_name).limit(max_results).all()

    # ===== TIME OFF METHODS =====

    def get_team_pto_calendar(
        self,
        tenant_id: int,
        department: Optional[str] = None,
        days_ahead: int = 30,
        include_pending: bool = True
    ) -> List[Dict]:
        """
        Get upcoming PTO for team/department

        Args:
            tenant_id: Tenant ID
            department: Filter by department
            days_ahead: Days ahead to look
            include_pending: Include pending requests

        Returns:
            List of PTO calendar entries
        """
        end_date = date.today() + timedelta(days=days_ahead)

        query = PTORequest.query.filter(
            PTORequest.tenant_id == tenant_id,
            PTORequest.start_date <= end_date,
            PTORequest.end_date >= date.today()
        )

        if not include_pending:
            query = query.filter_by(status='approved')

        if department:
            query = query.join(Employee).filter(Employee.department_name == department)

        requests = query.order_by(PTORequest.start_date).all()

        return [
            {
                'employee_name': req.employee.full_name,
                'department': req.employee.department_name,
                'start_date': req.start_date.isoformat(),
                'end_date': req.end_date.isoformat(),
                'days': req.total_days,
                'status': req.status,
                'is_pending': req.status == 'pending'
            }
            for req in requests
        ]

    @staticmethod
    def calculate_business_days(start_date: date, end_date: date) -> float:
        """
        Calculate business days between two dates (excluding weekends)

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Number of business days
        """
        if start_date > end_date:
            return 0.0

        # Count business days
        business_days = 0
        current = start_date

        while current <= end_date:
            # Monday = 0, Sunday = 6
            if current.weekday() < 5:  # Monday-Friday
                business_days += 1
            current += timedelta(days=1)

        return float(business_days)


# Singleton instance
hr_service = HRService()
