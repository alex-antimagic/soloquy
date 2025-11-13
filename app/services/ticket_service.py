"""
Ticket Service for managing support tickets
"""
from app import db
from app.models.ticket import Ticket
from app.models.ticket_comment import TicketComment
from app.models.ticket_status_history import TicketStatusHistory
from datetime import datetime, timedelta


def generate_ticket_number(tenant_id):
    """
    Generate the next ticket number for a tenant
    Format: TKT-00001
    """
    # Get the last ticket for this tenant
    last_ticket = Ticket.query.filter_by(
        tenant_id=tenant_id
    ).order_by(Ticket.id.desc()).first()

    if last_ticket and last_ticket.ticket_number:
        # Extract the number part and increment
        try:
            last_num = int(last_ticket.ticket_number.split('-')[1])
            new_num = last_num + 1
        except (IndexError, ValueError):
            new_num = 1
    else:
        new_num = 1

    return f"TKT-{new_num:05d}"


def create_ticket(tenant_id, subject, description, **kwargs):
    """
    Create a new support ticket

    Args:
        tenant_id: The tenant creating the ticket
        subject: Ticket subject/title
        description: Ticket description
        **kwargs: Additional ticket fields (requester_id, company_id, priority, etc.)

    Returns:
        Ticket: The created ticket
    """
    # Generate ticket number
    ticket_number = generate_ticket_number(tenant_id)

    # Create ticket
    ticket = Ticket(
        tenant_id=tenant_id,
        ticket_number=ticket_number,
        subject=subject,
        description=description,
        status=kwargs.get('status', 'new'),
        priority=kwargs.get('priority', 'medium'),
        category=kwargs.get('category'),
        source=kwargs.get('source', 'web'),
        requester_id=kwargs.get('requester_id'),
        requester_email=kwargs.get('requester_email'),
        requester_name=kwargs.get('requester_name'),
        company_id=kwargs.get('company_id'),
        assignee_id=kwargs.get('assignee_id'),
        department_id=kwargs.get('department_id'),
        tags=kwargs.get('tags'),
        email_message_id=kwargs.get('email_message_id')
    )

    # Set SLA due dates if applicable
    if kwargs.get('first_response_due_at'):
        ticket.first_response_due_at = kwargs.get('first_response_due_at')
    elif ticket.priority:
        # Calculate based on priority (simple defaults)
        ticket.first_response_due_at = calculate_first_response_due(ticket.priority)

    if kwargs.get('resolution_due_at'):
        ticket.resolution_due_at = kwargs.get('resolution_due_at')
    elif ticket.priority:
        ticket.resolution_due_at = calculate_resolution_due(ticket.priority)

    db.session.add(ticket)

    # Create initial status history entry
    history = TicketStatusHistory(
        ticket=ticket,
        from_status=None,
        to_status=ticket.status,
        changed_by_id=kwargs.get('created_by_id')
    )
    db.session.add(history)

    db.session.commit()

    return ticket


def assign_ticket(ticket_id, assignee_id, changed_by_id=None):
    """
    Assign a ticket to an agent

    Args:
        ticket_id: ID of the ticket
        assignee_id: ID of the user to assign to
        changed_by_id: ID of user making the change

    Returns:
        Ticket: The updated ticket
    """
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        raise ValueError("Ticket not found")

    ticket.assignee_id = assignee_id
    ticket.updated_at = datetime.utcnow()
    ticket.last_activity_at = datetime.utcnow()

    # Automatically change status from 'new' to 'open' when assigned
    if ticket.status == 'new':
        change_status(ticket_id, 'open', changed_by_id=changed_by_id, reason="Assigned to agent")

    db.session.commit()
    return ticket


def change_status(ticket_id, new_status, changed_by_id=None, reason=None):
    """
    Change ticket status and track in history

    Args:
        ticket_id: ID of the ticket
        new_status: New status value
        changed_by_id: ID of user making the change
        reason: Optional reason for the change

    Returns:
        Ticket: The updated ticket
    """
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        raise ValueError("Ticket not found")

    old_status = ticket.status

    # Don't record if status hasn't changed
    if old_status == new_status:
        return ticket

    # Update ticket status
    ticket.status = new_status
    ticket.updated_at = datetime.utcnow()
    ticket.last_activity_at = datetime.utcnow()

    # Set resolved/closed timestamps
    if new_status == 'resolved' and not ticket.resolved_at:
        ticket.resolved_at = datetime.utcnow()
    elif new_status == 'closed' and not ticket.closed_at:
        ticket.closed_at = datetime.utcnow()
        if not ticket.resolved_at:
            ticket.resolved_at = datetime.utcnow()

    # Create status history entry
    history = TicketStatusHistory(
        ticket_id=ticket_id,
        from_status=old_status,
        to_status=new_status,
        changed_by_id=changed_by_id,
        reason=reason
    )
    db.session.add(history)

    db.session.commit()
    return ticket


