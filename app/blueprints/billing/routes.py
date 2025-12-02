import os
import stripe
from flask import render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
from app import db
from app.blueprints.billing import billing_bp

# Configure Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# Pricing configuration
PRICING_PLANS = {
    'free': {
        'name': 'Free',
        'price': 0,
        'price_id': None,
        'features': [
            '1 workspace',
            '5 AI agents',
            '100 messages/month',
            'Basic integrations',
            'Community support'
        ]
    },
    'pro': {
        'name': 'Pro',
        'price': 29,  # $29/month
        'price_id': os.environ.get('STRIPE_PRO_PRICE_ID'),  # Set in Heroku config
        'features': [
            'Unlimited workspaces',
            'Unlimited AI agents',
            'Unlimited messages',
            'All integrations',
            'Priority support',
            'Custom branding',
            'Advanced analytics'
        ]
    }
}


@billing_bp.route('/pricing')
def pricing():
    """Show pricing page"""
    return render_template('billing/pricing.html',
                         pricing_plans=PRICING_PLANS,
                         current_plan=current_user.plan if current_user.is_authenticated else 'free')


@billing_bp.route('/checkout/create-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe Checkout session"""
    try:
        plan = request.form.get('plan', 'pro')

        if plan not in PRICING_PLANS or plan == 'free':
            flash('Invalid plan selected', 'danger')
            return redirect(url_for('billing.pricing'))

        price_id = PRICING_PLANS[plan]['price_id']
        if not price_id:
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

        # Create Checkout Session
        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
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
    """Handle successful checkout"""
    session_id = request.args.get('session_id')

    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)

            # Update user plan (webhook will also do this, but this is for immediate feedback)
            if session.payment_status == 'paid':
                plan = session.metadata.get('plan', 'pro')
                current_user.plan = plan
                if session.subscription:
                    current_user.stripe_subscription_id = session.subscription
                db.session.commit()

                flash(f'🎉 Welcome to {PRICING_PLANS[plan]["name"]}! Your subscription is active.', 'success')
            else:
                flash('Payment is being processed. You will receive a confirmation email shortly.', 'info')

        except Exception as e:
            print(f"[CHECKOUT SUCCESS ERROR] {e}")
            flash('Subscription activated, but there was an error loading details.', 'warning')

    return redirect(url_for('billing.subscription'))


@billing_bp.route('/subscription')
@login_required
def subscription():
    """Show subscription management page"""
    subscription_data = None

    if current_user.stripe_subscription_id:
        try:
            subscription_data = stripe.Subscription.retrieve(current_user.stripe_subscription_id)
        except Exception as e:
            print(f"[SUBSCRIPTION RETRIEVE ERROR] {e}")

    return render_template('billing/subscription.html',
                         pricing_plans=PRICING_PLANS,
                         subscription=subscription_data,
                         stripe_publishable_key=STRIPE_PUBLISHABLE_KEY)


@billing_bp.route('/subscription/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel current subscription"""
    if not current_user.stripe_subscription_id:
        flash('No active subscription found', 'warning')
        return redirect(url_for('billing.subscription'))

    try:
        # Cancel subscription at period end (don't charge again)
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
        # Remove the cancel_at_period_end flag
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
        # Create portal session
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
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        print(f"[WEBHOOK ERROR] Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        print(f"[WEBHOOK ERROR] Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle the event
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


def handle_checkout_completed(session):
    """Handle successful checkout"""
    user_id = session.get('metadata', {}).get('user_id')
    if not user_id:
        print("[WEBHOOK] No user_id in checkout session metadata")
        return

    from app.models.user import User
    user = User.query.get(int(user_id))
    if not user:
        print(f"[WEBHOOK] User {user_id} not found")
        return

    plan = session.get('metadata', {}).get('plan', 'pro')
    user.plan = plan
    user.stripe_subscription_id = session.get('subscription')
    db.session.commit()

    print(f"[WEBHOOK] User {user_id} upgraded to {plan}")


def handle_subscription_created(subscription):
    """Handle new subscription"""
    customer_id = subscription.get('customer')

    from app.models.user import User
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        print(f"[WEBHOOK] User with customer {customer_id} not found")
        return

    user.stripe_subscription_id = subscription['id']
    user.plan = 'pro'
    db.session.commit()

    print(f"[WEBHOOK] Subscription {subscription['id']} created for user {user.id}")


def handle_subscription_updated(subscription):
    """Handle subscription update"""
    customer_id = subscription.get('customer')

    from app.models.user import User
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        print(f"[WEBHOOK] User with customer {customer_id} not found")
        return

    # Check if subscription is canceled
    if subscription.get('cancel_at_period_end'):
        print(f"[WEBHOOK] Subscription {subscription['id']} will cancel at period end")

    # Check subscription status
    status = subscription.get('status')
    if status not in ['active', 'trialing']:
        user.plan = 'free'
        print(f"[WEBHOOK] Subscription {subscription['id']} is {status}, downgrading user {user.id}")

    db.session.commit()


def handle_subscription_deleted(subscription):
    """Handle subscription deletion"""
    customer_id = subscription.get('customer')

    from app.models.user import User
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        print(f"[WEBHOOK] User with customer {customer_id} not found")
        return

    user.plan = 'free'
    user.stripe_subscription_id = None
    db.session.commit()

    print(f"[WEBHOOK] Subscription deleted for user {user.id}, downgraded to free")


def handle_payment_failed(invoice):
    """Handle failed payment"""
    customer_id = invoice.get('customer')

    from app.models.user import User
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        print(f"[WEBHOOK] User with customer {customer_id} not found")
        return

    print(f"[WEBHOOK] Payment failed for user {user.id}")
    # TODO: Send email notification about failed payment
