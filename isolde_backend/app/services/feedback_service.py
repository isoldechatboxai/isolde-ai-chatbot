"""
Self-correction pipeline and feedback compatibility service.

Authoritative model usage:
- app.models.feedback.Feedback is the correction-feedback model.
- app.models.user.Feedback is the simple rating-feedback model.

This service intentionally imports both with aliases to avoid ambiguity
and to preserve existing behavior without duplicating models.
"""

from difflib import SequenceMatcher

from app.models.feedback import Feedback as CorrectionFeedback
from app.models.user import Feedback as RatingFeedback
from app.extensions import db


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_relevant_corrections(question: str, threshold: float = 0.72, limit: int = 3):
    """Look up past user-flagged-incorrect answers similar to this question."""
    corrections = CorrectionFeedback.query.filter_by(is_correct=False).all()
    scored = []

    for c in corrections:
        if not c.correction_text:
            continue

        score = _similarity(question, c.question)

        if score >= threshold:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [c for _, c in scored[:limit]]


def build_correction_context(corrections) -> str:
    if not corrections:
        return ""

    lines = ["Known corrections from previous user feedback (apply these if relevant):"]

    for c in corrections:
        lines.append(f"- Q: {c.question}\n  Correct answer: {c.correction_text}")

    return "\n".join(lines)


class FeedbackService:
    """
    Compatibility service layer for feedback persistence.

    Part 1 consistency fix:
    - use CorrectionFeedback for correction-based feedback
    - use RatingFeedback for simple rating feedback
    - do not rely on ambiguous app.models package-level Feedback resolution
    """

    @staticmethod
    def create_feedback(user_id, message_id, rating, comment=None):
        """
        Preserve the existing function signature.

        The existing simple rating-feedback model stores:
        - user_name
        - rating
        - comment

        It does not have message_id. To avoid a schema change, this method
        preserves the rating/comment contract and resolves a safe user_name.
        """
        user_name = "Guest"

        if user_id:
            user_name = f"user:{user_id}"

            try:
                from app.models.user import User

                user = db.session.get(User, user_id)

                if user:
                    user_name = user.name or user.email or user_name

            except Exception:
                db.session.rollback()

        feedback = RatingFeedback(
            user_name=user_name,
            rating=rating,
            comment=comment,
        )

        db.session.add(feedback)
        db.session.commit()

        return feedback