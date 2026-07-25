"""
Self-correction pipeline: before answering, check whether a similar
question was previously marked incorrect and has a stored correction.
Difflib keeps this dependency-free; swap for embedding similarity if needed.
"""
from difflib import SequenceMatcher
from app.models import Feedback


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_relevant_corrections(question: str, threshold: float = 0.72, limit: int = 3):
    """Look up past user-flagged-incorrect answers similar to this question."""
    corrections = Feedback.query.filter_by(is_correct=False).all()
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
from difflib import SequenceMatcher
from app.models import Feedback
from app.extensions import db

class FeedbackService:
    @staticmethod
    def create_feedback(user_id, message_id, rating, comment=None):
        feedback = Feedback(
            user_id=user_id,
            message_id=message_id,
            rating=rating,
            comment=comment
        )
        db.session.add(feedback)
        db.session.commit()
        return feedback