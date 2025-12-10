"""
Create sample HR data for testing the HR/People applet
Run this script to populate the database with sample candidates, employees, and PTO requests
"""

from app import create_app, db
from app.models.tenant import Tenant
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.employee import Employee
from app.models.onboarding_plan import OnboardingPlan, OnboardingTask
from app.models.pto_request import PTORequest
from app.models.job_posting import JobPosting
from datetime import datetime, date, timedelta
import json

def create_sample_hr_data():
    """Create sample HR data for the first tenant in the database"""

    # Get the first tenant
    tenant = Tenant.query.first()
    if not tenant:
        print("❌ No tenant found! Create a workspace first.")
        return

    print(f"📊 Creating sample HR data for tenant: {tenant.name}")

    # Check if HR data already exists
    existing_jobs = JobPosting.query.filter_by(tenant_id=tenant.id).count()
    existing_candidates = Candidate.query.filter_by(tenant_id=tenant.id).count()
    existing_employees = Employee.query.filter_by(tenant_id=tenant.id).count()

    if existing_jobs > 0 or existing_candidates > 0 or existing_employees > 0:
        print(f"\n⚠️  WARNING: HR data already exists for this tenant!")
        print(f"   - Job Postings: {existing_jobs}")
        print(f"   - Candidates: {existing_candidates}")
        print(f"   - Employees: {existing_employees}")
        print(f"\nThis script will create additional sample data.")
        print(f"To start fresh, delete existing data first.\n")

    # 1. Create Job Postings
    print("\n📋 Creating job postings...")

    job1 = JobPosting(
        tenant_id=tenant.id,
        title="Senior Software Engineer",
        department="Engineering",
        location="San Francisco, CA (Remote)",
        employment_type="full-time",
        description="We're looking for an experienced software engineer to join our growing team.",
        requirements="5+ years of experience with Python, React, and PostgreSQL. Strong problem-solving skills.",
        salary_range_min=120000,
        salary_range_max=180000,
        salary_currency="USD",
        status="published",
        published_at=datetime.utcnow() - timedelta(days=15),
        application_count=8
    )

    job2 = JobPosting(
        tenant_id=tenant.id,
        title="Product Designer",
        department="Design",
        location="Remote",
        employment_type="full-time",
        description="Join our design team to create beautiful, user-friendly experiences.",
        requirements="3+ years of experience with Figma, user research, and prototyping.",
        salary_range_min=90000,
        salary_range_max=130000,
        salary_currency="USD",
        status="published",
        published_at=datetime.utcnow() - timedelta(days=10),
        application_count=5
    )

    job3 = JobPosting(
        tenant_id=tenant.id,
        title="Marketing Manager",
        department="Marketing",
        location="New York, NY",
        employment_type="full-time",
        description="Lead our marketing initiatives and grow our brand.",
        requirements="5+ years of B2B marketing experience. Strong analytical skills.",
        salary_range_min=100000,
        salary_range_max=140000,
        salary_currency="USD",
        status="draft"
    )

    db.session.add_all([job1, job2, job3])
    db.session.flush()
    print(f"  ✅ Created {3} job postings")

    # 2. Create Candidates
    print("\n👥 Creating candidates...")

    candidates_data = [
        {
            "tenant_id": tenant.id,
            "first_name": "Sarah",
            "last_name": "Johnson",
            "email": "sarah.johnson@example.com",
            "phone": "(555) 123-4567",
            "position": "Senior Software Engineer",
            "status": "interviewing",
            "job_posting_id": job1.id,
            "applied_date": date.today() - timedelta(days=12),
            "overall_score": 85,
            "category_scores": json.dumps({"technical": 90, "communication": 85, "cultural_fit": 80}),
            "skills": json.dumps(["Python", "React", "PostgreSQL", "Docker", "AWS"]),
            "experience_years": 7,
            "resume_url": "https://example.com/resumes/sarah-johnson.pdf",
            "linkedin_url": "https://linkedin.com/in/sarahjohnson",
            "notes": json.dumps([{
                "note": "Strong technical background, excellent communication skills",
                "created_by": "Hannah (HR)",
                "created_at": datetime.utcnow().isoformat()
            }])
        },
        {
            "tenant_id": tenant.id,
            "first_name": "Michael",
            "last_name": "Chen",
            "email": "michael.chen@example.com",
            "phone": "(555) 234-5678",
            "position": "Senior Software Engineer",
            "status": "screening",
            "job_posting_id": job1.id,
            "applied_date": date.today() - timedelta(days=8),
            "overall_score": 78,
            "category_scores": json.dumps({"technical": 80, "communication": 75, "cultural_fit": 78}),
            "skills": json.dumps(["Python", "Django", "Redis", "Kubernetes"]),
            "experience_years": 6,
            "resume_url": "https://example.com/resumes/michael-chen.pdf"
        },
        {
            "tenant_id": tenant.id,
            "first_name": "Emily",
            "last_name": "Rodriguez",
            "email": "emily.rodriguez@example.com",
            "phone": "(555) 345-6789",
            "position": "Product Designer",
            "status": "offer_extended",
            "job_posting_id": job2.id,
            "applied_date": date.today() - timedelta(days=20),
            "overall_score": 92,
            "category_scores": json.dumps({"design_skills": 95, "ux_research": 90, "collaboration": 90}),
            "skills": json.dumps(["Figma", "Sketch", "User Research", "Prototyping", "Design Systems"]),
            "experience_years": 5,
            "resume_url": "https://example.com/resumes/emily-rodriguez.pdf",
            "linkedin_url": "https://linkedin.com/in/emilyrodriguez"
        },
        {
            "tenant_id": tenant.id,
            "first_name": "David",
            "last_name": "Kim",
            "email": "david.kim@example.com",
            "position": "Senior Software Engineer",
            "status": "applied",
            "job_posting_id": job1.id,
            "applied_date": date.today() - timedelta(days=3),
            "skills": json.dumps(["Java", "Spring", "MySQL"]),
            "experience_years": 5
        },
        {
            "tenant_id": tenant.id,
            "first_name": "Lisa",
            "last_name": "Anderson",
            "email": "lisa.anderson@example.com",
            "position": "Product Designer",
            "status": "rejected",
            "job_posting_id": job2.id,
            "applied_date": date.today() - timedelta(days=25),
            "overall_score": 62,
            "skills": json.dumps(["Photoshop", "Illustrator"]),
            "experience_years": 2
        }
    ]

    candidates = []
    for data in candidates_data:
        candidate = Candidate(**data)
        db.session.add(candidate)
        candidates.append(candidate)

    db.session.flush()
    print(f"  ✅ Created {len(candidates)} candidates")

    # 3. Create Interviews
    print("\n📅 Creating interviews...")

    # Interview for Sarah (interviewing stage)
    interview1 = Interview(
        candidate_id=candidates[0].id,
        tenant_id=tenant.id,
        interview_type="technical",
        scheduled_date=datetime.utcnow() + timedelta(days=2, hours=10),
        duration_minutes=60,
        location="Zoom: https://zoom.us/j/123456789",
        interviewers=json.dumps(["tech-lead@company.com", "senior-engineer@company.com"]),
        status="scheduled"
    )

    # Past interview for Emily (offer extended)
    interview2 = Interview(
        candidate_id=candidates[2].id,
        tenant_id=tenant.id,
        interview_type="panel",
        scheduled_date=datetime.utcnow() - timedelta(days=5),
        duration_minutes=90,
        location="Conference Room A",
        interviewers=json.dumps(["design-lead@company.com", "product-manager@company.com", "ceo@company.com"]),
        status="completed",
        score=92,
        feedback="Excellent portfolio, strong UX thinking, great culture fit"
    )

    db.session.add_all([interview1, interview2])
    print(f"  ✅ Created {2} interviews")

    # 4. Create Employees
    print("\n👨‍💼 Creating employees...")

    # Generate unique employee numbers
    existing_employee_count = Employee.query.filter_by(tenant_id=tenant.id).count()
    emp_num_start = existing_employee_count + 1

    employees_data = [
        {
            "tenant_id": tenant.id,
            "employee_number": f"EMP-{emp_num_start:03d}",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@company.com",
            "phone": "(555) 111-2222",
            "department_name": "Engineering",
            "role": "Senior Software Engineer",
            "manager_name": "Jane Doe",
            "hire_date": date.today() - timedelta(days=730),  # 2 years ago
            "status": "active",
            "salary": 150000,
            "salary_currency": "USD",
            "bonus_target_percentage": 15,
            "pto_balance": 15.0,
            "pto_used_this_year": 5.0,
            "sick_days_balance": 5.0
        },
        {
            "tenant_id": tenant.id,
            "employee_number": f"EMP-{emp_num_start + 1:03d}",
            "first_name": "Maria",
            "last_name": "Garcia",
            "email": "maria.garcia@company.com",
            "phone": "(555) 222-3333",
            "department_name": "Design",
            "role": "Product Designer",
            "manager_name": "Alex Thompson",
            "hire_date": date.today() - timedelta(days=365),  # 1 year ago
            "status": "active",
            "salary": 110000,
            "salary_currency": "USD",
            "bonus_target_percentage": 10,
            "pto_balance": 12.0,
            "pto_used_this_year": 8.0,
            "sick_days_balance": 3.0
        },
        {
            "tenant_id": tenant.id,
            "employee_number": f"EMP-{emp_num_start + 2:03d}",
            "first_name": "Robert",
            "last_name": "Taylor",
            "email": "robert.taylor@company.com",
            "department_name": "Marketing",
            "role": "Marketing Manager",
            "manager_name": "Sarah Wilson",
            "hire_date": date.today() - timedelta(days=45),  # Recent hire
            "status": "active",
            "salary": 120000,
            "salary_currency": "USD",
            "bonus_target_percentage": 12,
            "pto_balance": 20.0,
            "pto_used_this_year": 0.0,
            "sick_days_balance": 5.0
        }
    ]

    employees = []
    for data in employees_data:
        employee = Employee(**data)
        db.session.add(employee)
        employees.append(employee)

    db.session.flush()
    print(f"  ✅ Created {len(employees)} employees")

    # 5. Create Onboarding Plan for recent hire
    print("\n📝 Creating onboarding plan...")

    from app.services.hr_service import hr_service

    onboarding_plan = hr_service.create_onboarding_plan(
        employee=employees[2],  # Robert (recent hire)
        start_date=employees[2].hire_date.isoformat(),
        template="standard",
        buddy_email="maria.garcia@company.com"
    )

    # Mark some tasks as completed
    tasks = OnboardingTask.query.filter_by(plan_id=onboarding_plan.id).limit(3).all()
    for task in tasks:
        task.is_completed = True
        task.completed_at = datetime.utcnow()
        task.completed_by_email = "robert.taylor@company.com"

    # Update completion percentage
    onboarding_plan.calculate_completion()

    print(f"  ✅ Created onboarding plan with {onboarding_plan.tasks.count()} tasks")

    # 6. Create PTO Requests
    print("\n🏖️ Creating PTO requests...")

    # Pending request
    pto1 = PTORequest(
        employee_id=employees[0].id,
        tenant_id=tenant.id,
        start_date=date.today() + timedelta(days=30),
        end_date=date.today() + timedelta(days=34),
        total_days=5.0,
        request_type="pto",
        status="pending",
        request_reason="Family vacation"
    )

    # Approved future request
    pto2 = PTORequest(
        employee_id=employees[1].id,
        tenant_id=tenant.id,
        start_date=date.today() + timedelta(days=15),
        end_date=date.today() + timedelta(days=16),
        total_days=2.0,
        request_type="pto",
        status="approved",
        approved_by="Hannah (HR)",
        approved_at=datetime.utcnow() - timedelta(days=2)
    )

    # Past approved request
    pto3 = PTORequest(
        employee_id=employees[1].id,
        tenant_id=tenant.id,
        start_date=date.today() - timedelta(days=20),
        end_date=date.today() - timedelta(days=18),
        total_days=3.0,
        request_type="sick",
        status="approved",
        approved_by="Hannah (HR)",
        approved_at=datetime.utcnow() - timedelta(days=21)
    )

    db.session.add_all([pto1, pto2, pto3])
    print(f"  ✅ Created {3} PTO requests")

    # Commit all changes
    db.session.commit()

    print("\n" + "="*60)
    print("✅ Sample HR data created successfully!")
    print("="*60)
    print(f"\n📊 Summary:")
    print(f"  • Job Postings: 3 (2 published, 1 draft)")
    print(f"  • Candidates: 5 (across different stages)")
    print(f"  • Interviews: 2 (1 upcoming, 1 completed)")
    print(f"  • Employees: 3")
    print(f"  • Onboarding Plans: 1 (with {onboarding_plan.tasks.count()} tasks)")
    print(f"  • PTO Requests: 3 (1 pending, 2 approved)")
    print(f"\n🎯 You can now:")
    print(f"  • View the recruitment pipeline at /hr/recruitment")
    print(f"  • Check employee directory at /hr/employees")
    print(f"  • Review onboarding progress at /hr/onboarding")
    print(f"  • Manage PTO requests at /hr/time-off")
    print()

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        create_sample_hr_data()
