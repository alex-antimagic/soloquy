from flask import render_template, redirect, url_for, flash, request, g
from flask_login import login_required, current_user
from app import db
from app.blueprints.marketplace import marketplace_bp
from app.models.marketplace_agent import MarketplaceAgent, AgentReview, AgentInstall
from app.models.agent import Agent
from app.models.department import Department


@marketplace_bp.route('/')
@login_required
def index():
    """Browse marketplace agents"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Get filter parameters
    category = request.args.get('category')
    search = request.args.get('search')
    sort = request.args.get('sort', 'popular')  # popular, recent, rating

    # Base query - only active agents (global or workspace-specific)
    query = MarketplaceAgent.query.filter(
        MarketplaceAgent.is_active == True,
        db.or_(
            MarketplaceAgent.tenant_id == None,  # Global/public
            MarketplaceAgent.tenant_id == g.current_tenant.id  # Workspace-specific
        )
    )

    # Apply category filter
    if category:
        query = query.filter(MarketplaceAgent.category == category)

    # Apply search filter
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                MarketplaceAgent.name.ilike(search_term),
                MarketplaceAgent.description.ilike(search_term)
            )
        )

    # Apply sorting
    if sort == 'popular':
        query = query.order_by(MarketplaceAgent.install_count.desc())
    elif sort == 'recent':
        query = query.order_by(MarketplaceAgent.created_at.desc())
    elif sort == 'rating':
        query = query.order_by(MarketplaceAgent.average_rating.desc())

    agents = query.all()

    # Get featured agents
    featured = MarketplaceAgent.query.filter_by(
        is_active=True,
        is_featured=True
    ).order_by(MarketplaceAgent.install_count.desc()).limit(3).all()

    # Get categories for filter
    categories = db.session.query(MarketplaceAgent.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]

    return render_template('marketplace/index.html',
                          title='Agent Marketplace',
                          agents=agents,
                          featured=featured,
                          categories=categories,
                          current_category=category,
                          current_search=search,
                          current_sort=sort)


@marketplace_bp.route('/agent/<int:agent_id>')
@login_required
def view_agent(agent_id):
    """View marketplace agent details"""
    marketplace_agent = MarketplaceAgent.query.get_or_404(agent_id)

    # Check if user has already installed this agent
    installed = AgentInstall.query.filter_by(
        marketplace_agent_id=agent_id,
        tenant_id=g.current_tenant.id
    ).first()

    # Get reviews
    reviews = AgentReview.query.filter_by(
        marketplace_agent_id=agent_id,
        is_active=True
    ).order_by(AgentReview.created_at.desc()).all()

    # Check if user has reviewed
    user_review = AgentReview.query.filter_by(
        marketplace_agent_id=agent_id,
        user_id=current_user.id,
        tenant_id=g.current_tenant.id
    ).first()

    return render_template('marketplace/agent_detail.html',
                          title=marketplace_agent.name,
                          marketplace_agent=marketplace_agent,
                          installed=installed,
                          reviews=reviews,
                          user_review=user_review)


@marketplace_bp.route('/agent/<int:agent_id>/install', methods=['POST'])
@login_required
def install_agent(agent_id):
    """Install a marketplace agent to workspace"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('marketplace.index'))

    # Security: Only owners and admins can install agents
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('Only workspace owners and admins can install agents.', 'danger')
        return redirect(url_for('marketplace.index'))

    marketplace_agent = MarketplaceAgent.query.get_or_404(agent_id)

    # Check if already installed
    existing = AgentInstall.query.filter_by(
        marketplace_agent_id=agent_id,
        tenant_id=g.current_tenant.id
    ).first()

    if existing:
        flash('This agent is already installed in your workspace.', 'info')
        return redirect(url_for('marketplace.view_agent', agent_id=agent_id))

    # Get department to install to
    department_id = request.form.get('department_id', type=int)
    if not department_id:
        flash('Please select a department.', 'danger')
        return redirect(url_for('marketplace.view_agent', agent_id=agent_id))

    # Security: Fetch department with tenant validation built-in
    department = Department.query.filter_by(
        id=department_id,
        tenant_id=g.current_tenant.id
    ).first_or_404()

    try:
        # Create agent from marketplace listing
        agent_data = {
            'agent': {
                'name': marketplace_agent.name,
                'description': marketplace_agent.description,
                'avatar_url': marketplace_agent.avatar_url,
                'system_prompt': marketplace_agent.system_prompt,
                'model': marketplace_agent.model,
                'temperature': marketplace_agent.temperature,
                'max_tokens': marketplace_agent.max_tokens,
                'is_active': True,
                'enable_quickbooks': False,
                'enable_gmail': False,
                'enable_outlook': False,
                'enable_google_drive': False,
                'enable_website_builder': False
            },
            'metadata': {
                'original_department': 'Marketplace',
                'created_by': marketplace_agent.published_by.full_name if marketplace_agent.published_by else 'Unknown'
            }
        }

        # Import agent
        new_agent, _, _ = Agent.import_from_json(
            json_data=agent_data,
            department_id=department.id,
            created_by_user=current_user
        )

        # Record installation
        install = AgentInstall(
            marketplace_agent_id=agent_id,
            user_id=current_user.id,
            tenant_id=g.current_tenant.id,
            agent_id=new_agent.id
        )
        db.session.add(install)

        # Increment install count
        marketplace_agent.install_count += 1
        db.session.commit()

        flash(f'Agent "{marketplace_agent.name}" installed successfully!', 'success')
        return redirect(url_for('department.edit_agent', agent_id=new_agent.id))

    except Exception as e:
        db.session.rollback()
        # Log detailed error internally, show generic message to user
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Agent installation failed for user {current_user.id}, agent {agent_id}: {type(e).__name__}: {str(e)}")
        flash('Unable to install agent. Please try again later.', 'danger')
        return redirect(url_for('marketplace.view_agent', agent_id=agent_id))


