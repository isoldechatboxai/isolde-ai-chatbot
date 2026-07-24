// ===== Config =====
// Relative path: works automatically when this page is served by the
// Flask backend itself (http://127.0.0.1:5000/). If you instead open
// this file directly (file://) or serve it from a separate dev server,
// change this back to an absolute URL, e.g. "http://127.0.0.1:5000/api/chat",
// and make sure that origin is listed in CORS_ORIGINS in the backend's .env.
const API_URL = "/api/chat";
const BOT_NAME = "Isolde";

// ===== State =====
let chatHistory = []; // { role: 'user'|'bot', text, time }

// ===== DOM =====
const chatArea = document.getElementById("chatArea");
const welcomeScreen = document.getElementById("welcomeScreen");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const typingIndicator = document.getElementById("typingIndicator");
const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");
const clearChatBtn = document.getElementById("clearChatBtn");
const toast = document.getElementById("toast");
const voiceBtn = document.getElementById("voiceBtn");

const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    voiceBtn.addEventListener("click", () => {
    messageInput.value = "";
    recognition.start();
});

recognition.onstart = () => {
    console.log("Speech recognition started");
};
    recognition.onresult = (event) => {
        const text = event.results[0][0].transcript;

        console.log("Recognized:", text);

        alert(text);

        messageInput.value = text;
        updateSendButtonState();
    };

    recognition.onend = () => {
        console.log("Recognition ended");
    };

    recognition.onerror = (event) => {
        console.log("Error:", event.error);
        alert("Error: " + event.error);
    };
    
}

// ===== Theme =====
function initTheme() {
  const saved = localStorageSafeGet("isolde-theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
  updateThemeIcon(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  localStorageSafeSet("isolde-theme", next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  if (theme === "dark") {
    themeIcon.innerHTML = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>`;
  } else {
    themeIcon.innerHTML = `<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>`;
  }
}

// Safe localStorage wrappers (in case of sandboxed environments)
function localStorageSafeGet(key) {
  try { return localStorage.getItem(key); } catch (e) { return null; }
}
function localStorageSafeSet(key, val) {
  try { localStorage.setItem(key, val); } catch (e) {}
}

// ===== Utility =====
function formatTime(date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3000);
}

function scrollToBottom() {
  chatArea.scrollTop = chatArea.scrollHeight;
}

// ===== Rendering =====
function hideWelcome() {
  if (welcomeScreen) welcomeScreen.style.display = "none";
}

function renderMessage(role, text, time) {
  hideWelcome();

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = `message-avatar ${role === "user" ? "user-avatar" : "bot-avatar"}`;
  avatar.innerHTML = role === "user"
    ? "U"
    : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" fill="white" fill-opacity="0.001"/><path d="M8 12.5C8 12.5 9.5 15 12 15C14.5 15 16 12.5 16 12.5" stroke="white" stroke-width="1.5" stroke-linecap="round"/><circle cx="9" cy="9.5" r="1" fill="white"/><circle cx="15" cy="9.5" r="1" fill="white"/></svg>`;

  const content = document.createElement("div");
  content.className = "message-content";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "bot") {
    bubble.innerHTML = marked.parse(text);

    // Highlight code blocks
    bubble.querySelectorAll("pre code").forEach((block) => {
        hljs.highlightElement(block);
    });
} else {
    bubble.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
}

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.innerHTML = `<span>${formatTime(time)}</span>`;

  const copyBtn = document.createElement("button");
  copyBtn.className = "copy-btn";
  copyBtn.title = "Copy message";
  copyBtn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
  copyBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard"));
  });
  meta.appendChild(copyBtn);

  content.appendChild(bubble);
  content.appendChild(meta);
  row.appendChild(avatar);
row.appendChild(content);

chatArea.appendChild(row);

scrollToBottom();
}

// ===== Typing indicator =====
function showTyping() {
  typingIndicator.style.display = "flex";
  scrollToBottom();
}
function hideTyping() {
  typingIndicator.style.display = "none";
}

// ===== Sending messages =====
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;

  const now = new Date();
  renderMessage("user", text, now);
  chatHistory.push({ role: "user", text, time: now });

  messageInput.value = "";
  autoResizeInput();
  updateSendButtonState();

  showTyping();

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });

    if (!response.ok) {
      throw new Error(`Server responded with status ${response.status}`);
    }

    const data = await response.json();
    hideTyping();

    const replyText = data.reply || "Sorry, I didn't get a proper response.";
    const replyTime = new Date();
    renderMessage("bot", replyText, replyTime);
    chatHistory.push({ role: "bot", text: replyText, time: replyTime });
  } catch (err) {
    hideTyping();
    console.error("Chat error:", err);
    const errorMsg = "⚠️ Unable to reach the server. Please make sure the backend is running.";
    renderMessage("bot", errorMsg, new Date());
    showToast("Backend unavailable. Check your Flask server.");
  }
}

// ===== Input handling =====
function autoResizeInput() {
  messageInput.style.height = "auto";
  messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + "px";
}

function updateSendButtonState() {
  sendBtn.disabled = messageInput.value.trim().length === 0;
}

messageInput.addEventListener("input", () => {
  autoResizeInput();
  updateSendButtonState();
});

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

// ===== Suggestions =====
document.querySelectorAll(".suggestion-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    messageInput.value = chip.dataset.text;
    updateSendButtonState();
    sendMessage();
  });
});

// ===== Clear chat =====
clearChatBtn.addEventListener("click", () => {
  if (chatHistory.length === 0) return;
  if (confirm("Clear the current chat session?")) {
    chatHistory = [];
    // Remove all message rows, keep welcome screen structure
    document.querySelectorAll(".message-row").forEach((el) => el.remove());
    if (welcomeScreen) welcomeScreen.style.display = "flex";
    hideTyping();
  }
});

// ===== Theme toggle =====
themeToggle.addEventListener("click", toggleTheme);

// ===== Init =====
initTheme();
updateSendButtonState();
messageInput.focus();
