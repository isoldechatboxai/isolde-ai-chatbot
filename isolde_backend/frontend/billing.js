function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("access_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function loadSubscription() {
  const res = await fetch("/api/billing/subscription", { headers: authHeaders() });
  const data = await res.json();
  document.getElementById("plan-name").textContent = `Plan: ${data.subscription.plan_name} (${data.subscription.status})`;
  loadCredits();
}

async function loadCredits() {
  const res = await fetch("/api/billing/credits", { headers: authHeaders() });
  const data = await res.json();
  document.getElementById("credits-left").textContent = `Credits: ${data.credits}`;
}

async function subscribe() {
  const plan_name = document.getElementById("plan-select").value;
  const res = await fetch("/api/billing/subscription", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ plan_name })
  });
  const data = await res.json();
  alert(data.message || "Subscription updated");
  loadSubscription();
}

async function loadInvoices() {
  const res = await fetch("/api/billing/invoices", { headers: authHeaders() });
  const data = await res.json();
  const list = document.getElementById("invoice-list");
  list.innerHTML = "";
  (data.invoices || []).forEach(inv => {
    const li = document.createElement("li");
    li.textContent = `${inv.invoice_id} — ${inv.amount} ${inv.currency} (${inv.status})`;
    list.appendChild(li);
  });
}

async function generateInvoice() {
  const res = await fetch("/api/billing/invoices", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ amount: 19.99, currency: "USD" })
  });
  await res.json();
  loadInvoices();
}

document.getElementById("subscribe-btn").addEventListener("click", subscribe);
document.getElementById("generate-invoice-btn").addEventListener("click", generateInvoice);

loadSubscription();
loadInvoices();