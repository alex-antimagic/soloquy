"""
Unified Search Service
Provides search functionality across all data types within a tenant
with user-specific access control
"""

from app import db
from app.models.task import Task
from app.models.contact import Contact
from app.models.company import Company
from app.models.deal import Deal
from app.models.ticket import Ticket
from app.models.message import Message
from app.models.department import Department
from app.models.channel import Channel
from flask import url_for


class UnifiedSearchService:
    """
    Service for searching across multiple data types with user-specific access control
    """

    @staticmethod
    def search_all(user_id, tenant_id, query, limit=5):
        """
        Search across all data types and return categorized results

        Args:
            user_id: Current user ID for access control
            tenant_id: Current tenant ID for data scoping
            query: Search query string
            limit: Max results per category

        Returns:
            dict: Categorized search results
        """
        results = {
            'tasks': UnifiedSearchService.search_tasks(user_id, tenant_id, query, limit),
            'contacts': UnifiedSearchService.search_contacts(tenant_id, query, limit),
            'companies': UnifiedSearchService.search_companies(tenant_id, query, limit),
            'deals': UnifiedSearchService.search_deals(user_id, tenant_id, query, limit),
            'tickets': UnifiedSearchService.search_tickets(user_id, tenant_id, query, limit),
            'messages': UnifiedSearchService.search_messages(user_id, tenant_id, query, limit),
        }

        # Calculate total count
        total = sum(len(results[key]) for key in results)
        results['total_count'] = total

        return results

    @staticmethod
    def search_tasks(user_id, tenant_id, query, limit=5):
        """
        Search tasks (user-specific: assigned to or created by user)
        """
        try:
            tasks = Task.query.filter(
                Task.tenant_id == tenant_id,
                db.or_(
                    Task.assigned_to_id == user_id,
                    Task.created_by_id == user_id
                ),
                db.or_(
                    Task.title.ilike(f'%{query}%'),
                    Task.description.ilike(f'%{query}%'),
                    Task.tags.ilike(f'%{query}%')
                )
            ).order_by(Task.updated_at.desc()).limit(limit).all()

            return [{
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'priority': task.priority,
                'due_date': task.due_date.strftime('%b %d') if task.due_date else None,
                'url': url_for('tasks.index', highlight=task.id)
            } for task in tasks]
        except Exception as e:
            print(f"Error searching tasks: {e}")
            return []

    @staticmethod
    def search_contacts(tenant_id, query, limit=5):
        """
        Search contacts (tenant-wide, team shared data)
        """
        try:
            contacts = Contact.query.filter(
                Contact.tenant_id == tenant_id,
                db.or_(
                    Contact.first_name.ilike(f'%{query}%'),
                    Contact.last_name.ilike(f'%{query}%'),
                    Contact.email.ilike(f'%{query}%'),
                    Contact.job_title.ilike(f'%{query}%')
                )
            ).order_by(Contact.updated_at.desc()).limit(limit).all()

            return [{
                'id': contact.id,
                'name': contact.full_name,
                'email': contact.email,
                'job_title': contact.job_title,
                'company': contact.company.name if contact.company else None,
                'url': url_for('crm.contact_detail', contact_id=contact.id)
            } for contact in contacts]
        except Exception as e:
            print(f"Error searching contacts: {e}")
            return []

    @staticmethod
    def search_companies(tenant_id, query, limit=5):
        """
        Search companies (tenant-wide, team shared data)
        """
        try:
            companies = Company.query.filter(
                Company.tenant_id == tenant_id,
                db.or_(
                    Company.name.ilike(f'%{query}%'),
                    Company.industry.ilike(f'%{query}%'),
                    Company.description.ilike(f'%{query}%')
                )
            ).order_by(Company.updated_at.desc()).limit(limit).all()

            return [{
                'id': company.id,
                'name': company.name,
                'industry': company.industry,
                'website': company.website,
                'url': url_for('crm.company_detail', company_id=company.id)
            } for company in companies]
        except Exception as e:
            print(f"Error searching companies: {e}")
            return []

    @staticmethod
    def search_deals(user_id, tenant_id, query, limit=5):
        """
        Search deals (user-specific: owned by user)
        """
        try:
            deals = Deal.query.filter(
                Deal.tenant_id == tenant_id,
                Deal.owner_id == user_id,
                db.or_(
                    Deal.name.ilike(f'%{query}%'),
                    Deal.description.ilike(f'%{query}%'),
                    Deal.tags.ilike(f'%{query}%')
                )
            ).order_by(Deal.updated_at.desc()).limit(limit).all()

            return [{
                'id': deal.id,
                'name': deal.name,
                'amount': float(deal.amount) if deal.amount else 0,
                'status': deal.status,
                'company': deal.company.name if deal.company else None,
                'url': url_for('crm.deal_detail', deal_id=deal.id)
            } for deal in deals]
        except Exception as e:
            print(f"Error searching deals: {e}")
            return []

    @staticmethod
    def search_tickets(user_id, tenant_id, query, limit=5):
        """
        Search support tickets (user-specific: created by or assigned to user)
        """
        try:
            # Get tickets where user is assignee or requester
            from app.models.user import User
            user = User.query.get(user_id)
            if not user:
                return []

            # Search tickets assigned to user or where user's email is requester
            tickets = Ticket.query.filter(
                Ticket.tenant_id == tenant_id,
                db.or_(
                    Ticket.assignee_id == user_id,
                    Ticket.requester_email == user.email
                ),
                db.or_(
                    Ticket.ticket_number.ilike(f'%{query}%'),
                    Ticket.subject.ilike(f'%{query}%'),
                    Ticket.description.ilike(f'%{query}%')
                )
            ).order_by(Ticket.updated_at.desc()).limit(limit).all()

            return [{
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'subject': ticket.subject,
                'status': ticket.status,
                'priority': ticket.priority,
                'url': url_for('support.ticket_detail', ticket_id=ticket.id)
            } for ticket in tickets]
        except Exception as e:
            print(f"Error searching tickets: {e}")
            return []

    @staticmethod
    def search_messages(user_id, tenant_id, query, limit=5):
        """
        Search messages with permission checks
        Only return messages from:
        - Department channels in user's tenant (tenant-wide access)
        - Direct messages involving the user
        """
        try:
            from app.models.user import User
            from app.models.department import Department

            user = User.query.get(user_id)
            if not user:
                return []

            # Get all department IDs in this tenant
            tenant_dept_ids = [d.id for d in Department.query.filter_by(
                tenant_id=tenant_id,
                is_active=True
            ).all()]

            # Search messages in tenant departments and user's DMs
            messages = Message.query.filter(
                Message.content.ilike(f'%{query}%'),
                db.or_(
                    # Department channels in tenant
                    Message.department_id.in_(tenant_dept_ids),
                    # Direct messages to/from user
                    db.and_(
                        Message.recipient_id == user_id,
                        Message.department_id.is_(None)
                    ),
                    db.and_(
                        Message.sender_id == user_id,
                        Message.department_id.is_(None)
                    )
                )
            ).order_by(Message.created_at.desc()).limit(limit).all()

            results = []
            for msg in messages:
                # Build preview and context
                preview = msg.content[:100] + '...' if len(msg.content) > 100 else msg.content

                # Determine context (channel, DM, etc.)
                if msg.department_id:
                    dept = Department.query.get(msg.department_id)
                    context = f"#{dept.name}" if dept else "Department"
                    url = url_for('chat.department_chat', department_id=msg.department_id)
                elif msg.channel_id:
                    channel = Channel.query.get(msg.channel_id)
                    context = f"#{channel.name}" if channel else "Channel"
                    url = url_for('chat.channel_chat', channel_id=msg.channel_id)
                elif msg.recipient_id:
                    # Direct message
                    other_user = msg.sender if msg.sender_id != user_id else msg.recipient
                    context = f"DM with {other_user.full_name if other_user else 'Unknown'}"
                    url = url_for('chat.user_chat', user_id=msg.recipient_id if msg.sender_id == user_id else msg.sender_id)
                else:
                    context = "Message"
                    url = "#"

                results.append({
                    'id': msg.id,
                    'preview': preview,
                    'sender': msg.get_sender_name(),
                    'context': context,
                    'created_at': msg.created_at.strftime('%b %d, %I:%M %p'),
                    'url': url
                })

            return results
        except Exception as e:
            print(f"Error searching messages: {e}")
            return []
