function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("access_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function loadPlugins() {
  const category = document.getElementById("category-filter").value;
  const url = category === "All" ? "/api/marketplace/plugins" : `/api/marketplace/plugins?category=${encodeURIComponent(category)}`;
  const res = await fetch(url, { headers: authHeaders() });
  const data = await res.json();
  const grid = document.getElementById("plugin-grid");
  grid.innerHTML = "";
  (data.plugins || []).forEach(p => {
    const card = document.createElement("div");
    card.style.cssText = "border:1px solid var(--border-color,#333);border-radius:10px;padding:12px;";
    card.innerHTML = `
      <h3>${p.name}</h3>
      <p>${p.description || ""}</p>
      <p>v${p.version} · ${p.category}</p>
      <p>${p.downloads_count} downloads · ★ ${p.rating_avg}</p>
      <button data-id="${p.id}" class="install-btn">Install</button>
    `;
    grid.appendChild(card);
  });
  document.querySelectorAll(".install-btn").forEach(btn => {
    btn.addEventListener("click", () => installPlugin(btn.dataset.id));
  });
}

async function installPlugin(pluginId) {
  const res = await fetch(`/api/marketplace/install/${pluginId}`, {
    method: "POST",
    headers: authHeaders()
  });
  const data = await res.json();
  alert(data.message || "Installed");
  loadInstalled();
}

async function loadInstalled() {
  const res = await fetch("/api/marketplace/installed", { headers: authHeaders() });
  const data = await res.json();
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

loadPlugins();
loadInstalled();