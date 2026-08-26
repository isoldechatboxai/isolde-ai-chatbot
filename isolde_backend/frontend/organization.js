const token = localStorage.getItem("access_token");
const headers = {Authorization: `Bearer ${token || ""}`, "Content-Type": "application/json"};
const message = document.getElementById("org-message");
const select = document.getElementById("org-select");
let currentOrg;

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {...headers, ...(options.headers || {})}});
  if (response.status === 401) { localStorage.removeItem("access_token"); location.href = "/login.html"; throw new Error("Session expired."); }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed.");
  return data;
}

async function loadOrganizations() {
  const data = await api("/api/organizations");
  select.replaceChildren();
  for (const org of data.organizations) {
    const option = document.createElement("option"); option.value = org.id; option.textContent = org.name; select.append(option);
  }
  if (!data.organizations.length) { message.textContent = "No organizations available."; return; }
  await loadOrganization(data.organizations[0]);
}

async function loadOrganization(org) {
  currentOrg = org; message.textContent = "";
  const [members, roles] = await Promise.all([api(`/api/organizations/${org.id}/members`), api(`/api/organizations/${org.id}/roles`)]);
  const list = document.getElementById("member-list"); list.replaceChildren();
  for (const member of members.members) {
    const row = document.createElement("p"); row.textContent = `${member.name || member.email} — ${member.role?.name || "No role"} — ${member.status}`; list.append(row);
  }
  const controls = document.getElementById("member-controls");
  const user = JSON.parse(localStorage.getItem("user") || "{}"); controls.hidden = org.owner_id !== user.id;
  const roleSelect = document.getElementById("member-role"); roleSelect.replaceChildren();
  for (const role of roles.roles) { const option = document.createElement("option"); option.value = role.id; option.textContent = role.name; roleSelect.append(option); }
  if (!controls.hidden) {
    const usage = await api(`/api/organizations/${org.id}/usage`);
    document.getElementById("tenant-usage").textContent = `${usage.tokens_used} recorded tokens; ${usage.usage}`;
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
loadOrganizations().catch(error => { message.textContent = error.message; });
