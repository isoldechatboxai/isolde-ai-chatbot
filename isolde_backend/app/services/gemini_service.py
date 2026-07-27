"""
Wrapper around Google's Gemini API using the current, supported
`google-genai` SDK. Keeps the API key server-side only.
"""
from google import genai
from google.genai import types
from flask import current_app
from app.models.user import Setting

def _get_client() -> genai.Client:
    # 1. First check Database settings
    db_key_setting = Setting.query.filter_by(key="gemini_api_key").first()
    api_key = db_key_setting.value if db_key_setting and db_key_setting.value else None
    
    # 2. Fallback to .env if not in DB
    if not api_key:
        api_key = current_app.config.get("GEMINI_API_KEY")
        
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it in Admin Panel or your .env file."
        )
    return genai.Client(api_key=api_key)


def _get_model_name() -> str:
    db_model_setting = Setting.query.filter_by(key="gemini_model").first()
    if db_model_setting and db_model_setting.value:
        return db_model_setting.value
    return "gemini-2.0-flash"


def _to_content_history(history):
    if not history:
        return []
    contents = []
    for turn in history:
        role = turn.get("role", "user")
        parts = turn.get("parts", [])
        text = parts[0] if parts else ""
        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return contents


def _system_instruction(system_context: str) -> str:
    base = (
        "You are Isolde, a helpful, honest AI assistant. "
        "If context is provided below, ground your answer in it. "
        "If you are not confident or the answer cannot be verified from "
        "context or general knowledge, say so plainly instead of guessing."
    )
    if system_context:
        return f"{base}\n\n{system_context}"
    return base


def generate_reply(prompt: str, history=None, system_context: str = "") -> str:
    client = _get_client()
    model_name = _get_model_name()
    
    print(f"Using Gemini model: {model_name}")

    chat = client.chats.create(
        model=model_name,
        history=_to_content_history(history),
        config=types.GenerateContentConfig(
            system_instruction=_system_instruction(system_context),
        ),
    )
    
    print("Sending Gemini request...")
    response = chat.send_message(message=prompt)
    print("Gemini response received!")
    
    return (response.text or "").strip()


def generate_reply_stream(prompt: str, history=None, system_context: str = ""):
    client = _get_client()
    model_name = _get_model_name()

    chat = client.chats.create(
        model=model_name,
        history=_to_content_history(history),
        config=types.GenerateContentConfig(
            system_instruction=_system_instruction(system_context),
        ),
    )
    for chunk in chat.send_message_stream(message=prompt):
        if chunk.text:
            yield chunk.text


def embed_text(text: str):
    client = _get_client()
    result = client.models.embed_content(
        model="text-embedding-004",
        contents=text,
    )
    return list(result.embeddings[0].values)


def analyze_image(image_bytes: bytes, mime_type: str, question: str) -> str:
    client = _get_client()
    model_name = _get_model_name()
    
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            question,
        ],
    )
    return (response.text or "").strip()