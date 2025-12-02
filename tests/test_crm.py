"""
Tests for CRM workflows and data isolation
"""
import pytest
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.deal_pipeline import DealPipeline
from app.models.deal_stage import DealStage
from app.models.tenant import TenantMembership
from decimal import Decimal


class TestCRMTenantIsolation:
    """Test suite for CRM tenant isolation"""

    def test_cannot_access_other_tenant_company(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot access companies from other tenants"""
        # Create company in tenant_2
        company_2 = Company(
            name='Other Company',
            tenant_id=test_tenant_2.id,
            website='https://other.com'
        )
        db_session.add(company_2)
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to access company from tenant_2
        response = client.get(f'/crm/companies/{company_2.id}')

        # Should be denied
        assert response.status_code in [403, 404]

    def test_cannot_access_other_tenant_contact(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot access contacts from other tenants"""
        # Create contact in tenant_2
        contact_2 = Contact(
            first_name='John',
            last_name='Doe',
            email='john@other.com',
            tenant_id=test_tenant_2.id
        )
        db_session.add(contact_2)
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to access contact from tenant_2
        response = client.get(f'/crm/contacts/{contact_2.id}')

        # Should be denied
        assert response.status_code in [403, 404]

    def test_cannot_move_deal_to_other_tenant_pipeline(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot move deals to pipelines from other tenants"""
        # Create pipeline in tenant 1
        pipeline_1 = DealPipeline(
            name='Sales Pipeline',
            tenant_id=test_tenant.id
        )
        db_session.add(pipeline_1)
        db_session.flush()

        stage_1 = DealStage(
            name='Prospecting',
            pipeline_id=pipeline_1.id,
            position=0
        )
        db_session.add(stage_1)
        db_session.flush()

        # Create deal in tenant 1
        company = Company(
            name='Test Company',
            tenant_id=test_tenant.id
        )
        db_session.add(company)
        db_session.flush()

        deal = Deal(
            name='Test Deal',
            tenant_id=test_tenant.id,
            company_id=company.id,
            pipeline_id=pipeline_1.id,
            stage_id=stage_1.id,
            amount=Decimal('10000.00')
        )
        db_session.add(deal)
        db_session.commit()

        # Create pipeline in tenant 2
        pipeline_2 = DealPipeline(
            name='Other Pipeline',
            tenant_id=test_tenant_2.id
        )
        db_session.add(pipeline_2)
        db_session.flush()

        stage_2 = DealStage(
            name='Qualified',
            pipeline_id=pipeline_2.id,
            position=0
        )
        db_session.add(stage_2)
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to move deal to tenant_2's pipeline/stage
        response = client.post(
            f'/crm/deals/{deal.id}/move',
            json={'stage_id': stage_2.id}
        )

        # Should be rejected
        assert response.status_code in [403, 404]

        # Verify deal wasn't moved
        deal_check = Deal.query.get(deal.id)
        assert deal_check.stage_id == stage_1.id
        assert deal_check.pipeline_id == pipeline_1.id


class TestCRMWorkflows:
    """Test suite for CRM workflow operations"""

    def test_create_company(self, client, test_user, test_tenant, db_session):
        """Test creating a new company"""
        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Create company
        response = client.post('/crm/companies/create', json={
            'name': 'Acme Corp',
            'website': 'https://acme.com',
            'industry': 'Technology'
        }, follow_redirects=False)

        # Should be successful
        assert response.status_code in [200, 201, 302]

        # Verify company was created in correct tenant
        company = Company.query.filter_by(name='Acme Corp', tenant_id=test_tenant.id).first()
        assert company is not None
        assert company.tenant_id == test_tenant.id
        assert company.website == 'https://acme.com'

    def test_create_contact(self, client, test_user, test_tenant, db_session):
        """Test creating a new contact"""
        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Create contact
        response = client.post('/crm/contacts/create', json={
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@example.com',
            'job_title': 'CEO'
        }, follow_redirects=False)

        # Should be successful
        assert response.status_code in [200, 201, 302]

        # Verify contact was created in correct tenant
        contact = Contact.query.filter_by(email='jane@example.com', tenant_id=test_tenant.id).first()
        assert contact is not None
        assert contact.tenant_id == test_tenant.id
        assert contact.first_name == 'Jane'

    def test_link_contact_to_company(self, client, test_user, test_tenant, db_session):
        """Test linking a contact to a company"""
        # Create company
        company = Company(
            name='Test Company',
            tenant_id=test_tenant.id
        )
        db_session.add(company)
        db_session.flush()

        # Create contact
        contact = Contact(
            first_name='John',
            last_name='Doe',
            email='john@test.com',
            tenant_id=test_tenant.id
        )
        db_session.add(contact)
        db_session.commit()

        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Link contact to company
        response = client.post(f'/crm/contacts/{contact.id}/update', json={
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@test.com',
            'company_id': company.id
        })

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify link
        contact_check = Contact.query.get(contact.id)
        assert contact_check.company_id == company.id

    def test_create_deal_with_pipeline(self, client, test_user, test_tenant, db_session):
        """Test creating a deal in a pipeline"""
        # Create pipeline and stage
        pipeline = DealPipeline(
            name='Sales Pipeline',
            tenant_id=test_tenant.id
        )
        db_session.add(pipeline)
        db_session.flush()

        stage = DealStage(
            name='Prospecting',
            pipeline_id=pipeline.id,
            position=0
        )
        db_session.add(stage)
        db_session.flush()

        # Create company
        company = Company(
            name='Test Company',
            tenant_id=test_tenant.id
        )
        db_session.add(company)
        db_session.commit()

        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Create deal
        response = client.post('/crm/deals/create', json={
            'name': 'Big Deal',
            'company_id': company.id,
            'pipeline_id': pipeline.id,
            'stage_id': stage.id,
            'amount': '25000.00'
        }, follow_redirects=False)

        # Should be successful
        assert response.status_code in [200, 201, 302]

        # Verify deal was created
        deal = Deal.query.filter_by(name='Big Deal', tenant_id=test_tenant.id).first()
        assert deal is not None
        assert deal.tenant_id == test_tenant.id
        assert deal.pipeline_id == pipeline.id
        assert deal.stage_id == stage.id
        assert deal.amount == Decimal('25000.00')

    def test_move_deal_between_stages(self, client, test_user, test_tenant, db_session):
        """Test moving a deal between stages in the same pipeline"""
        # Create pipeline with stages
        pipeline = DealPipeline(
            name='Sales Pipeline',
            tenant_id=test_tenant.id
        )
        db_session.add(pipeline)
        db_session.flush()

        stage_1 = DealStage(
            name='Prospecting',
            pipeline_id=pipeline.id,
            position=0
        )
        stage_2 = DealStage(
            name='Qualified',
            pipeline_id=pipeline.id,
            position=1
        )
        db_session.add_all([stage_1, stage_2])
        db_session.flush()

        # Create deal in stage 1
        company = Company(
            name='Test Company',
            tenant_id=test_tenant.id
        )
        db_session.add(company)
        db_session.flush()

        deal = Deal(
            name='Test Deal',
            tenant_id=test_tenant.id,
            company_id=company.id,
            pipeline_id=pipeline.id,
            stage_id=stage_1.id
        )
        db_session.add(deal)
        db_session.commit()

        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Move deal to stage 2
        response = client.post(
            f'/crm/deals/{deal.id}/move',
            json={'stage_id': stage_2.id}
        )

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify deal was moved
        deal_check = Deal.query.get(deal.id)
        assert deal_check.stage_id == stage_2.id

    def test_list_companies_filtered_by_tenant(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that company listings are filtered by tenant"""
        # Create companies in both tenants
        company_1 = Company(
            name='My Company',
            tenant_id=test_tenant.id
        )
        company_2 = Company(
            name='Other Company',
            tenant_id=test_tenant_2.id
        )
        db_session.add_all([company_1, company_2])
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Get company list
        response = client.get('/crm/companies')

        # Should show only test_tenant companies
        assert response.status_code == 200
        assert b'My Company' in response.data
        assert b'Other Company' not in response.data
