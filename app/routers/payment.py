from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import get_current_user
from app.models import User, Payment, SubscriptionStatus
from app import schemas
from app.config import (
    STRIPE_SECRET_KEY, 
    STRIPE_WEBHOOK_SECRET,
    PREMIUM_PRICE_MONTHLY,
    PREMIUM_PRICE_YEARLY
)
import stripe
from datetime import datetime, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

stripe.api_key = STRIPE_SECRET_KEY

# Plan pricing (in cents)
PLANS = {
    "monthly": PREMIUM_PRICE_MONTHLY,   # $20.00
    "yearly": PREMIUM_PRICE_YEARLY       # $200.00
}

@router.get("/plans")
def get_available_plans():
    """Get available subscription plans"""
    return {
        "plans": [
            {
                "id": "monthly",
                "name": "Monthly Premium",
                "price": PREMIUM_PRICE_MONTHLY / 100,  # Convert to dollars
                "currency": "USD",
                "interval": "month",
                "description": "Full access to all premium features"
            },
            {
                "id": "yearly",
                "name": "Yearly Premium",
                "price": PREMIUM_PRICE_YEARLY / 100,  # Convert to dollars
                "currency": "USD",
                "interval": "year",
                "description": "Full access to all premium features - Save $40/year!",
                "savings": ((PREMIUM_PRICE_MONTHLY * 12) - PREMIUM_PRICE_YEARLY) / 100
            }
        ]
    }

