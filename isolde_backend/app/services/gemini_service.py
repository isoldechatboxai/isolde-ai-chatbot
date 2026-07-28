"""
Universal AI Wrapper: Supports Gemini, OpenAI, Anthropic (Claude), and Groq.
Auto-detects the provider based on the API Key format.
"""
import requests
from google import genai
from google.genai import types
from flask import current_app
from app.models.user import Setting

def _get_api_key() -> str:
    db_key_setting = Setting.query.filter_by(key="gemini_api_key").first()
    api_key = db_key_setting.value if db_key_setting and db_key_setting.value else None
    
    if not api_key:
        api_key = current_app.config.get("GEMINI_API_KEY")
        
    if not api_key:
        raise RuntimeError("API_KEY is not set. Add it in Admin Panel.")
    return api_key.strip()

def _get_system_instruction(system_context: str) -> str:
    db_prompt_setting = Setting.query.filter_by(key="system_prompt").first()
    base = db_prompt_setting.value if db_prompt_setting and db_prompt_setting.value else (
        "You are Isolde, a helpful, honest AI assistant. "
        "If context is provided below, ground your answer in it."
    )
    if system_context:
        return f"{base}\n\n{system_context}"
    return base

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


# ==========================================
# 🌟 MAIN GENERATOR: UNIVERSAL AUTO-DETECT
# ==========================================
def generate_reply(prompt: str, history=None, system_context: str = "") -> str:
    api_key = _get_api_key()
    sys_prompt = _get_system_instruction(system_context)

    # 1. GROQ DETECTION (Keys start with 'gsk_') - 100% Free & Fast
    if api_key.startswith("gsk_"):
        print("🤖 Auto-detected: GROQ (Llama / Mistral)")
        return _call_groq(api_key, prompt, history, sys_prompt)

    # 2. CLAUDE DETECTION (Keys start with 'sk-ant')
    elif api_key.startswith("sk-ant"):
        print("🤖 Auto-detected: CLAUDE (Anthropic)")
        return _call_claude(api_key, prompt, history, sys_prompt)
    
    # 3. OPENAI / CHATGPT DETECTION (Keys start with 'sk-')
    elif api_key.startswith("sk-"):
        print("🤖 Auto-detected: CHATGPT (OpenAI)")
        return _call_openai(api_key, prompt, history, sys_prompt)
    
    # 4. GEMINI DETECTION (Default / Google)
    else:
        print("🤖 Auto-detected: GOOGLE GEMINI")
        return _call_gemini(api_key, prompt, history, sys_prompt)


# --- GEMINI IMPLEMENTATION ---
def _call_gemini(api_key, prompt, history, sys_prompt):
    client = genai.Client(api_key=api_key)
    db_model_setting = Setting.query.filter_by(key="gemini_model").first()
    model_name = db_model_setting.value if db_model_setting and db_model_setting.value else "gemini-2.0-flash"
    
    chat = client.chats.create(
        model=model_name,
        history=_to_content_history(history),
        config=types.GenerateContentConfig(system_instruction=sys_prompt),
    )
    response = chat.send_message(message=prompt)
    return (response.text or "").strip()

# --- GROQ IMPLEMENTATION (Free & Ultra Fast) ---
def _call_groq(api_key, prompt, history, sys_prompt):
    messages = [{"role": "system", "content": sys_prompt}]
    
    if history:
        for turn in history:
            role = "user" if turn.get("role") == "user" else "assistant"
            parts = turn.get("parts", [])
            messages.append({"role": role, "content": parts[0] if parts else ""})
            
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile", # You can also use "llama-3.1-8b-instant"
        "messages": messages
    }
    
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API Error: {resp.text}")
        
    return resp.json()["choices"][0]["message"]["content"].strip()

# --- OPENAI IMPLEMENTATION ---
def _call_openai(api_key, prompt, history, sys_prompt):
    messages = [{"role": "system", "content": sys_prompt}]
    
    if history:
        for turn in history:
            role = "user" if turn.get("role") == "user" else "assistant"
            parts = turn.get("parts", [])
            messages.append({"role": role, "content": parts[0] if parts else ""})
            
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o",
        "messages": messages
    }
    
    resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI Error: {resp.text}")
        
    return resp.json()["choices"][0]["message"]["content"].strip()

# --- CLAUDE IMPLEMENTATION ---
def _call_cla_ude(api_key, prompt, history, sys_prompt):
    messages = []
    if history:
        for turn in history:
            role = "user" if turn.get("role") == "user" else "assistant"
            parts = turn.get("parts", [])
            messages.append({"role": role, "content": parts[0] if parts else ""})
            
    messages.append({"role": "user", "content": prompt})

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": "claude-3-5-sonnet-20240620", 
        "system": sys_prompt,
        "messages": messages,
        "max_tokens": 1024
    }
    
    resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)
    if resp.status_code != 200:
        raise RuntimeError(f"Claude Error: {resp.text}")
        
    return resp.json()["content"][0]["text"].strip()


# ==========================================
# 🌟 EMBEDDINGS & VISION HELPERS
# ==========================================
def embed_text(text: str):
    api_key = _get_api_key()
    
    if api_key.startswith("sk-") or api_key.startswith("gsk_"):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"model": "text-embedding-3-small", "input": text}
        url = "https://api.openai.com/v1/embeddings" if api_key.startswith("sk-") else "https://api.groq.com/openai/v1/embeddings"
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code == 200:
            return resp.json()["data"][0]["embedding"]
            
    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(model="text-embedding-004", contents=text)
    return list(result.embeddings[0].values)


def analyze_image(image_bytes: bytes, mime_type: str, question: str) -> str:
    api_key = _get_api_key()
    client = genai.Client(api_key=api_key)
    db_model_setting = Setting.query.filter_by(key="gemini_model").first()
    model_name = db_model_setting.value if db_model_setting and db_model_setting.value else "gemini-2.0-flash"
    
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            question,
        ],
    )
    return (response.text or "").strip()