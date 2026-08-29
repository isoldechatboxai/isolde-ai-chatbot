const token = localStorage.getItem("access_token");
if (!token) window.location.replace("/login.html");
const headers = {Authorization: `Bearer ${token || ""}`, "Content-Type": "application/json"};
const message = document.getElementById("org-message");
const select = document.getElementById("org-select");
let currentOrg;
let currentUserId;
const supportedProviders = ["gemini", "groq", "openai", "claude", "openrouter", "deepseek", "mistral"];

async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, {...options, headers: {...headers, ...(options.headers || {})}}); }
  catch (_) { throw new Error("Network request failed."); }
  if (response.status === 401) { localStorage.removeItem("access_token"); location.href = "/login.html"; throw new Error("Session expired."); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

async function loadOrganizations() {
  const [data, profile] = await Promise.all([
    api("/api/organizations"),
    api("/api/profile"),
  ]);
  currentUserId = String(profile.data?.id || "");
  select.replaceChildren();
  for (const org of data.organizations) {
    const option = document.createElement("option"); option.value = org.id; option.textContent = org.name; select.append(option);
  }
  const active = data.organizations.find(org => org.status === "Active");
  if (!active) { message.textContent = data.organizations.length ? "No active organizations available." : "No organizations available."; return; }
  select.value = String(active.id);
  await loadOrganization(active);
}

async function loadOrganization(org) {
  currentOrg = org; message.textContent = "";
  const [members, roles, projects, policyData] = await Promise.all([
    api(`/api/organizations/${org.id}/members`), api(`/api/organizations/${org.id}/roles`),
    api(`/api/organizations/${org.id}/projects`), api(`/api/organizations/${org.id}/policy`),
  ]);
  const controls = document.getElementById("member-controls");
  controls.hidden = String(org.owner_id) !== currentUserId;
  const list = document.getElementById("member-list"); list.replaceChildren();
  for (const member of members.members) {
    const row = document.createElement("p"); row.append(document.createTextNode(`${member.name || member.email} — ${member.role?.name || "No role"} — ${member.status} `));
    if (!controls.hidden && member.user_id !== org.owner_id) {
      const status = document.createElement("select");
      for (const value of ["Active", "Suspended"]) { const option = document.createElement("option"); option.value = value; option.textContent = value; option.selected = value === member.status; status.append(option); }
      status.addEventListener("change", async () => { try { await api(`/api/organizations/${org.id}/members/${member.id}`, {method: "PATCH", body: JSON.stringify({status: status.value})}); await loadOrganization(org); } catch (error) { message.textContent = error.message; } });
      const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "Remove";
      remove.addEventListener("click", async () => { if (!window.confirm("Remove this organization member?")) return; try { await api(`/api/organizations/${org.id}/members/${member.id}`, {method: "DELETE"}); await loadOrganization(org); } catch (error) { message.textContent = error.message; } });
      row.append(status, remove);
    }
    list.append(row);
  }
  const roleSelect = document.getElementById("member-role"); roleSelect.replaceChildren();
  for (const role of roles.roles) { const option = document.createElement("option"); option.value = role.id; option.textContent = role.name; roleSelect.append(option); }
  const projectList = document.getElementById("shared-projects"); projectList.replaceChildren();
  for (const project of projects.projects) { const row = document.createElement("p"); row.textContent = `${project.name} — ${project.shared_access}`; projectList.append(row); }
  if (!projects.projects.length) projectList.textContent = "No shared projects.";
  if (!controls.hidden) {
    const usage = await api(`/api/organizations/${org.id}/usage`);
    document.getElementById("tenant-usage").textContent = `${usage.usage}; member account total: ${usage.account_tokens_used} tokens (not tenant-attributed)`;
    document.getElementById("policy-providers").value = (policyData.policy.allowed_providers?.length ? policyData.policy.allowed_providers : supportedProviders).join(", ");
    document.getElementById("policy-billing").checked = policyData.policy.billing_enabled;
  }
}

select.addEventListener("change", async () => {
  const orgs = await api("/api/organizations"); await loadOrganization(orgs.organizations.find(org => String(org.id) === select.value));
});
document.getElementById("member-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await api(`/api/organizations/${currentOrg.id}/members`, {method: "POST", body: JSON.stringify({email: document.getElementById("member-email").value, role_id: Number(document.getElementById("member-role").value)})});
    await loadOrganization(currentOrg); message.textContent = "Member added.";
  } catch (error) { message.textContent = error.message; }
});
document.getElementById("project-share-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const projectId = Number(document.getElementById("project-share-id").value);
    const access_level = document.getElementById("project-share-access").value;
    await api(`/api/organizations/${currentOrg.id}/projects/${projectId}`, {method: "POST", body: JSON.stringify({access_level})});
    await loadOrganization(currentOrg); message.textContent = "Project shared.";
  } catch (error) { message.textContent = error.message; }
});
document.getElementById("policy-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const allowed_providers = document.getElementById("policy-providers").value.split(",").map(value => value.trim()).filter(Boolean);
    const billing_enabled = document.getElementById("policy-billing").checked;
    await api(`/api/organizations/${currentOrg.id}/policy`, {method: "PATCH", body: JSON.stringify({allowed_providers, billing_enabled})});
    message.textContent = "Tenant policy saved.";
  } catch (error) { message.textContent = error.message; }
});
loadOrganizations().catch(error => { message.textContent = error.message; });