@router.post("/create-checkout-session")
def create_checkout_session(
    data: schemas.CreateCheckoutSession,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout session for subscription"""
    
    if data.plan_type not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan type. Choose 'monthly' or 'yearly'")
    
    amount = PLANS[data.plan_type]
    
    try:
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={
                    "user_id": current_user.id,
                    "name": f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
                }
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        
        # Determine interval and plan name
        interval = "month" if data.plan_type == "monthly" else "year"
        plan_name = "Monthly Premium" if data.plan_type == "monthly" else "Yearly Premium"
        plan_description = f"${amount/100:.2f}/{interval} - Full access to Quran recitation premium features"
        
        BASE_URL = "https://quran-api-arfx.onrender.com"
        # Create Checkout Session for recurring subscription
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Quran Recitation App - {plan_name}',
                        'description': plan_description,
                        'images': ['https://your-app-logo-url.com/logo.png'],  # Optional: Add your app logo
                    },
                    'unit_amount': amount,
                    'recurring': {
                        'interval': interval,
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{BASE_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",            
            cancel_url=f"{BASE_URL}/payment/cancel",            
            metadata={
                'user_id': current_user.id,
                'plan_type': data.plan_type
            },
            # Allow promotion codes
            allow_promotion_codes=True,
            # Billing address collection
            billing_address_collection='auto',
        )
        
        return {
            "checkout_url": session.url, 
            "session_id": session.id,
            "plan": data.plan_type,
            "amount": amount / 100
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events"""
    
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    event_type = event['type']
    logger.info(f"Received Stripe webhook: {event_type}")
    
    if event_type == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session_completed(session, db)
    
    elif event_type == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        handle_invoice_payment_succeeded(invoice, db)
    
    elif event_type == 'invoice.payment_failed':
        invoice = event['data']['object']
        handle_invoice_payment_failed(invoice, db)
    
    elif event_type == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_updated(subscription, db)
    
    elif event_type == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_deleted(subscription, db)
    
    return {"status": "success"}

def handle_checkout_session_completed(session, db: Session):
    """Handle successful checkout session"""
    user_id = int(session['metadata']['user_id'])
    plan_type = session['metadata']['plan_type']
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error(f"User {user_id} not found")
        return
    
    # Update user subscription
    user.subscription_status = SubscriptionStatus.ACTIVE
    user.subscription_plan = plan_type
    user.subscription_start_date = datetime.utcnow()
    
    # Set end date
    if plan_type == "monthly":
        user.subscription_end_date = datetime.utcnow() + timedelta(days=30)
    else:  # yearly
        user.subscription_end_date = datetime.utcnow() + timedelta(days=365)
    
    # Save subscription ID
    if session.get('subscription'):
        user.stripe_subscription_id = session['subscription']
    
    # Record payment - FIX: Get payment_intent_id correctly
    payment_intent_id = (
        session.get('payment_intent') or 
        session.get('id') or 
        f"checkout_{session.get('id', 'unknown')}"
    )
    
    payment = Payment(
        user_id=user_id,
        stripe_payment_intent_id=payment_intent_id,
        amount=session.get('amount_total', 0),
        currency=session.get('currency', 'usd'),
        status='succeeded',
        plan_type=plan_type
    )
    db.add(payment)
    db.commit()
    
    logger.info(f"User {user_id} subscribed to {plan_type} plan")

def handle_invoice_payment_succeeded(invoice, db: Session):
    """Handle successful recurring payment"""
    customer_id = invoice['customer']
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.warning(f"User not found for customer {customer_id}")
        return
    
    # Extend subscription
    if user.subscription_plan == "monthly":
        user.subscription_end_date = datetime.utcnow() + timedelta(days=30)
    elif user.subscription_plan == "yearly":
        user.subscription_end_date = datetime.utcnow() + timedelta(days=365)
    
    user.subscription_status = SubscriptionStatus.ACTIVE
    
    # Record payment
    payment = Payment(
        user_id=user.id,
        stripe_payment_intent_id=invoice.get('payment_intent', invoice['id']),
        amount=invoice['amount_paid'],
        currency=invoice['currency'],
        status='succeeded',
        plan_type=user.subscription_plan
    )
    db.add(payment)
    db.commit()
    
    logger.info(f"Subscription renewed for user {user.id}")

def handle_invoice_payment_failed(invoice, db: Session):
    """Handle failed recurring payment"""
    customer_id = invoice['customer']
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return
    
    # Mark subscription as expired if payment fails
    user.subscription_status = SubscriptionStatus.EXPIRED
    
    # Record failed payment
    payment = Payment(
        user_id=user.id,
        stripe_payment_intent_id=invoice.get('payment_intent', invoice['id']),
        amount=invoice['amount_due'],
        currency=invoice['currency'],
        status='failed',
        plan_type=user.subscription_plan
    )
    db.add(payment)
    db.commit()
    
    logger.warning(f"Payment failed for user {user.id}")

def handle_subscription_updated(subscription, db: Session):
    """Handle subscription updates"""
    customer_id = subscription['customer']
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return
    
    # Update subscription status based on Stripe status
    stripe_status = subscription['status']
    
    if stripe_status == 'active':
        user.subscription_status = SubscriptionStatus.ACTIVE
    elif stripe_status == 'canceled':
        user.subscription_status = SubscriptionStatus.CANCELLED
    elif stripe_status in ['past_due', 'unpaid']:
        user.subscription_status = SubscriptionStatus.EXPIRED
    
    db.commit()
    logger.info(f"Subscription updated for user {user.id}: {stripe_status}")

def handle_subscription_deleted(subscription, db: Session):
    """Handle subscription cancellation"""
    customer_id = subscription['customer']
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return
    
    user.subscription_status = SubscriptionStatus.CANCELLED
    user.stripe_subscription_id = None
    db.commit()
    
    logger.info(f"Subscription cancelled for user {user.id}")

@router.get("/subscription-status", response_model=schemas.SubscriptionOut)
def get_subscription_status(
    current_user: User = Depends(get_current_user)
):
    """Get current user's subscription status"""
    
    # Calculate days remaining if active
    days_remaining = None
    if current_user.subscription_end_date and current_user.subscription_status == SubscriptionStatus.ACTIVE:
        days_remaining = (current_user.subscription_end_date - datetime.utcnow()).days
    
    return {
        "subscription_status": current_user.subscription_status,
        "subscription_plan": current_user.subscription_plan,
        "subscription_end_date": current_user.subscription_end_date,
        "days_remaining": days_remaining
    }

@router.post("/cancel-subscription")
def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel user's subscription (at end of billing period)"""
    
    if not current_user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription found")
    
    if current_user.subscription_status != SubscriptionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Subscription is not active")
    
    try:
        # Cancel at period end (user keeps access until end of billing period)
        subscription = stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        return {
            "message": "Subscription will be cancelled at the end of the billing period",
            "cancels_at": subscription.cancel_at,
            "access_until": current_user.subscription_end_date
        }
    except stripe.error.StripeError as e:
        logger.error(f"Failed to cancel subscription: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reactivate-subscription")
def reactivate_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reactivate a cancelled subscription"""
    
    if not current_user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No subscription found")
    
    try:
        # Remove cancellation
        subscription = stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=False
        )
        
        current_user.subscription_status = SubscriptionStatus.ACTIVE
        db.commit()
        
        return {
            "message": "Subscription reactivated successfully",
            "status": current_user.subscription_status
        }
    except stripe.error.StripeError as e:
        logger.error(f"Failed to reactivate subscription: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/payment-history")
def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's payment history"""
    payments = db.query(Payment).filter(
        Payment.user_id == current_user.id
    ).order_by(Payment.created_at.desc()).all()
    
    return {
        "payments": [
            {
                "id": p.id,
                "amount": p.amount / 100,  # Convert cents to dollars
                "currency": p.currency.upper(),
                "status": p.status,
                "plan_type": p.plan_type,
                "created_at": p.created_at
            }
            for p in payments
        ],
        "total_spent": sum(p.amount for p in payments if p.status == 'succeeded') / 100
    }

@router.post("/change-plan")
def change_plan(
    new_plan: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upgrade or downgrade subscription plan"""
    
    if new_plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan type")
    
    if not current_user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription")
    
    if current_user.subscription_plan == new_plan:
        raise HTTPException(status_code=400, detail="Already on this plan")
    
    try:
        # Get current subscription
        subscription = stripe.Subscription.retrieve(current_user.stripe_subscription_id)
        
        # Update the subscription
        interval = "month" if new_plan == "monthly" else "year"
        
        stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            items=[{
                'id': subscription['items']['data'][0].id,
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Quran App - {new_plan.capitalize()} Premium',
                    },
                    'unit_amount': PLANS[new_plan],
                    'recurring': {
                        'interval': interval,
                    },
                },
            }],
            proration_behavior='always_invoice',  # Prorate immediately
        )
        
        current_user.subscription_plan = new_plan
        db.commit()
        
        return {
            "message": f"Plan changed to {new_plan} successfully",
            "new_plan": new_plan,
            "amount": PLANS[new_plan] / 100
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Failed to change plan: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/success")
def payment_success(session_id: str):
    return {
        "message": "Payment successful",
        "session_id": session_id,
        "note": "Subscription will be activated via webhook."
    }


@router.get("/cancel")
def payment_cancel():
    return {
        "message": "Payment cancelled"
    }