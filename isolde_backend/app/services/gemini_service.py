"""
Wrapper around Google's Gemini API using the current, supported
`google-genai` SDK (the older `google-generativeai` package and the
`gemini-1.5-*` model family it defaulted to have both been shut down).
Keeps the API key server-side only; the frontend never sees it.
"""
from google import genai
from google.genai import types
from flask import current_app

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = current_app.config.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your .env file."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _to_content_history(history):
    """Convert our stored {'role': 'user'/'model', 'parts': [text]} dicts
    into the google-genai SDK's typed Content objects."""
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
    """
    prompt: latest user message
    history: list of {"role": "user"/"model", "parts": [text]} for memory
    system_context: RAG-retrieved context / corrections to ground the answer
    """
    client = _get_client()
    model_name = current_app.config.get("GEMINI_MODEL", "gemini-flash-latest")

    chat = client.chats.create(
        model=model_name,
        history=_to_content_history(history),
        config=types.GenerateContentConfig(
            system_instruction=_system_instruction(system_context),
        ),
    )
    response = chat.send_message(message=prompt)
    return (response.text or "").strip()


def generate_reply_stream(prompt: str, history=None, system_context: str = ""):
    """Generator yielding response chunks for real-time streaming endpoints."""
    client = _get_client()
    model_name = current_app.config.get("GEMINI_MODEL", "gemini-flash-latest")

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
    """Generate an embedding vector for RAG semantic search."""
    client = _get_client()
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
    )
    return list(result.embeddings[0].values)


def analyze_image(image_bytes: bytes, mime_type: str, question: str) -> str:
    """Gemini Vision: answer a question about an uploaded image."""
    client = _get_client()
    model_name = current_app.config.get("GEMINI_MODEL", "gemini-flash-latest")

    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            question,
        ],
    )
    return (response.text or "").strip()
