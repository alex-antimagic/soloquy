import os
import stripe
from flask import render_template, redirect, url_for, request, jsonify, flash, g
from flask_login import login_required, current_user
from app import db
from app.blueprints.billing import billing_bp

# Configure Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# Stripe price IDs — set these in Heroku config vars
# STRIPE_PRO_PRICE_ID    = flat $49/month recurring price
# STRIPE_USAGE_PRICE_ID  = metered $10/1000 messages price (aggregate_usage=sum, billing_scheme=tiered or per_unit)
STRIPE_PRO_PRICE_ID   = os.environ.get('STRIPE_PRO_PRICE_ID')
STRIPE_USAGE_PRICE_ID = os.environ.get('STRIPE_USAGE_PRICE_ID')

# Pricing configuration
PRICING_PLANS = {
    'free': {
        'name': 'Free',
        'price': 0,
        'price_id': None,
        'ai_messages_included': 100,
        'features': [
            '1 workspace',
            '3 AI agents',
            '100 AI messages/month',
            'Core tools (Chat, CRM, Projects)',
            'Community support',
        ]
    },
    'pro': {
        'name': 'Pro',
        'price': 49,  # $49/month flat
        'price_id': STRIPE_PRO_PRICE_ID,
        'ai_messages_included': 1000,
        'overage_per_1k': 10,  # $10 per 1,000 messages over included
        'features': [
            'Unlimited users',
            'Unlimited AI agents',
            '1,000 AI messages/month included',
            '$10 per 1,000 additional messages',
            'All 10 tools included',
            'Priority support',
            'Advanced analytics',
        ]
    }
}

AI_MESSAGES_FREE_LIMIT = 100
AI_MESSAGES_PRO_INCLUDED = 1000


@billing_bp.route('/pricing')
def pricing():
    """Show pricing page"""
    return render_template('billing/pricing.html',
                           pricing_plans=PRICING_PLANS,
                           current_plan=current_user.plan if current_user.is_authenticated else 'free')


@billing_bp.route('/checkout/create-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe Checkout session with flat base + metered usage prices"""
    try:
        plan = request.form.get('plan', 'pro')

        if plan not in PRICING_PLANS or plan == 'free':
            flash('Invalid plan selected', 'danger')
            return redirect(url_for('billing.pricing'))

        if not STRIPE_PRO_PRICE_ID:
            flash('Pricing not configured. Please contact support.', 'danger')
            return redirect(url_for('billing.pricing'))

        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name,
                metadata={'user_id': current_user.id}
            )
            current_user.stripe_customer_id = customer.id
            db.session.commit()

        line_items = [
            {'price': STRIPE_PRO_PRICE_ID, 'quantity': 1},
        ]

        # Add metered usage price if configured
        if STRIPE_USAGE_PRICE_ID:
            line_items.append({'price': STRIPE_USAGE_PRICE_ID})

        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=line_items,
            mode='subscription',
            success_url=url_for('billing.checkout_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('billing.pricing', _external=True),
            metadata={
                'user_id': current_user.id,
                'plan': plan
            }
        )

        return redirect(checkout_session.url, code=303)

    except stripe.error.StripeError as e:
        flash(f'Stripe error: {str(e)}', 'danger')
        return redirect(url_for('billing.pricing'))
    except Exception as e:
        print(f"[CHECKOUT ERROR] {e}")
        flash('An error occurred. Please try again.', 'danger')
        return redirect(url_for('billing.pricing'))


