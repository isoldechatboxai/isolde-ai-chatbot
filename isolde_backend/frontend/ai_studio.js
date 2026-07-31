function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("access_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function loadModels() {
  const res = await fetch("/api/ai-studio/models", { headers: authHeaders() });
  const data = await res.json();
  const list = document.getElementById("model-list");
  list.innerHTML = "";
  (data.models || []).forEach(m => {
    const li = document.createElement("li");
    li.textContent = `${m.model_id} — ${m.name} (${m.status})`;
    list.appendChild(li);
  });
}

async function createModel() {
  const model_name = document.getElementById("model-name").value;
  const base_model = document.getElementById("base-model").value;
  const dataset_uri = document.getElementById("dataset-uri").value;

  const res = await fetch("/api/ai-studio/models", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ model_name, base_model, dataset_uri })
  });
  const data = await res.json();
  alert(data.message || "Model created");
  loadModels();
}

async function runPrompt() {
  const model_id = document.getElementById("playground-model-id").value || "default";
  const prompt = document.getElementById("playground-prompt").value;

  const res = await fetch("/api/ai-studio/playground/test", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ model_id, prompt, parameters: { temperature: 0.7 } })
  });
  const data = await res.json();
  document.getElementById("playground-output").textContent = JSON.stringify(data, null, 2);
}

document.getElementById("create-model-btn").addEventListener("click", createModel);
document.getElementById("run-prompt-btn").addEventListener("click", runPrompt);

loadModels();