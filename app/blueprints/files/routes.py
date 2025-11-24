"""
Files Blueprint Routes
Manages file listing, viewing, and deletion for workspace files
"""
from flask import render_template, redirect, url_for, flash, request, g, jsonify
from flask_login import login_required, current_user
from app import db
from app.blueprints.files import files_bp
from app.models.generated_file import GeneratedFile
from app.services.cloudinary_service import delete_image


@files_bp.route('/')
@login_required
def index():
    """List all files in the current workspace"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Get filter parameters
    file_type = request.args.get('type')
    agent_id = request.args.get('agent')

    # Build query
    query = GeneratedFile.query.filter_by(tenant_id=g.current_tenant.id)

    if file_type:
        query = query.filter_by(file_type=file_type)

    if agent_id:
        query = query.filter_by(agent_id=agent_id)

    # Order by newest first
    query = query.order_by(GeneratedFile.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    files = pagination.items

    # Get file type counts for filter UI
    type_counts = db.session.query(
        GeneratedFile.file_type,
        db.func.count(GeneratedFile.id)
    ).filter_by(
        tenant_id=g.current_tenant.id
    ).group_by(
        GeneratedFile.file_type
    ).all()

    # Get agents who have generated files for filter UI
    from app.models.agent import Agent
    agent_files = db.session.query(
        Agent.id,
        Agent.name,
        db.func.count(GeneratedFile.id).label('file_count')
    ).join(
        GeneratedFile
    ).filter(
        GeneratedFile.tenant_id == g.current_tenant.id
    ).group_by(
        Agent.id,
        Agent.name
    ).all()

    return render_template(
        'files/index.html',
        title='Files',
        files=files,
        pagination=pagination,
        type_counts=dict(type_counts),
        agent_files=agent_files,
        current_file_type=file_type,
        current_agent_id=int(agent_id) if agent_id else None
    )


@files_bp.route('/<int:file_id>')
@login_required
def view(file_id):
    """View/download a specific file"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Get file and verify it belongs to current tenant
    file = GeneratedFile.query.filter_by(
        id=file_id,
        tenant_id=g.current_tenant.id
    ).first_or_404()

    # Redirect to Cloudinary URL for download
    return redirect(file.cloudinary_url)


@files_bp.route('/delete/<int:file_id>', methods=['POST'])
@login_required
def delete(file_id):
    """Delete a file"""
    if not g.current_tenant:
        return jsonify({'error': 'No workspace selected'}), 400

    # Get file and verify it belongs to current tenant
    file = GeneratedFile.query.filter_by(
        id=file_id,
        tenant_id=g.current_tenant.id
    ).first_or_404()

    # Check if user has permission (owner/admin or the user who requested the file)
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin'] and file.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403

    try:
        # Delete from Cloudinary
        delete_image(file.cloudinary_public_id)

        # Delete from database
        db.session.delete(file)
        db.session.commit()

        flash(f'File "{file.filename}" deleted successfully.', 'success')
        return jsonify({'success': True})

    except Exception as e:
        current_app.logger.error(f"Error deleting file {file_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete file'}), 500


@files_bp.route('/stats')
@login_required
def stats():
    """Get file statistics for the workspace"""
    if not g.current_tenant:
        return jsonify({'error': 'No workspace selected'}), 400

    # Total files
    total_files = GeneratedFile.query.filter_by(
        tenant_id=g.current_tenant.id
    ).count()

    # Total storage used (bytes)
    total_storage = db.session.query(
        db.func.sum(GeneratedFile.file_size)
    ).filter_by(
        tenant_id=g.current_tenant.id
    ).scalar() or 0

    # Files by type
    files_by_type = db.session.query(
        GeneratedFile.file_type,
        db.func.count(GeneratedFile.id)
    ).filter_by(
        tenant_id=g.current_tenant.id
    ).group_by(
        GeneratedFile.file_type
    ).all()

    # Recent files (last 7 days)
    from datetime import datetime, timedelta
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_files = GeneratedFile.query.filter(
        GeneratedFile.tenant_id == g.current_tenant.id,
        GeneratedFile.created_at >= seven_days_ago
    ).count()

    return jsonify({
        'total_files': total_files,
        'total_storage': total_storage,
        'total_storage_display': _format_bytes(total_storage),
        'files_by_type': dict(files_by_type),
        'recent_files': recent_files
    })


def _format_bytes(size):
    """Helper to format bytes to human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"