@billing_bp.route('/checkout/success')
@login_required
def checkout_success():
    """Handle successful checkout — extract metered usage item ID from subscription"""
    session_id = request.args.get('session_id')

    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == 'paid':
                plan = session.metadata.get('plan', 'pro')
                current_user.plan = plan

                if session.subscription:
                    current_user.stripe_subscription_id = session.subscription

                    # Find and store the metered usage subscription item ID
                    if STRIPE_USAGE_PRICE_ID:
                        subscription = stripe.Subscription.retrieve(session.subscription)
                        for item in subscription['items']['data']:
                            if item['price']['id'] == STRIPE_USAGE_PRICE_ID:
                                current_user.stripe_usage_subscription_item_id = item['id']
                                break

                db.session.commit()
                flash(f'Welcome to Pro! Your subscription is active.', 'success')
            else:
                flash('Payment is being processed. You will receive a confirmation email shortly.', 'info')

        except Exception as e:
            print(f"[CHECKOUT SUCCESS ERROR] {e}")
            flash('Subscription activated, but there was an error loading details.', 'warning')

    return redirect(url_for('billing.subscription'))


@billing_bp.route('/subscription')
@login_required
def subscription():
    """Show subscription management page with current usage"""
    subscription_data = None
    usage_data = None

    if current_user.stripe_subscription_id:
        try:
            subscription_data = stripe.Subscription.retrieve(current_user.stripe_subscription_id)
        except Exception as e:
            print(f"[SUBSCRIPTION RETRIEVE ERROR] {e}")

    # Get current month AI usage for primary tenant
    try:
        from app.models.tenant import TenantMembership
        membership = TenantMembership.query.filter_by(
            user_id=current_user.id,
            role='owner',
            is_active=True
        ).first()

        if membership:
            usage_count = current_user.get_current_month_ai_usage(membership.tenant_id)
            limit = current_user.get_ai_message_limit()
            usage_data = {
                'count': usage_count,
                'limit': limit,
                'percentage': min(round((usage_count / limit) * 100), 100) if limit else 0,
                'overage': max(0, usage_count - limit),
                'overage_cost': max(0, (usage_count - limit) / 1000 * 10) if current_user.is_pro() else 0,
            }
    except Exception as e:
        print(f"[USAGE DATA ERROR] {e}")

    return render_template('billing/subscription.html',
                           pricing_plans=PRICING_PLANS,
                           subscription=subscription_data,
                           usage=usage_data,
                           stripe_publishable_key=STRIPE_PUBLISHABLE_KEY)


@billing_bp.route('/subscription/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel current subscription at period end"""
    if not current_user.stripe_subscription_id:
        flash('No active subscription found', 'warning')
        return redirect(url_for('billing.subscription'))

    try:
        stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=True
        )
        flash('Subscription will be canceled at the end of the billing period', 'info')

    except stripe.error.StripeError as e:
        flash(f'Error canceling subscription: {str(e)}', 'danger')
    except Exception as e:
        print(f"[CANCEL SUBSCRIPTION ERROR] {e}")
        flash('An error occurred. Please contact support.', 'danger')

    return redirect(url_for('billing.subscription'))


@billing_bp.route('/subscription/reactivate', methods=['POST'])
@login_required
def reactivate_subscription():
    """Reactivate a canceled subscription"""
    if not current_user.stripe_subscription_id:
        flash('No subscription found', 'warning')
        return redirect(url_for('billing.subscription'))

    try:
        stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=False
        )
        flash('Subscription reactivated successfully', 'success')

    except stripe.error.StripeError as e:
        flash(f'Error reactivating subscription: {str(e)}', 'danger')
    except Exception as e:
        print(f"[REACTIVATE SUBSCRIPTION ERROR] {e}")
        flash('An error occurred. Please contact support.', 'danger')

    return redirect(url_for('billing.subscription'))


@billing_bp.route('/subscription/portal', methods=['POST'])
@login_required
def customer_portal():
    """Redirect to Stripe Customer Portal"""
    if not current_user.stripe_customer_id:
        flash('No customer account found', 'warning')
        return redirect(url_for('billing.subscription'))

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=url_for('billing.subscription', _external=True)
        )
        return redirect(portal_session.url, code=303)

    except stripe.error.StripeError as e:
        flash(f'Error accessing customer portal: {str(e)}', 'danger')
    except Exception as e:
        print(f"[CUSTOMER PORTAL ERROR] {e}")
        flash('An error occurred. Please contact support.', 'danger')

    return redirect(url_for('billing.subscription'))


