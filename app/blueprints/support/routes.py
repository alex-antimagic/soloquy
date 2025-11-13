from flask import render_template, request, jsonify, g, current_app
from flask_login import login_required, current_user
from app.blueprints.support import support_bp
from app.models.ticket import Ticket
from app.models.ticket_comment import TicketComment
from app.models.ticket_attachment import TicketAttachment
from app.models.contact import Contact
from app.models.company import Company
from app.models.user import User
from app.models.department import Department
from app.services import ticket_service
from app.services.cloudinary_service import upload_image
from app.services.ai_service import get_ai_service
from app import db
from datetime import datetime
import base64


# ========== DASHBOARD ==========

@support_bp.route('/')
@login_required
def index():
    """Support dashboard with metrics"""
    # Get ticket metrics
    metrics = ticket_service.get_ticket_metrics(g.current_tenant.id)

    # Get recent tickets
    recent_tickets = Ticket.query.filter_by(
        tenant_id=g.current_tenant.id
    ).order_by(Ticket.created_at.desc()).limit(10).all()

    # Get my assigned tickets
    my_tickets = Ticket.query.filter_by(
        tenant_id=g.current_tenant.id,
        assignee_id=current_user.id
    ).filter(Ticket.status.in_(['new', 'open', 'pending'])).order_by(Ticket.created_at.desc()).limit(5).all()

    # Get unassigned tickets
    unassigned_tickets = Ticket.query.filter_by(
        tenant_id=g.current_tenant.id,
        assignee_id=None
    ).filter(Ticket.status.in_(['new', 'open'])).order_by(Ticket.created_at.asc()).limit(5).all()

    return render_template('support/index.html',
                          title='Support',
                          metrics=metrics,
                          recent_tickets=recent_tickets,
                          my_tickets=my_tickets,
                          unassigned_tickets=unassigned_tickets)


# ========== TICKET LIST & VIEWS ==========

