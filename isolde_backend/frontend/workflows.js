const workflowToken = sessionStorage.getItem("access_token");
if (!workflowToken) window.location.replace("/login.html");

const workflowMessage = document.getElementById("workflow-message");
const workflowList = document.getElementById("workflow-list");
const workspaceSelect = document.getElementById("workflow-workspace");

async function workflowApi(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  let response;
  try {
    response = await fetch(path, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${workflowToken}`,
        ...(options.headers || {}),
      },
    });
  } catch (error) {
    throw new Error(error.name === "AbortError" ? "Request timed out." : "Network request failed.");
  } finally {
    clearTimeout(timer);
  }
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

function renderWorkflows(workflows) {
  workflowList.replaceChildren(...workflows.map((workflow) => {
    const card = document.createElement("article");
    card.style.cssText = "border:1px solid var(--border-color,#333);border-radius:10px;padding:16px;margin:12px 0";
    const title = document.createElement("h3");
    title.textContent = workflow.name;
    const description = document.createElement("p");
    description.textContent = workflow.description || "No description.";
    const state = document.createElement("p");
    state.textContent = `Manual · ${workflow.is_active ? "Active" : "Inactive"} · Execution NOT_SUPPORTED`;
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.textContent = workflow.is_active ? "Deactivate" : "Activate";
    toggle.addEventListener("click", async () => {
      if (toggle.disabled) return;
      toggle.disabled = true;
      try {
        await workflowApi(`/api/workflows/${workflow.id}`, {
          method: "PUT", body: JSON.stringify({is_active: !workflow.is_active}),
        });
        await loadWorkflows();
      } catch (error) {
        workflowMessage.textContent = error.message;
        toggle.disabled = false;
      }
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Delete";
    remove.addEventListener("click", async () => {
      if (!window.confirm("Delete this workflow definition?")) return;
      remove.disabled = true;
      try {
        await workflowApi(`/api/workflows/${workflow.id}`, {method: "DELETE"});
        await loadWorkflows();
      } catch (error) {
        workflowMessage.textContent = error.message;
        remove.disabled = false;
      }
    });
    card.append(title, description, state, toggle, document.createTextNode(" "), remove);
    return card;
  }));
  document.getElementById("workflow-empty").hidden = workflows.length !== 0;
}

async function loadWorkflows({showLoading = true} = {}) {
  if (showLoading) workflowMessage.textContent = "Loading…";
  const data = await workflowApi("/api/workflows");
  renderWorkflows(data.workflows || []);
  if (showLoading) workflowMessage.textContent = "";
}

async function initializeWorkflows() {
  const workspaces = await workflowApi("/api/workspace/list");
  workspaceSelect.replaceChildren(...(workspaces.workspaces || []).map((workspace) => {
    const option = document.createElement("option");
    option.value = workspace.id;
    option.textContent = workspace.name;
    return option;
  }));
  const createButton = document.getElementById("workflow-create");
  if (!workspaceSelect.options.length) {
    createButton.disabled = true;
    workflowMessage.textContent = "Create a workspace before creating a workflow.";
    await loadWorkflows({showLoading: false});
    return;
  }
  await loadWorkflows();
}

document.getElementById("workflow-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = document.getElementById("workflow-create");
  if (button.disabled) return;
  button.disabled = true;
  workflowMessage.textContent = "Creating…";
  try {
    await workflowApi("/api/workflows", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: Number(workspaceSelect.value),
        name: document.getElementById("workflow-name").value.trim(),
        description: document.getElementById("workflow-description").value.trim(),
        trigger_type: "Manual",
      }),
    });
    event.currentTarget.reset();
    await loadWorkflows();
    workflowMessage.textContent = "Workflow created.";
  } catch (error) {
    workflowMessage.textContent = error.message;
  } finally {
    button.disabled = !workspaceSelect.options.length;
  }
});

initializeWorkflows().catch((error) => { workflowMessage.textContent = error.message; });
