if (!sessionStorage.getItem("access_token")) window.location.replace("/login.html");

function authHeaders() {
  const token = sessionStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, {
      ...options,
      headers: {"Content-Type": "application/json", ...authHeaders(), ...(options.headers || {})},
    });
  } catch (_) { throw new Error("Network request failed."); }
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("user");
    window.location.replace("/login.html");
    throw new Error("Session expired.");
  }
  if (!response.ok) throw new Error(data.error || "Unable to load billing data.");
  return data;
}

async function loadBilling() {
  const [subscriptionData, creditData, invoiceData, config] = await Promise.all([
    api("/api/billing/subscription"), api("/api/billing/credits"), api("/api/billing/invoices"), api("/api/billing/config")
  ]);
  const subscription = subscriptionData.subscription;
  document.getElementById("plan-name").textContent = `Plan: ${subscription.plan_name} (${subscription.status})`;
  document.getElementById("credits-left").textContent = `Credits: ${creditData.credits}`;
  const invoices = invoiceData.invoices || [];
  const list = document.getElementById("invoice-list");
  list.replaceChildren(...invoices.map((invoice) => {
    const item = document.createElement("li");
    item.textContent = `${invoice.invoice_id} — ${invoice.amount} ${invoice.currency} (${invoice.status})`;
    return item;
  }));
  document.getElementById("invoice-empty").hidden = invoices.length !== 0;
  renderCheckout(config, subscription);
}

function renderCheckout(config, subscription) {
  const status = document.getElementById("billing-status");
  const actions = document.getElementById("billing-checkout-actions");
  actions.replaceChildren();
  if (subscription.provider_managed && subscription.status === "active") {
    const cancel = document.createElement("button");
    cancel.type = "button"; cancel.textContent = "Cancel subscription";
    cancel.addEventListener("click", async () => {
      if (!window.confirm("Cancel this subscription?")) return;
      cancel.disabled = true;
      try { await api("/api/billing/subscription/cancel", {method: "POST"}); await loadBilling(); }
      catch (error) { status.textContent = error.message; cancel.disabled = false; }
    });
    actions.append(cancel);
  }
  if (!config.tenant_billing_enabled) { status.textContent = "Checkout is disabled by your tenant policy."; return; }
  if (!config.checkout_available) { status.textContent = "Payment provider: Not configured"; return; }
  status.textContent = `Payment provider: ${config.provider}`;
  for (const plan of config.plans || []) {
    const button = document.createElement("button");
    button.type = "button"; button.textContent = `Checkout for ${plan}`;
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const checkout = await api("/api/billing/checkout", {method: "POST", body: JSON.stringify({plan})});
        window.location.assign(checkout.url);
      } catch (error) { status.textContent = error.message; button.disabled = false; }
    });
    actions.append(button);
  }
}

loadBilling().catch((error) => {
  document.getElementById("billing-status").textContent = error.message;
});
