if (!sessionStorage.getItem("access_token")) window.location.replace("/login.html");

function authHeaders() {
  const token = sessionStorage.getItem("access_token");
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, { ...options, headers: { ...authHeaders(), ...(options.headers || {}) } }); }
  catch (_) { throw new Error("Network request failed."); }
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("user");
    window.location.replace("/login.html");
    throw new Error("Session expired.");
  }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

async function loadModels() {
  const data = await api("/api/ai-studio/models");
  const items = (data.models || []).map((model) => {
    const item = document.createElement("li");
    item.textContent = `${model.model_id} — ${model.name} (${model.status})`;
    return item;
  });
  const list = document.getElementById("model-list");
  list.replaceChildren(...items);
  if (!items.length) list.textContent = "No custom models.";
}

async function runPrompt() {
  const button = document.getElementById("run-prompt-btn");
  if (button.disabled) return;
  const prompt = document.getElementById("playground-prompt").value.trim();
  if (!prompt) return;
  button.disabled = true;
  const output = document.getElementById("playground-output");
  output.textContent = "Running…";
  try {
    const data = await api("/api/ai-studio/playground/test", {
      method: "POST",
      body: JSON.stringify({
        model_id: "default",
        prompt,
        parameters: {}
      })
    });
    output.textContent = `${data.output}\n\nUsage: ${typeof data.usage === "string" ? data.usage : JSON.stringify(data.usage)}`;
  } catch (error) {
    output.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

document.getElementById("run-prompt-btn").addEventListener("click", runPrompt);
loadModels().catch((error) => { document.getElementById("model-list").textContent = error.message; });
