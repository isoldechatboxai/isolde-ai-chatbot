function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("access_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function api(url, options = {}) {
  let response;
  try { response = await fetch(url, {...options, headers: {...authHeaders(), ...(options.headers || {})}}); }
  catch (_) { throw new Error("Network request failed."); }
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    localStorage.removeItem("access_token");
    window.location.replace("/login.html");
    throw new Error("Session expired.");
  }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

async function loadPlugins() {
  const category = document.getElementById("category-filter").value;
  const url = category === "All" ? "/api/marketplace/plugins" : `/api/marketplace/plugins?category=${encodeURIComponent(category)}`;
  const data = await api(url);
  const grid = document.getElementById("plugin-grid");
  grid.innerHTML = "";
  (data.plugins || []).forEach(p => {
    const card = document.createElement("div");
    card.style.cssText = "border:1px solid var(--border-color,#333);border-radius:10px;padding:12px;";
    const heading = document.createElement("h3"); heading.textContent = p.name;
    const description = document.createElement("p"); description.textContent = p.description || "";
    const version = document.createElement("p"); version.textContent = `v${p.version} · ${p.category}`;
    const rating = document.createElement("p"); rating.textContent = `${p.downloads_count} downloads · ★ ${p.rating_avg}`;
    const button = document.createElement("button"); button.type = "button"; button.dataset.id = String(p.id); button.className = "install-btn"; button.textContent = "Install";
    card.append(heading, description, version, rating, button);
    grid.appendChild(card);
  });
  document.querySelectorAll(".install-btn").forEach(btn => {
    btn.addEventListener("click", () => installPlugin(btn.dataset.id));
  });
}

async function installPlugin(pluginId) {
  try {
    const data = await api(`/api/marketplace/install/${pluginId}`, {method: "POST"});
    alert(data.message || "Plugin installed.");
    await loadInstalled();
  } catch (error) { alert(error.message); }
}

async function loadInstalled() {
  const data = await api("/api/marketplace/installed");
  const list = document.getElementById("installed-list");
  list.innerHTML = "";
  (data.installed_plugins || []).forEach(p => {
    const li = document.createElement("li");
    li.textContent = `${p.name} (v${p.version})`;
    list.appendChild(li);
  });
}

document.getElementById("refresh-btn").addEventListener("click", loadPlugins);
document.getElementById("category-filter").addEventListener("change", loadPlugins);

loadPlugins().catch(error => { document.getElementById("plugin-grid").textContent = error.message; });
loadInstalled().catch(error => { document.getElementById("installed-list").textContent = error.message; });
