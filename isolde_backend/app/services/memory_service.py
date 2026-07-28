# app/services/memory_service.py
import re
from app import db
from app.models.memory_model import UserMemory

def extract_and_save_memories(user_id, user_text):
    text_lower = user_text.lower()
    
    # Simple pattern matching rules for extraction
    patterns = [
        (r"my name is ([a-zA-Z\s]+)", "Personal"),
        (r"i live in ([a-zA-Z\s]+)", "Location"),
        (r"i work as (?:a |an )?([a-zA-Z\s]+)", "Work"),
        (r"i prefer ([a-zA-Z\s]+)", "Preferences"),
        (r"my favorite ([a-zA-Z\s]+) is ([a-zA-Z\s]+)", "Preferences"),
        (r"i studied ([a-zA-Z\s]+)", "Education"),
        (r"i know ([a-zA-Z\s]+)", "Skills")
    ]

    for pattern, category in patterns:
        match = re.search(pattern, text_lower)
        if match:
            memory_text = match.group(0).capitalize()
            # Check if already exists
            exists = UserMemory.query.filter_by(user_id=user_id, memory=memory_text).first()
            if not exists:
                new_mem = UserMemory(user_id=user_id, memory=memory_text, category=category)
                db.session.add(new_mem)
                db.session.commit()

def build_memory_prompt(user_id):
    memories = UserMemory.query.filter_by(user_id=user_id).all()
    if not memories:
        return ""
    
    prompt_snippet = "\n\nUser Memories:\n"
    for mem in memories:
        prompt_snippet += f"- [{mem.category}] {mem.memory}\n"
    return prompt_snippet