@marketplace_bp.route('/publish/<int:agent_id>', methods=['GET', 'POST'])
@login_required
def publish_agent(agent_id):
    """Publish an agent to the marketplace"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Security: Only owners and admins can publish agents
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('Only workspace owners and admins can publish agents.', 'danger')
        return redirect(url_for('department.index'))

    # Security: Fetch agent with tenant validation built-in
    agent = Agent.query.join(Department).filter(
        Agent.id == agent_id,
        Department.tenant_id == g.current_tenant.id
    ).first_or_404()
    department = agent.department

    if request.method == 'POST':
        # Get form data
        category = request.form.get('category', 'general')
        tags_input = request.form.get('tags', '')
        is_public = request.form.get('visibility') == 'public'

        # Parse tags (comma-separated)
        tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()]

        try:
            # Create marketplace listing
            marketplace_agent = MarketplaceAgent.create_from_agent(
                agent=agent,
                published_by_user=current_user,
                category=category,
                tags=tags,
                is_public=is_public
            )

            visibility = "publicly" if is_public else "to your workspace"
            flash(f'Agent "{agent.name}" published {visibility}!', 'success')
            return redirect(url_for('marketplace.view_agent', agent_id=marketplace_agent.id))

        except Exception as e:
            db.session.rollback()
            # Log detailed error internally, show generic message to user
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Agent publishing failed for user {current_user.id}, agent {agent_id}: {type(e).__name__}: {str(e)}")
            flash('Unable to publish agent. Please try again later.', 'danger')
            return redirect(url_for('marketplace.publish_agent', agent_id=agent.id))

    return render_template('marketplace/publish.html',
                          title=f'Publish {agent.name}',
                          agent=agent,
                          department=department)


@marketplace_bp.route('/agent/<int:agent_id>/review', methods=['POST'])
@login_required
def add_review(agent_id):
    """Add or update review for a marketplace agent"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('marketplace.index'))

    marketplace_agent = MarketplaceAgent.query.get_or_404(agent_id)

    # Check if user has installed this agent
    install = AgentInstall.query.filter_by(
        marketplace_agent_id=agent_id,
        tenant_id=g.current_tenant.id
    ).first()

    if not install:
        flash('You must install an agent before reviewing it.', 'warning')
        return redirect(url_for('marketplace.view_agent', agent_id=agent_id))

    # Get form data
    rating = request.form.get('rating', type=int)
    review_text = request.form.get('review_text', '').strip()

    # Validate rating
    if not rating or not 1 <= rating <= 5:
        flash('Please provide a rating between 1 and 5 stars.', 'danger')
        return redirect(url_for('marketplace.view_agent', agent_id=agent_id))

    try:
        # Check if user already reviewed
        existing_review = AgentReview.query.filter_by(
            marketplace_agent_id=agent_id,
            user_id=current_user.id,
            tenant_id=g.current_tenant.id
        ).first()

        if existing_review:
            # Update existing review
            existing_review.rating = rating
            existing_review.review_text = review_text if review_text else None
            flash('Your review has been updated.', 'success')
        else:
            # Create new review
            review = AgentReview(
                marketplace_agent_id=agent_id,
                user_id=current_user.id,
                tenant_id=g.current_tenant.id,
                rating=rating,
                review_text=review_text if review_text else None
            )
            db.session.add(review)
            flash('Thank you for your review!', 'success')

        db.session.commit()

        # Update marketplace agent rating stats
        marketplace_agent.update_rating_stats()

    except Exception as e:
        db.session.rollback()
        # Log detailed error internally, show generic message to user
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Review submission failed for user {current_user.id}, agent {agent_id}: {type(e).__name__}: {str(e)}")
        flash('Unable to save review. Please try again later.', 'danger')

    return redirect(url_for('marketplace.view_agent', agent_id=agent_id))


@marketplace_bp.route('/my-published')
@login_required
def my_published():
    """View user's published agents"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Get all agents published by current user
    agents = MarketplaceAgent.query.filter_by(
        published_by_id=current_user.id
    ).order_by(MarketplaceAgent.created_at.desc()).all()

    return render_template('marketplace/my_published.html',
                          title='My Published Agents',
                          agents=agents)