@billing_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    if not STRIPE_WEBHOOK_SECRET:
        print("[WEBHOOK WARNING] No webhook secret configured")
        return jsonify({'error': 'Webhook secret not configured'}), 400

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError as e:
        print(f"[WEBHOOK ERROR] Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        print(f"[WEBHOOK ERROR] Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400

    event_type = event['type']

    try:
        if event_type == 'checkout.session.completed':
            handle_checkout_completed(event['data']['object'])
        elif event_type == 'customer.subscription.created':
            handle_subscription_created(event['data']['object'])
        elif event_type == 'customer.subscription.updated':
            handle_subscription_updated(event['data']['object'])
        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(event['data']['object'])
        elif event_type == 'invoice.payment_failed':
            handle_payment_failed(event['data']['object'])
        else:
            print(f"[WEBHOOK] Unhandled event type: {event_type}")

    except Exception as e:
        print(f"[WEBHOOK ERROR] Error processing {event_type}: {e}")
        return jsonify({'error': 'Error processing event'}), 500

    return jsonify({'status': 'success'}), 200


# ── Webhook handlers ──────────────────────────────────────────────────────────

def handle_checkout_completed(session):
    user_id = session.get('metadata', {}).get('user_id')
    if not user_id:
        return

    from app.models.user import User
    user = User.query.get(int(user_id))
    if not user:
        return

    plan = session.get('metadata', {}).get('plan', 'pro')
    user.plan = plan
    subscription_id = session.get('subscription')
    user.stripe_subscription_id = subscription_id

    # Capture metered usage item ID
    if subscription_id and STRIPE_USAGE_PRICE_ID:
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            for item in subscription['items']['data']:
                if item['price']['id'] == STRIPE_USAGE_PRICE_ID:
                    user.stripe_usage_subscription_item_id = item['id']
                    break
        except Exception as e:
            print(f"[WEBHOOK] Could not retrieve usage item ID: {e}")

    db.session.commit()
    print(f"[WEBHOOK] User {user_id} upgraded to {plan}")


def handle_subscription_created(subscription):
    customer_id = subscription.get('customer')

    from app.models.user import User
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    user.stripe_subscription_id = subscription['id']
    user.plan = 'pro'

    # Capture metered usage item ID
    if STRIPE_USAGE_PRICE_ID:
        for item in subscription.get('items', {}).get('data', []):
            if item['price']['id'] == STRIPE_USAGE_PRICE_ID:
                user.stripe_usage_subscription_item_id = item['id']
                break

    db.session.commit()
    print(f"[WEBHOOK] Subscription {subscription['id']} created for user {user.id}")


def handle_subscription_updated(subscription):
    customer_id = subscription.get('customer')

    from app.models.user import User
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    status = subscription.get('status')
    if status not in ['active', 'trialing']:
        user.plan = 'free'
        user.stripe_usage_subscription_item_id = None
        print(f"[WEBHOOK] Subscription {subscription['id']} is {status}, downgrading user {user.id}")

    db.session.commit()


def handle_subscription_deleted(subscription):
    customer_id = subscription.get('customer')

    from app.models.user import User
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    user.plan = 'free'
    user.stripe_subscription_id = None
    user.stripe_usage_subscription_item_id = None
    db.session.commit()
    print(f"[WEBHOOK] Subscription deleted for user {user.id}, downgraded to free")


def handle_payment_failed(invoice):
    customer_id = invoice.get('customer')

    from app.models.user import User
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    print(f"[WEBHOOK] Payment failed for user {user.id}")
    try:
        from app.services.email_service import EmailService
        email_service = EmailService()
        email_service.send_security_alert_email(user, 'payment_failed', {
            'message': 'Your worklead payment failed. Please update your payment method to continue service.'
        })
    except Exception as e:
        print(f"[WEBHOOK] Could not send payment failed email: {e}")
