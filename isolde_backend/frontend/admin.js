const tokenKey = "admin_access_token";

async function adminApi(path, options = {}) {
  const token = localStorage.getItem(tokenKey);
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers || {}) }
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 || response.status === 403) {
    localStorage.removeItem(tokenKey);
    document.getElementById("admin-dashboard").hidden = true;
    document.getElementById("admin-login").hidden = false;
  }
  if (!response.ok) throw new Error(data.message || data.error || "Admin request failed.");
  return data;
}

async function loadDashboard() {
  const [dashboard, users, tenants, providers, billing, subscriptions, operations, logs] = await Promise.all([
    adminApi("/api/admin/dashboard"), adminApi("/api/admin/users"), adminApi("/api/admin/tenants"),
    adminApi("/api/admin/provider-status"), adminApi("/api/admin/billing-summary"), adminApi("/api/admin/billing/subscriptions"),
    adminApi("/api/admin/operations"), adminApi("/api/admin/operations/log-summary")
  ]);
  document.getElementById("admin-login").hidden = true;
  document.getElementById("admin-dashboard").hidden = false;
  const stats = dashboard.dashboard || {};
  document.getElementById("admin-stats").replaceChildren(...Object.entries(stats).map(([key, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt"); term.textContent = key.replaceAll("_", " ");
    const detail = document.createElement("dd"); detail.textContent = String(value);
    row.append(term, detail); return row;
  }));
  const body = document.getElementById("admin-users");
  body.replaceChildren(...(users.users || []).map((user) => {
    const row = document.createElement("tr");
    [user.name, user.email, user.role, user.status].forEach((value) => { const cell = document.createElement("td"); cell.textContent = value || "—"; row.appendChild(cell); });
    return row;
  }));
  document.getElementById("admin-empty").hidden = (users.users || []).length !== 0;
  document.getElementById("admin-tenants").replaceChildren(...(tenants.tenants || []).map((tenant) => {
    const row = document.createElement("p"); row.append(document.createTextNode(`${tenant.name} — ${tenant.member_count} members — `));
    const status = document.createElement("select");
    for (const value of ["Active", "Suspended", "Archived"]) { const option = document.createElement("option"); option.value = value; option.textContent = value; option.selected = value === tenant.status; status.append(option); }
    status.addEventListener("change", () => adminApi(`/api/admin/tenants/${tenant.id}`, {method: "PATCH", body: JSON.stringify({status: status.value})}).catch(error => { document.getElementById("admin-message").textContent = error.message; }));
    row.append(status); return row;
  }));
  renderDefinitionList("admin-providers", providers.providers || {});
  renderDefinitionList("admin-billing", billing.billing || {});
  document.getElementById("admin-subscriptions").replaceChildren(...(subscriptions.subscriptions || []).map((subscription) => {
    const row = document.createElement("p"); row.append(document.createTextNode(`${subscription.user_id} — ${subscription.plan_name} — ${subscription.status} `));
    if (subscription.provider_managed && subscription.status === "active") {
      const button = document.createElement("button"); button.type = "button"; button.textContent = "Cancel subscription";
      button.addEventListener("click", async () => {
        if (!window.confirm("Cancel this provider subscription?")) return;
        try { await adminApi(`/api/admin/billing/subscriptions/${subscription.user_id}/cancel`, {method: "POST"}); await loadDashboard(); }
        catch (error) { document.getElementById("admin-message").textContent = error.message; }
      }); row.append(button);
    }
    return row;
  }));
  renderDefinitionList("admin-operations", {
    storage_backend: operations.operations?.storage_backend,
    rag_backend: operations.operations?.rag_backend,
    rate_limit_storage: operations.operations?.rate_limit_storage,
    logs: operations.operations?.logs,
    health: operations.operations?.health?.status,
  });
  renderDefinitionList("admin-log-summary", logs.summary || {});
}

function renderDefinitionList(id, values) {
  document.getElementById(id).replaceChildren(...Object.entries(values).map(([key, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt"); term.textContent = key.replaceAll("_", " ");
    const detail = document.createElement("dd"); detail.textContent = String(value ?? "Not configured");
    row.append(term, detail); return row;
  }));
}

document.getElementById("admin-login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  if (button.disabled) return;
  button.disabled = true;
  try {
    const data = await adminApi("/api/admin/login", { method: "POST", body: JSON.stringify({ email: document.getElementById("admin-email").value.trim(), password: document.getElementById("admin-password").value }) });
    localStorage.setItem(tokenKey, data.access_token);
    await loadDashboard();
  } catch (error) { document.getElementById("admin-message").textContent = error.message; }
  finally { button.disabled = false; }
});

document.getElementById("admin-logout").addEventListener("click", async () => {
  try { await adminApi("/api/logout", { method: "POST" }); } catch (_) {}
  localStorage.removeItem(tokenKey);
  window.location.reload();
});

if (localStorage.getItem(tokenKey)) loadDashboard().catch((error) => { document.getElementById("admin-message").textContent = error.message; });
