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
    try:
        user_id = str(get_jwt_identity())
        data = request.get_json() or {}
        amount = int(data.get("amount", 0))
        if amount <= 0:
            return jsonify({"error": "Amount must be a positive integer."}), 400

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