@support_bp.route('/tickets')
@login_required
def tickets():
    """List all tickets with filters"""
    # Get filter parameters
    status_filter = request.args.get('status')
    priority_filter = request.args.get('priority')
    assignee_filter = request.args.get('assignee')
    department_filter = request.args.get('department')
    search = request.args.get('search', '')

    # Build query
    query = Ticket.query.filter_by(tenant_id=g.current_tenant.id)

    # Apply filters
    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    if assignee_filter:
        if assignee_filter == 'unassigned':
            query = query.filter_by(assignee_id=None)
        else:
            query = query.filter_by(assignee_id=int(assignee_filter))
    if department_filter:
        query = query.filter_by(department_id=int(department_filter))
    if search:
        query = query.filter(
            db.or_(
                Ticket.ticket_number.ilike(f'%{search}%'),
                Ticket.subject.ilike(f'%{search}%'),
                Ticket.description.ilike(f'%{search}%')
            )
        )

    # Execute query with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 25
    tickets_paginated = query.order_by(Ticket.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Get filter options
    agents = User.query.join(User.tenant_memberships).filter_by(tenant_id=g.current_tenant.id).all()
    departments = Department.query.filter_by(tenant_id=g.current_tenant.id).all()

    return render_template('support/tickets/index.html',
                          title='Tickets',
                          tickets=tickets_paginated.items,
                          pagination=tickets_paginated,
                          agents=agents,
                          departments=departments,
                          current_filters={
                              'status': status_filter,
                              'priority': priority_filter,
                              'assignee': assignee_filter,
                              'department': department_filter,
                              'search': search
                          })


@support_bp.route('/tickets/my')
@login_required
def my_tickets():
    """List tickets assigned to current user"""
    tickets = Ticket.query.filter_by(
        tenant_id=g.current_tenant.id,
        assignee_id=current_user.id
    ).filter(Ticket.status.notin_(['closed'])).order_by(Ticket.created_at.desc()).all()

    return render_template('support/tickets/my_tickets.html',
                          title='My Tickets',
                          tickets=tickets)


@support_bp.route('/tickets/unassigned')
@login_required
def unassigned_tickets():
    """List unassigned tickets"""
    tickets = Ticket.query.filter_by(
        tenant_id=g.current_tenant.id,
        assignee_id=None
    ).filter(Ticket.status.in_(['new', 'open', 'pending'])).order_by(Ticket.created_at.asc()).all()

    return render_template('support/tickets/unassigned.html',
                          title='Unassigned Tickets',
                          tickets=tickets)


# ========== TICKET DETAIL ==========

@support_bp.route('/tickets/<int:ticket_id>')
@login_required
def ticket_detail(ticket_id):
    """View ticket details"""
    ticket = Ticket.query.get_or_404(ticket_id)

    # Verify tenant access
    if ticket.tenant_id != g.current_tenant.id:
        return "Access denied", 403

    # Get comments ordered by creation time
    comments = ticket.comments.order_by(TicketComment.created_at.asc()).all()

    # Get status history
    status_history = ticket.status_history.order_by(db.desc('created_at')).all()

    # Get available agents for assignment
    agents = User.query.join(User.tenant_memberships).filter_by(tenant_id=g.current_tenant.id).all()

    # Get departments
    departments = Department.query.filter_by(tenant_id=g.current_tenant.id).all()

    # Get companies for linking
    companies = Company.query.filter_by(tenant_id=g.current_tenant.id).order_by(Company.name).all()

    # Get contacts for linking
    contacts = Contact.query.filter_by(tenant_id=g.current_tenant.id).order_by(Contact.first_name).all()

    return render_template('support/tickets/detail.html',
                          title=f'{ticket.ticket_number}: {ticket.subject}',
                          ticket=ticket,
                          comments=comments,
                          status_history=status_history,
                          agents=agents,
                          departments=departments,
                          companies=companies,
                          contacts=contacts)


# ========== CREATE TICKET ==========

@support_bp.route('/tickets/new')
@login_required
def new_ticket():
    """Show create ticket form"""
    # Get data for form dropdowns
    contacts = Contact.query.filter_by(tenant_id=g.current_tenant.id).order_by(Contact.first_name).all()
    companies = Company.query.filter_by(tenant_id=g.current_tenant.id).order_by(Company.name).all()
    agents = User.query.join(User.tenant_memberships).filter_by(tenant_id=g.current_tenant.id).all()
    departments = Department.query.filter_by(tenant_id=g.current_tenant.id).all()

    return render_template('support/tickets/new.html',
                          title='Create Ticket',
                          contacts=contacts,
                          companies=companies,
                          agents=agents,
                          departments=departments)


# ========== BUG REPORT WITH AI ANALYSIS ==========

@support_bp.route('/bug-report/analyze', methods=['POST'])
@login_required
def analyze_bug_screenshot():
    """Analyze a bug screenshot using Claude and upload to Cloudinary"""
    try:
        # Validate file upload
        if 'screenshot' not in request.files:
            return jsonify({'error': 'No screenshot provided'}), 400

        file = request.files['screenshot']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Validate file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        max_size = current_app.config.get('MAX_FILE_SIZE', 10 * 1024 * 1024)
        if file_size > max_size:
            return jsonify({'error': f'File too large. Maximum size is {max_size // (1024 * 1024)}MB'}), 400

        # Validate file type
        allowed_extensions = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif'})
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

        if file_ext not in allowed_extensions:
            return jsonify({'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400

        # Read file content
        file_content = file.read()

        # Convert to base64 for Claude
        file_base64 = base64.b64encode(file_content).decode('utf-8')

        # Determine MIME type
        mime_types = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif'
        }
        mime_type = mime_types.get(file_ext, 'image/png')

        # Get context from request
        current_url = request.form.get('current_url', '')

        # Analyze with Claude
        ai_service = get_ai_service()
        analysis = ai_service.analyze_bug_screenshot(
            image_base64=file_base64,
            image_media_type=mime_type,
            current_url=current_url,
            tenant_name=g.current_tenant.name,
            user_name=current_user.full_name
        )

        # Upload to Cloudinary
        # Reset file position
        file.seek(0)
        upload_result = upload_image(file, folder="bug_reports")

        return jsonify({
            'success': True,
            'subject': analysis['subject'],
            'description': analysis['description'],
            'priority': analysis['priority'],
            'screenshot_url': upload_result['secure_url'],
            'screenshot_public_id': upload_result['public_id']
        })

    except Exception as e:
        current_app.logger.error(f"Error analyzing bug screenshot: {str(e)}")
        return jsonify({'error': 'Failed to analyze screenshot. Please try again.'}), 500


@support_bp.route('/tickets/create', methods=['POST'])
@login_required
def create_ticket():
    """Create a new ticket"""
    data = request.get_json()

    # Validate required fields
    subject = data.get('subject')
    description = data.get('description')

    if not subject or not description:
        return jsonify({'error': 'Subject and description are required'}), 400

    try:
        # Create ticket using service
        ticket = ticket_service.create_ticket(
            tenant_id=g.current_tenant.id,
            subject=subject,
            description=description,
            priority=data.get('priority', 'medium'),
            category=data.get('category'),
            source=data.get('source', 'web'),
            requester_id=data.get('requester_id'),
            requester_email=data.get('requester_email'),
            requester_name=data.get('requester_name'),
            company_id=data.get('company_id'),
            assignee_id=data.get('assignee_id'),
            department_id=data.get('department_id'),
            tags=data.get('tags'),
            created_by_id=current_user.id
        )

        # Handle screenshot attachment if provided
        screenshot_url = data.get('screenshot_url')
        if screenshot_url:
            # Create ticket attachment record
            attachment = TicketAttachment(
                ticket_id=ticket.id,
                filename='bug_screenshot.png',
                file_path=screenshot_url,  # Store Cloudinary URL
                file_size=0,  # Size not tracked for Cloudinary URLs
                content_type='image/png',
                uploaded_by_id=current_user.id
            )
            db.session.add(attachment)
            db.session.commit()

        return jsonify({
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'success': True
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ========== UPDATE TICKET ==========

@support_bp.route('/tickets/<int:ticket_id>/update', methods=['POST'])
@login_required
def update_ticket(ticket_id):
    """Update ticket details"""
    ticket = Ticket.query.get_or_404(ticket_id)

    # Verify tenant access
    if ticket.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()

    try:
        # Update allowed fields
        if 'subject' in data:
            ticket.subject = data['subject']
        if 'description' in data:
            ticket.description = data['description']
        if 'priority' in data:
            ticket.priority = data['priority']
        if 'category' in data:
            ticket.category = data['category']
        if 'company_id' in data:
            ticket.company_id = data['company_id'] if data['company_id'] else None
        if 'department_id' in data:
            ticket.department_id = data['department_id'] if data['department_id'] else None
        if 'tags' in data:
            ticket.tags = data['tags']

        ticket.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ========== TICKET ACTIONS ==========

@support_bp.route('/tickets/<int:ticket_id>/assign', methods=['POST'])
@login_required
def assign_ticket(ticket_id):
    """Assign ticket to an agent"""
    data = request.get_json()
    assignee_id = data.get('assignee_id')

    try:
        ticket = ticket_service.assign_ticket(ticket_id, assignee_id, changed_by_id=current_user.id)
        return jsonify({'success': True, 'assignee_id': ticket.assignee_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@support_bp.route('/tickets/<int:ticket_id>/status', methods=['POST'])
@login_required
def change_ticket_status(ticket_id):
    """Change ticket status"""
    data = request.get_json()
    new_status = data.get('status')

    if not new_status:
        return jsonify({'error': 'Status is required'}), 400

    try:
        ticket = ticket_service.change_status(
            ticket_id,
            new_status,
            changed_by_id=current_user.id,
            reason=data.get('reason')
        )
        return jsonify({'success': True, 'status': ticket.status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@support_bp.route('/tickets/<int:ticket_id>/priority', methods=['POST'])
@login_required
def change_ticket_priority(ticket_id):
    """Change ticket priority"""
    ticket = Ticket.query.get_or_404(ticket_id)

    # Verify tenant access
    if ticket.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    new_priority = data.get('priority')

    if not new_priority:
        return jsonify({'error': 'Priority is required'}), 400

    try:
        ticket.priority = new_priority
        ticket.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'priority': ticket.priority})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@support_bp.route('/tickets/<int:ticket_id>/comment', methods=['POST'])
@login_required
def add_ticket_comment(ticket_id):
    """Add a comment to a ticket"""
    data = request.get_json()
    body = data.get('body')

    if not body:
        return jsonify({'error': 'Comment body is required'}), 400

    try:
        comment = ticket_service.add_comment(
            ticket_id=ticket_id,
            body=body,
            author_id=current_user.id,
            author_type='agent',
            is_public=data.get('is_public', True),
            is_resolution=data.get('is_resolution', False)
        )

        return jsonify({
            'success': True,
            'comment_id': comment.id,
            'created_at': comment.created_at.isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@support_bp.route('/tickets/<int:ticket_id>/merge', methods=['POST'])
@login_required
def merge_ticket(ticket_id):
    """Merge ticket into another ticket"""
    data = request.get_json()
    target_ticket_id = data.get('target_ticket_id')

    if not target_ticket_id:
        return jsonify({'error': 'Target ticket ID is required'}), 400

    try:
        target_ticket = ticket_service.merge_tickets(
            ticket_id,
            target_ticket_id,
            merged_by_id=current_user.id
        )

        return jsonify({
            'success': True,
            'target_ticket_id': target_ticket.id,
            'target_ticket_number': target_ticket.ticket_number
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== DELETE TICKET ==========

@support_bp.route('/tickets/<int:ticket_id>', methods=['DELETE'])
@login_required
def delete_ticket(ticket_id):
    """Delete a ticket (soft delete by closing)"""
    ticket = Ticket.query.get_or_404(ticket_id)

    # Verify tenant access
    if ticket.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        # Soft delete by closing
        ticket_service.change_status(
            ticket_id,
            'closed',
            changed_by_id=current_user.id,
            reason='Ticket deleted'
        )

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
