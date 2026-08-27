import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.billing_model import Subscription, CreditBalance, Invoice, PaymentEvent
from app.services.payment_service import get_payment_provider, PaymentNotConfigured
from sqlalchemy.exc import IntegrityError
from app.utils.logger import log_event

billing_bp = Blueprint("billing_bp", __name__)

PLAN_CREDITS = {"Free": 100, "Pro": 2000, "Enterprise": 50000}


def _get_or_create_balance(user_id):
    balance = CreditBalance.query.filter_by(user_id=user_id).first()
    if not balance:
        balance = CreditBalance(user_id=user_id, credits=100)
        db.session.add(balance)
        db.session.commit()
    return balance


@billing_bp.route("/billing/subscription", methods=["GET"])
@jwt_required()
def get_subscription():
    try:
        user_id = str(get_jwt_identity())
        sub = Subscription.query.filter_by(user_id=user_id).first()
        if not sub:
            sub = Subscription(user_id=user_id, plan_name="Free", status="active")
            db.session.add(sub)
            db.session.commit()
        return jsonify({"subscription": sub.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/billing/subscription", methods=["POST"])
@jwt_required()
def assign_subscription():
    # Plan changes must originate from a verified payment webhook or an
    # authorized admin workflow. Letting customers call this route directly
    # would allow free privilege/quota escalation.
    return jsonify({
        "error": "Subscription changes require the configured billing provider."
    }), 501


@billing_bp.route("/billing/credits", methods=["GET"])
@jwt_required()
def get_credits():
    try:
        user_id = str(get_jwt_identity())
        balance = _get_or_create_balance(user_id)
        return jsonify({"user_id": user_id, "credits": balance.credits}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/billing/credits/deduct", methods=["POST"])
@jwt_required()
def deduct_credits():
    return jsonify({
        "error": "Credit deductions are server-authoritative and cannot be submitted by clients."
    }), 403


@billing_bp.route("/billing/invoices", methods=["GET"])
@jwt_required()
def list_invoices():
    try:
        user_id = str(get_jwt_identity())
        invoices = Invoice.query.filter_by(user_id=user_id).order_by(Invoice.created_at.desc()).all()
        return jsonify({"invoices": [i.to_dict() for i in invoices]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/billing/invoices", methods=["POST"])
@jwt_required()
def generate_invoice():
    # Invoices are financial records and may only be created from verified
    # payment events; accepting a browser-supplied amount creates fake bills.
    return jsonify({
        "error": "Invoice creation requires the configured billing provider."
    }), 501


@billing_bp.route("/billing/config", methods=["GET"])
@jwt_required()
def billing_config():
    configured = bool(
        current_app.config.get("PAYMENT_PROVIDER") == "stripe"
        and current_app.config.get("STRIPE_SECRET_KEY")
        and current_app.config.get("STRIPE_WEBHOOK_SECRET")
    )
    return jsonify({
        "provider": "stripe" if configured else "Not configured",
        "checkout_available": configured,
        "plans": [name for name in ("Pro", "Enterprise") if current_app.config.get(f"STRIPE_PRICE_{name.upper()}")],
    }), 200


@billing_bp.route("/billing/checkout", methods=["POST"])
@jwt_required()
def create_checkout():
    plan = str((request.get_json(silent=True) or {}).get("plan") or "")
    if plan not in {"Pro", "Enterprise"}:
        return jsonify({"error": "Unknown plan."}), 400
    try:
        checkout = get_payment_provider().create_checkout(str(get_jwt_identity()), plan)
        return jsonify(checkout), 201
    except PaymentNotConfigured as error:
        return jsonify({"error": str(error)}), 503
    except Exception:
        current_app.logger.exception("Payment checkout creation failed.")
        return jsonify({"error": "Payment checkout could not be created."}), 502


@billing_bp.route("/billing/subscription/cancel", methods=["POST"])
@jwt_required()
def cancel_subscription():
    user_id = str(get_jwt_identity())
    subscription = Subscription.query.filter_by(user_id=user_id).first()
    if not subscription or not subscription.provider_subscription_id:
        return jsonify({"error": "No cancellable provider subscription exists."}), 404
    try:
        result = get_payment_provider().cancel_subscription(subscription.provider_subscription_id)
    except PaymentNotConfigured as error:
        return jsonify({"error": str(error)}), 503
    except Exception:
        current_app.logger.exception("Subscription cancellation failed.")
        return jsonify({"error": "Subscription cancellation failed."}), 502
    subscription.status = str(result.get("status") or "cancellation_pending")
    db.session.commit()
    log_event(current_app, "BILLING_CANCEL", subscription.provider_subscription_id, user_id)
    return jsonify({"subscription": subscription.to_dict()}), 200


@billing_bp.route("/billing/invoices/<int:invoice_id>/refund", methods=["POST"])
@jwt_required()
def refund_invoice(invoice_id):
    user_id = str(get_jwt_identity())
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=user_id).first()
    if not invoice:
        return jsonify({"error": "Invoice not found."}), 404
    if invoice.status == "refunded":
        return jsonify({"invoice": invoice.to_dict(), "status": "already_refunded"}), 200
    if invoice.status != "paid" or not invoice.provider_payment_id:
        return jsonify({"error": "Invoice is not refundable."}), 409
    try:
        result = get_payment_provider().refund_payment(
            invoice.provider_payment_id, f"invoice-refund-{invoice.id}"
        )
    except PaymentNotConfigured as error:
        return jsonify({"error": str(error)}), 503
    except Exception:
        current_app.logger.exception("Payment refund failed.")
        return jsonify({"error": "Payment refund failed."}), 502
    invoice.status = "refunded" if result.get("status") in {"succeeded", "pending"} else "refund_pending"
    db.session.commit()
    log_event(current_app, "BILLING_REFUND", invoice.invoice_uid, user_id)
    return jsonify({"invoice": invoice.to_dict()}), 200


@billing_bp.route("/billing/webhook", methods=["POST"])
def payment_webhook():
    try:
        event = get_payment_provider().verify_webhook(
            request.get_data(cache=True), request.headers.get("Stripe-Signature", "")
        )
    except PaymentNotConfigured as error:
        return jsonify({"error": str(error)}), 503
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid payment webhook."}), 400

    if PaymentEvent.query.filter_by(event_id=event["id"]).first():
        return jsonify({"status": "already_processed"}), 200
    event_type = event["type"]
    payment_object = ((event.get("data") or {}).get("object") or {})
    metadata = payment_object.get("metadata") or {}
    user_id, plan = str(metadata.get("user_id") or ""), str(metadata.get("plan") or "")
    if event_type == "checkout.session.completed" and payment_object.get("payment_status") == "paid":
        if not user_id or plan not in PLAN_CREDITS:
            return jsonify({"error": "Payment metadata is invalid."}), 422
        subscription = Subscription.query.filter_by(user_id=user_id).first() or Subscription(user_id=user_id)
        subscription.plan_name, subscription.status = plan, "active"
        subscription.provider_subscription_id = payment_object.get("subscription") or subscription.provider_subscription_id
        db.session.add(subscription)
        balance = CreditBalance.query.filter_by(user_id=user_id).first() or CreditBalance(user_id=user_id)
        balance.credits = PLAN_CREDITS[plan]
        db.session.add(balance)
    elif event_type == "invoice.paid" and user_id:
        invoice_id = str(payment_object.get("id") or "")
        if invoice_id and not Invoice.query.filter_by(invoice_uid=invoice_id).first():
            db.session.add(Invoice(
                invoice_uid=invoice_id, user_id=user_id,
                amount=float(payment_object.get("amount_paid") or 0) / 100,
                currency=str(payment_object.get("currency") or "usd").upper(), status="paid",
                provider_payment_id=payment_object.get("payment_intent"),
            ))
    elif event_type == "customer.subscription.deleted" and user_id:
        subscription = Subscription.query.filter_by(user_id=user_id).first()
        if subscription:
            subscription.status = "cancelled"
            balance = CreditBalance.query.filter_by(user_id=user_id).first()
            if balance:
                balance.credits = min(balance.credits, PLAN_CREDITS["Free"])
    elif event_type in {"charge.refunded", "refund.updated"}:
        payment_id = str(payment_object.get("payment_intent") or payment_object.get("id") or "")
        invoice = Invoice.query.filter_by(provider_payment_id=payment_id).first() if payment_id else None
        if invoice:
            invoice.status = "refunded"
    db.session.add(PaymentEvent(provider="stripe", event_id=event["id"], event_type=event_type))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"status": "already_processed"}), 200
    return jsonify({"status": "processed"}), 200
