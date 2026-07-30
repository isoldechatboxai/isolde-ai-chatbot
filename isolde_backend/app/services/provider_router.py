"""
Universal AI Wrapper: Supports Gemini, OpenAI, Anthropic (Claude), and Groq.
Auto-detects the provider based on the API Key format.
Zero-bug version: Fully compatible with standard {"role": "user", "content": "..."} history format.
"""
import requests
from google import genai
from google.genai import types
from flask import current_app
from app.models.user import Setting
from app.models.workspace_model import Agent, Workspace, Project, WorkspaceDocument

def _get_api_key() -> str:
    db_key_setting = Setting.query.filter_by(key="gemini_api_key").first()
    api_key = db_key_setting.value if db_key_setting and db_key_setting.value else None
    
    if not api_key:
        api_key = current_app.config.get("GEMINI_API_KEY")
        
    if not api_key:
        raise RuntimeError("API_KEY is not set. Add it in Admin Panel or .env file.")
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


# ==========================================
# 🌟 WORKSPACE & AGENT CONTEXT BUILDER
# ==========================================
def _build_agent_workspace_context(
    agent_id: int = None,
    workspace_id: int = None,
    project_id: int = None,
) -> str:
    """
    Builds an additional context block (agent persona + workspace knowledge + project scope).
    """
    context_blocks = []

    # --- Agent persona ---
    if agent_id:
        try:
            agent = Agent.query.get(agent_id)
            if agent and agent.is_active:
                agent_block = f"ACTIVE AGENT PERSONA ({agent.name}):\n{agent.system_prompt}"
                if agent.role_description:
                    agent_block += f"\nRole: {agent.role_description}"
                context_blocks.append(agent_block)
        except Exception as e:
            print(f"⚠️ Agent context skipped (non-fatal): {e}")

    # --- Workspace-level shared knowledge ---
    if workspace_id:
        try:
            workspace = Workspace.query.get(workspace_id)
            if workspace:
                docs = WorkspaceDocument.query.filter_by(
                    workspace_id=workspace_id, project_id=None
                ).limit(5).all()
                doc_snippets = [
                    d.extracted_text[:1500] for d in docs if d.extracted_text
                ]
                if doc_snippets:
                    context_blocks.append(
                        f"WORKSPACE KNOWLEDGE ({workspace.name}):\n" + "\n---\n".join(doc_snippets)
                    )
        except Exception as e:
            print(f"⚠️ Workspace context skipped (non-fatal): {e}")

    # --- Project-level scoped knowledge ---
    if project_id:
        try:
            project = Project.query.get(project_id)
            if project:
                proj_docs = WorkspaceDocument.query.filter_by(project_id=project_id).limit(5).all()
                proj_snippets = [
                    d.extracted_text[:1500] for d in proj_docs if d.extracted_text
                ]
                proj_block = f"ACTIVE PROJECT ({project.name})"
                if project.description:
                    proj_block += f": {project.description}"
                if proj_snippets:
                    proj_block += "\nProject documents:\n" + "\n---\n".join(proj_snippets)
                context_blocks.append(proj_block)
        except Exception as e:
            print(f"⚠️ Project context skipped (non-fatal): {e}")

    return "\n\n".join(context_blocks)


def _to_content_history(history):
    if not history:
        return []
    contents = []
    for turn in history:
        role = turn.get("role", "user")
        # FIX: Added support for 'content' format to prevent bugs with MemoryService
        text = turn.get("content")
        if not text:
            parts = turn.get("parts", [])
            text = parts[0] if parts else ""
        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return contents


# ==========================================
# 🌟 MAIN GENERATOR: UNIVERSAL AUTO-DETECT
# ==========================================
def generate_reply(
    prompt: str,
    history=None,
    system_context: str = "",
    agent_id: int = None,
    workspace_id: int = None,
    project_id: int = None,
) -> str:
    """
    Main entry point for generating AI replies. Routes to the correct provider.
    """
    api_key = _get_api_key()

    phase4_context = _build_agent_workspace_context(agent_id, workspace_id, project_id)
    combined_context = system_context or ""
    if phase4_context:
        combined_context = f"{combined_context}\n\n{phase4_context}".strip()

    sys_prompt = _get_system_instruction(combined_context)

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
            # FIX: Get content properly
            text = turn.get("content")
            if not text:
                parts = turn.get("parts", [])
                text = parts[0] if parts else ""
            messages.append({"role": role, "content": text})
            
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile",
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
            # FIX: Get content properly
            text = turn.get("content")
            if not text:
                parts = turn.get("parts", [])
                text = parts[0] if parts else ""
            messages.append({"role": role, "content": text})
            
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
def _call_claude(api_key, prompt, history, sys_prompt):
    messages = []
    if history:
        for turn in history:
            role = "user" if turn.get("role") == "user" else "assistant"
            # FIX: Get content properly
            text = turn.get("content")
            if not text:
                parts = turn.get("parts", [])
                text = parts[0] if parts else ""
            messages.append({"role": role, "content": text})
            
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
    
    if api_key.startswith("sk-") and not api_key.startswith("sk-ant"):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"model": "text-embedding-3-small", "input": text}
        resp = requests.post("https://api.openai.com/v1/embeddings", headers=headers, json=data)
        if resp.status_code == 200:
            return resp.json()["data"][0]["embedding"]
        else:
            raise RuntimeError(f"OpenAI Embedding Error: {resp.text}")
            
    elif api_key.startswith("gsk_") or api_key.startswith("sk-ant"):
        raise RuntimeError("Embeddings are currently supported natively for Google Gemini and OpenAI. Please configure a valid API key for embeddings.")
        
    else:
        # Default fallback to Gemini
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