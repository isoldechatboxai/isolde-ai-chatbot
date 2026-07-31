import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.billing_model import Subscription, CreditBalance, Invoice

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
@jwt_required(optional=True)
def get_subscription():
    try:
        user_id = str(get_jwt_identity() or "1")
        sub = Subscription.query.filter_by(user_id=user_id).first()
        if not sub:
            sub = Subscription(user_id=user_id, plan_name="Free", status="active")
            db.session.add(sub)
            db.session.commit()
        return jsonify({"subscription": sub.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/billing/subscription", methods=["POST"])
@jwt_required(optional=True)
def assign_subscription():
    try:
        user_id = str(get_jwt_identity() or "1")
        data = request.get_json() or {}
        plan_name = data.get("plan_name", "Free")

        sub = Subscription.query.filter_by(user_id=user_id).first()
        if not sub:
            sub = Subscription(user_id=user_id, plan_name=plan_name, status="active")
            db.session.add(sub)
        else:
            sub.plan_name = plan_name
            sub.status = "active"

        balance = _get_or_create_balance(user_id)
        balance.credits = PLAN_CREDITS.get(plan_name, balance.credits)

        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"Successfully subscribed to {plan_name}.",
            "subscription": sub.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/billing/credits", methods=["GET"])
@jwt_required(optional=True)
def get_credits():
    try:
        user_id = str(get_jwt_identity() or "1")
        balance = _get_or_create_balance(user_id)
        return jsonify({"user_id": user_id, "credits": balance.credits}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/billing/credits/deduct", methods=["POST"])
@jwt_required(optional=True)
def deduct_credits():
    try:
        user_id = str(get_jwt_identity() or "1")
        data = request.get_json() or {}
        amount = int(data.get("amount", 0))

        balance = _get_or_create_balance(user_id)
        if balance.credits < amount:
            return jsonify({"error": "Insufficient credits", "available": balance.credits}), 400

        balance.credits -= amount
        db.session.commit()
        return jsonify({"status": "success", "remaining_credits": balance.credits}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/billing/invoices", methods=["GET"])
@jwt_required(optional=True)
def list_invoices():
    try:
        user_id = str(get_jwt_identity() or "1")
        invoices = Invoice.query.filter_by(user_id=user_id).order_by(Invoice.created_at.desc()).all()
        return jsonify({"invoices": [i.to_dict() for i in invoices]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/billing/invoices", methods=["POST"])
@jwt_required(optional=True)
def generate_invoice():
    try:
        user_id = str(get_jwt_identity() or "1")
        data = request.get_json() or {}
        amount = float(data.get("amount", 0.0))
        currency = data.get("currency", "USD")

        invoice = Invoice(
            invoice_uid=f"INV-{user_id[:8]}-{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            amount=amount,
            currency=currency,
            status="generated"
        )
        db.session.add(invoice)
        db.session.commit()
        return jsonify({"status": "generated", "invoice": invoice.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500