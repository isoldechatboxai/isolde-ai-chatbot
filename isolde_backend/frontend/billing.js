function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function api(path) {
  const response = await fetch(path, { headers: authHeaders() });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    localStorage.removeItem("access_token");
    window.location.replace("/login.html");
    throw new Error("Session expired.");
  }
  if (!response.ok) throw new Error(data.error || "Unable to load billing data.");
  return data;
}

async function loadBilling() {
  const [subscriptionData, creditData, invoiceData] = await Promise.all([
    api("/api/billing/subscription"), api("/api/billing/credits"), api("/api/billing/invoices")
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
}

loadBilling().catch((error) => {
  document.getElementById("billing-status").textContent = error.message;
});