def add_comment(ticket_id, body, author_id=None, author_type='agent', is_public=True, is_resolution=False, **kwargs):
    """
    Add a comment to a ticket

    Args:
        ticket_id: ID of the ticket
        body: Comment text
        author_id: ID of the user (if agent)
        author_type: 'agent', 'customer', or 'system'
        is_public: Whether the comment is public (False = internal note)
        is_resolution: Whether this comment resolves the ticket
        **kwargs: Additional fields (email_message_id, etc.)

    Returns:
        TicketComment: The created comment
    """
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        raise ValueError("Ticket not found")

    comment = TicketComment(
        ticket_id=ticket_id,
        author_id=author_id,
        author_type=author_type,
        body=body,
        is_public=is_public,
        is_resolution=is_resolution,
        email_message_id=kwargs.get('email_message_id')
    )

    db.session.add(comment)

    # Update ticket's last activity timestamp
    ticket.updated_at = datetime.utcnow()
    ticket.last_activity_at = datetime.utcnow()

    # Track first response time
    if author_type == 'agent' and not ticket.first_response_at:
        ticket.first_response_at = datetime.utcnow()

    # Auto-resolve ticket if this is a resolution comment
    if is_resolution and ticket.status not in ['resolved', 'closed']:
        change_status(ticket_id, 'resolved', changed_by_id=author_id, reason="Marked as resolved via comment")

    db.session.commit()
    return comment


def calculate_first_response_due(priority):
    """
    Calculate first response due date based on priority

    Args:
        priority: Ticket priority level

    Returns:
        datetime: Due date for first response
    """
    now = datetime.utcnow()

    # Simple SLA times (can be made configurable later)
    sla_hours = {
        'urgent': 1,    # 1 hour
        'high': 4,      # 4 hours
        'medium': 24,   # 24 hours
        'low': 48       # 48 hours
    }

    hours = sla_hours.get(priority, 24)
    return now + timedelta(hours=hours)


def calculate_resolution_due(priority):
    """
    Calculate resolution due date based on priority

    Args:
        priority: Ticket priority level

    Returns:
        datetime: Due date for resolution
    """
    now = datetime.utcnow()

    # Simple SLA times (can be made configurable later)
    sla_hours = {
        'urgent': 4,     # 4 hours
        'high': 24,      # 1 day
        'medium': 72,    # 3 days
        'low': 168       # 7 days
    }

    hours = sla_hours.get(priority, 72)
    return now + timedelta(hours=hours)


def merge_tickets(source_ticket_id, target_ticket_id, merged_by_id=None):
    """
    Merge one ticket into another

    Args:
        source_ticket_id: Ticket to merge (will be closed)
        target_ticket_id: Ticket to merge into
        merged_by_id: User performing the merge

    Returns:
        Ticket: The target ticket
    """
    source = Ticket.query.get(source_ticket_id)
    target = Ticket.query.get(target_ticket_id)

    if not source or not target:
        raise ValueError("Ticket not found")

    if source.tenant_id != target.tenant_id:
        raise ValueError("Cannot merge tickets from different tenants")

    # Link tickets
    source.related_ticket_id = target_ticket_id

    # Add merge comment to target
    merge_comment = f"Ticket {source.ticket_number} was merged into this ticket."
    add_comment(
        target_ticket_id,
        merge_comment,
        author_id=merged_by_id,
        author_type='system',
        is_public=False
    )

    # Close source ticket
    change_status(
        source_ticket_id,
        'closed',
        changed_by_id=merged_by_id,
        reason=f"Merged into {target.ticket_number}"
    )

    db.session.commit()
    return target


def get_ticket_metrics(tenant_id):
    """
    Get ticket metrics for dashboard

    Args:
        tenant_id: The tenant ID

    Returns:
        dict: Metrics dictionary
    """
    from sqlalchemy import func

    # Count by status
    status_counts = dict(
        db.session.query(Ticket.status, func.count(Ticket.id))
        .filter_by(tenant_id=tenant_id)
        .group_by(Ticket.status)
        .all()
    )

    # Count by priority
    priority_counts = dict(
        db.session.query(Ticket.priority, func.count(Ticket.id))
        .filter_by(tenant_id=tenant_id)
        .group_by(Ticket.priority)
        .all()
    )

    # Open tickets
    open_count = Ticket.query.filter_by(tenant_id=tenant_id).filter(
        Ticket.status.in_(['new', 'open', 'pending', 'on_hold'])
    ).count()

    # Unassigned tickets
    unassigned_count = Ticket.query.filter_by(tenant_id=tenant_id, assignee_id=None).filter(
        Ticket.status.in_(['new', 'open', 'pending'])
    ).count()

    # Overdue tickets
    overdue_count = Ticket.query.filter_by(tenant_id=tenant_id).filter(
        Ticket.resolution_due_at < datetime.utcnow(),
        Ticket.status.notin_(['resolved', 'closed'])
    ).count()

    # Average response time (for tickets with first response)
    tickets_with_response = Ticket.query.filter_by(tenant_id=tenant_id).filter(
        Ticket.first_response_at.isnot(None)
    ).all()

    avg_response_time = None
    if tickets_with_response:
        total_seconds = sum([
            (t.first_response_at - t.created_at).total_seconds()
            for t in tickets_with_response
        ])
        avg_response_time = total_seconds / len(tickets_with_response) / 3600  # In hours

    return {
        'status_counts': status_counts,
        'priority_counts': priority_counts,
        'open_count': open_count,
        'unassigned_count': unassigned_count,
        'overdue_count': overdue_count,
        'avg_response_time_hours': avg_response_time
    }
