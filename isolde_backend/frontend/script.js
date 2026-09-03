// frontend/script.js
// PRESENTATION-ONLY refactor: hard-coded inline dark styles moved to CSS classes.
// NO functional changes: all IDs, event listeners, API calls, state, and logic preserved.
(() => {
  "use strict";

  // Clear persistent state left by pre-session-only frontend releases.
  function clearLegacyPersistentState() {
    try {
      ["access_token", "user", "isolde-conversations", "isolde-active-conversation"]
        .forEach((key) => localStorage.removeItem(key));
    } catch (_) {}
  }
  clearLegacyPersistentState();

  function escapeText(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  if (typeof marked !== "undefined") {
    const codeRenderer = new marked.Renderer();
    codeRenderer.code = function (code, language) {
      const validLang =
        typeof hljs !== "undefined" && language && hljs.getLanguage(language)
          ? language
          : "";
      let highlighted;
      try {
        if (validLang) {
          highlighted = hljs.highlight(code, { language: validLang }).value;
        } else if (typeof hljs !== "undefined") {
          highlighted = hljs.highlightAuto(code).value;
        } else {
          highlighted = code
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
        }
      } catch (e) {
        highlighted = code
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");
      }

      const langLabel = escapeText(String(language || "PLAINTEXT").toUpperCase());
      let encodedCode = "";
      try {
        encodedCode = btoa(unescape(encodeURIComponent(code)));
      } catch (e) {
        encodedCode = "";
      }

      // Presentation: inline dark styles removed — now styled by style.css (theme-aware)
      return `<div class="code-block-wrapper">
        <div class="code-block-header">
          <span class="code-block-lang">${langLabel}</span>
          <button type="button" class="code-copy-btn" data-code-b64="${encodedCode}">📋 Copy Code</button>
        </div>
        <pre><code class="hljs ${validLang}">${highlighted}</code></pre>
      </div>`;
    };

    marked.setOptions({
      renderer: codeRenderer,
      highlight: function (code, lang) {
        if (typeof hljs !== "undefined" && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return typeof hljs !== "undefined" ? hljs.highlightAuto(code).value : code;
      },
      breaks: true,
      gfm: true,
    });
  }

  document.addEventListener("click", (event) => {
    const btn = event.target.closest ? event.target.closest(".code-copy-btn") : null;
    if (!btn) return;
    event.preventDefault();
    event.stopPropagation();

    const b64 = btn.getAttribute("data-code-b64") || "";
    let codeText = "";
    try {
      codeText = decodeURIComponent(escape(atob(b64)));
    } catch (e) {
      codeText = "";
    }

    const doCopy = () => {
      const originalLabel = btn.dataset.originalLabel || btn.textContent;
      btn.dataset.originalLabel = originalLabel;
      btn.textContent = "✓ Copied!";
      btn.classList.add("is-copied");
      clearTimeout(btn._codeCopyTimer);
      btn._codeCopyTimer = setTimeout(() => {
        btn.textContent = originalLabel;
        btn.classList.remove("is-copied");
      }, 1600);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(codeText)
        .then(doCopy)
        .catch(() => {
          const ta = document.createElement("textarea");
          ta.value = codeText;
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand("copy"); } catch (e) {}
          document.body.removeChild(ta);
          doCopy();
        });
    } else {
      const ta = document.createElement("textarea");
      ta.value = codeText;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (e) {}
      document.body.removeChild(ta);
      doCopy();
    }
  });

  const isLoginPage =
    window.location.pathname.includes("login.html") ||
    window.location.pathname.endsWith("login");

  if (isLoginPage) {
    initLoginPage();
  } else {
    initChatbotApp();
  }

  function getAuthHeaders(includeJson = false) {
    const headers = {};
    if (includeJson) {
      headers["Content-Type"] = "application/json";
    }
    const token = sessionStorage.getItem("access_token");
    if (token && token !== "null" && token !== "undefined") {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  }

  function initLoginPage() {
    const init = () => {
      const loginForm = document.getElementById("login-form");
      const loginBtn = document.getElementById("login-btn");
      const btnText = loginBtn?.querySelector(".btn-text");
      const spinner = loginBtn?.querySelector(".spinner");
      const messageContainer = document.getElementById("message-container");

      const setLoading = (isLoading) => {
        if (isLoading) {
          btnText?.classList.add("hidden");
          spinner?.classList.remove("hidden");
          loginBtn.disabled = true;
          loginBtn.style.opacity = "0.8";
        } else {
          btnText?.classList.remove("hidden");
          spinner?.classList.add("hidden");
          loginBtn.disabled = false;
          loginBtn.style.opacity = "1";
        }
      };

      const showMessage = (type, text) => {
        if (!messageContainer) return;
        messageContainer.textContent = text;
        messageContainer.className = `message ${type}`;
        setTimeout(() => {
          messageContainer.classList.add("hidden");
          messageContainer.className = "message hidden";
        }, 4000);
      };

      if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
          e.preventDefault();
          const email = document.getElementById("email").value;
          const password = document.getElementById("password").value;
          if (!email || !password) {
            showMessage("error", "Please fill in all fields.");
            return;
          }
          setLoading(true);
          try {
            const response = await fetch("/api/login", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ email, password }),
            });
            const data = await response.json();
            if (response.ok && data.access_token) {
              sessionStorage.setItem("access_token", data.access_token);
              sessionStorage.setItem("user", JSON.stringify(data.user || {}));
              showMessage("success", "Welcome back! Redirecting...");
              setTimeout(() => { window.location.href = "/"; }, 1000);
            } else {
              showMessage("error", data.error || "Invalid email or password.");
              setLoading(false);
            }
          } catch (err) {
            console.error("Login failed", err);
            showMessage("error", "Server error. Please try again later.");
            setLoading(false);
          }
        });
      }

    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }

  function initChatbotApp() {
    const accessToken = sessionStorage.getItem("access_token");
    if (!accessToken || accessToken === "null" || accessToken === "undefined") {
      window.location.replace("/login.html");
      return;
    }
    const STORAGE_KEYS = {
      THEME: "isolde-theme",
      PREFERENCES: "isolde-preferences",
    };

    const MAX_TEXTAREA_HEIGHT = 200;
    const COPY_FEEDBACK_DURATION = 1600;

    let dom = {};
    let state = {
      conversations: {},
      activeConversationId: null,
      backendConversationId: null,
      isLoading: false,
      isRecording: false,
      searchQuery: "",
      abortController: null,
      streamingBotMsgObj: null,
      streamingTextEl: null,
      generationId: null,
      webSearchEnabled: false,
      capabilities: {},
    };

    let preferences = {
      theme: "dark",
      defaultModel: "Flash-Lite Extended",
      systemPrompt: "",
    };

    let speechRecognition = null;
    if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
      const SpeechAuth = window.SpeechRecognition || window.webkitSpeechRecognition;
      speechRecognition = new SpeechAuth();
      speechRecognition.continuous = false;
      speechRecognition.interimResults = false;

      speechRecognition.onresult = function (event) {
        const transcript = event.results[0][0].transcript;
        if (dom.messageTextarea) {
          const currentVal = dom.messageTextarea.value.trim();
          dom.messageTextarea.value = currentVal ? `${currentVal} ${transcript}` : transcript;
          autoResizeTextarea();
          updateSendButtonState();
        }
        stopVoiceRecording();
      };

      speechRecognition.onerror = function (event) {
        console.error("Speech recognition error:", event.error);
        stopVoiceRecording();
      };

      speechRecognition.onend = function () {
        stopVoiceRecording();
      };
    }

    function bindDomElements() {
      dom = {
        app: document.querySelector(".app"),
        sidebar: document.querySelector(".sidebar"),
        newChatBtn: document.querySelector(".new-chat-btn"),
        chatHistoryList: document.getElementById("chat-history-list") || document.querySelector(".chat-history-list"),
        chatSearchInput: document.getElementById("chat-search-input"),
        themeToggleBtn: document.querySelector(".theme-toggle-btn"),
        clearChatBtn: document.querySelector(".clear-chat-btn"),
        logoutBtn: document.getElementById("logout-btn") || document.querySelector(".logout-btn"),
        chatArea: document.querySelector(".chat-area"),
        welcomeScreen: document.querySelector(".welcome-screen"),
        chatMessages: document.querySelector(".chat-messages"),
        suggestionChips: document.querySelectorAll(".suggestion-chip"),
        typingIndicator: document.querySelector(".typing-indicator"),
        messageForm: document.querySelector(".message-form, form"),
        messageTextarea: document.getElementById("messageInput") || document.getElementById("chat-message-input") || document.querySelector(".message-textarea, textarea"),
        sendBtn: document.querySelector(".send-btn, button[type='submit']"),
        fileUploadBtn: document.querySelector(".file-upload-btn, .attachment-btn"),
        fileUploadInput: document.getElementById("file-upload-input") || document.querySelector(".file-upload-input, input[type='file']"),
        voiceInputBtn: document.querySelector(".voice-input-btn, .mic-btn"),
        sidebarUserName: document.getElementById("sidebar-user-name"),
        sidebarUserEmail: document.getElementById("sidebar-user-email"),
        memoryList: document.getElementById("memory-list"),
        clearAllMemoriesBtn: document.getElementById("clear-all-memories"),
        modelSelect: document.getElementById("ai-model-select"),
        attachmentMenu: document.getElementById("attachment-menu"),
        toggleAttachmentBtn: document.getElementById("toggle-attachment-btn"),
        settingsBtn: document.getElementById("open-settings-btn"),
        sidebarToggleBtn: document.getElementById("sidebar-toggle-btn"),
        appSidebar: document.getElementById("app-sidebar") || document.getElementById("sidebar"),
        stopGenerationBtn: null,
        webSearchToggleBtn: null,
      };
    }

    function injectDynamicButtons() {
      if (dom.voiceInputBtn && !document.getElementById("web-search-toggle-btn")) {
        const webBtn = document.createElement("button");
        webBtn.type = "button";
        webBtn.id = "web-search-toggle-btn";
        webBtn.className = "web-search-toggle-btn";
        webBtn.textContent = "🌐 Web: AUTO";
        webBtn.title = "Automatically use web research for current or comparison questions";
        webBtn.addEventListener("click", (e) => {
          e.preventDefault();
          state.webSearchEnabled = !state.webSearchEnabled;
          if (state.webSearchEnabled) {
            webBtn.textContent = "🌐 Web: ON";
            webBtn.classList.add("is-on");
          } else {
            webBtn.textContent = "🌐 Web: AUTO";
            webBtn.classList.remove("is-on");
          }
        });
        if (dom.voiceInputBtn.parentNode) {
          dom.voiceInputBtn.parentNode.insertBefore(webBtn, dom.voiceInputBtn.nextSibling);
        }
        dom.webSearchToggleBtn = webBtn;
      }

      if (!document.getElementById("stop-generation-btn")) {
        const stopBtn = document.createElement("button");
        stopBtn.type = "button";
        stopBtn.id = "stop-generation-btn";
        stopBtn.className = "stop-generation-btn";
        stopBtn.textContent = "⏹ Stop Generating";
        stopBtn.addEventListener("mouseover", () => {
          stopBtn.classList.add("is-hover");
        });
        stopBtn.addEventListener("mouseout", () => {
          stopBtn.classList.remove("is-hover");
        });
        stopBtn.addEventListener("click", async (e) => {
          e.preventDefault();
          if (!state.generationId) {
            appendBotMessage("Cancellation is not yet available for this request.");
            return;
          }
          try {
              const response = await fetch("/api/chat/stop", {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify({ generation_id: state.generationId }),
              });
              const data = await response.json().catch(() => ({}));
              if (!response.ok || data.stopped !== true) {
                appendBotMessage(data.error || "This generation could not be cancelled.");
                return;
              }
              if (state.abortController) state.abortController.abort();
          } catch (err) {
            appendBotMessage("Cancellation service could not be reached.");
          }
        });

        const host = dom.messageForm || (dom.messageTextarea && dom.messageTextarea.parentNode);
        if (host) {
          const cs = window.getComputedStyle(host);
          if (cs.position === "static") {
            host.style.position = "relative";
          }
          host.appendChild(stopBtn);
        } else {
          document.body.appendChild(stopBtn);
          stopBtn.style.position = "fixed";
          stopBtn.style.bottom = "90px";
        }
        dom.stopGenerationBtn = stopBtn;
      }
    }

    function updateStopButtonVisibility() {
      if (dom.stopGenerationBtn) {
        dom.stopGenerationBtn.style.display = state.isLoading ? "inline-block" : "none";
      }
    }

    function generateId() {
      return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    }

    function formatTime(date) {
      try {
        return new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      } catch (e) {
        return "";
      }
    }

    function deriveTitle(text) {
      const trimmed = text.trim().replace(/\s+/g, " ");
      return trimmed.length > 42 ? `${trimmed.slice(0, 42)}…` : trimmed || "New conversation";
    }

    function sanitizeFilename(name) {
      const clean = String(name || "chat")
        .toLowerCase()
        .replace(/[^a-z0-9-_ ]/gi, "")
        .trim()
        .replace(/\s+/g, "-")
        .slice(0, 60);
      return clean || "chat";
    }

    function downloadJson(data, filename) {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function sanitizeHtml(html) {
      if (!html) return "";
      const template = document.createElement("template");
      template.innerHTML = html;
      template.content.querySelectorAll("script,iframe,object,embed,link,style,meta,base").forEach((el) => el.remove());
      template.content.querySelectorAll("*").forEach((el) => {
        Array.from(el.attributes).forEach((attr) => {
          const name = attr.name.toLowerCase();
          const value = (attr.value || "").trim().toLowerCase();
          if (name.startsWith("on")) {
            el.removeAttribute(attr.name);
          } else if (["href", "src", "xlink:href", "action", "formaction", "data", "background"].includes(name)) {
            try {
              const url = new URL(attr.value, window.location.origin);
              if (!["http:", "https:", "mailto:"].includes(url.protocol)) el.removeAttribute(attr.name);
            } catch (_) { el.removeAttribute(attr.name); }
          }
        });
      });
      return template.innerHTML;
    }

    function scrollToBottom() {
      if (!dom.chatMessages) return;
      dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
    }

    function saveChat() {
      // Conversation content remains in memory only. The authenticated backend
      // history API is authoritative after reload.
    }

    function loadChat() {
      // Deliberately no browser conversation cache.
    }

    function saveTheme(theme) {
      try { sessionStorage.setItem(STORAGE_KEYS.THEME, theme); } catch (err) {}
    }

    function loadTheme() {
      try { return sessionStorage.getItem(STORAGE_KEYS.THEME); } catch (err) { return null; }
    }

    function applyTheme(theme) {
      if (!document.documentElement) return;
      document.documentElement.setAttribute("data-theme", theme);
      if (dom.themeToggleBtn) {
        dom.themeToggleBtn.setAttribute("data-theme", theme);
        dom.themeToggleBtn.setAttribute("title", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
      }
    }

    function toggleTheme() {
      const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      const next = current === "dark" ? "light" : "dark";
      applyTheme(next);
      saveTheme(next);
      preferences.theme = next;
      savePreferences();
    }

    function restoreTheme() {
      const saved = loadTheme();
      const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
      const theme = saved || (prefersDark ? "dark" : "light");
      applyTheme(theme);
    }

    function savePreferences() {
      try { sessionStorage.setItem(STORAGE_KEYS.PREFERENCES, JSON.stringify(preferences)); } catch (err) {}
    }

    function loadPreferences() {
      try {
        const raw = sessionStorage.getItem(STORAGE_KEYS.PREFERENCES);
        if (raw) {
          const parsed = JSON.parse(raw);
          preferences = { ...preferences, ...parsed };
        }
      } catch (err) {}
      const savedTheme = loadTheme();
      if (savedTheme) preferences.theme = savedTheme;
    }

    function hideWelcomeScreen() {
      if (dom.welcomeScreen) dom.welcomeScreen.style.display = "none";
      if (dom.chatMessages) {
        dom.chatMessages.style.display = "flex";
        dom.chatMessages.removeAttribute("hidden");
      }
    }

    function showWelcomeScreen() {
      if (dom.welcomeScreen) dom.welcomeScreen.style.display = "flex";
      if (dom.chatMessages) {
        dom.chatMessages.style.display = "none";
        dom.chatMessages.setAttribute("hidden", "true");
      }
    }

    function createConversation() {
      const id = generateId();
      state.conversations[id] = {
        id,
        title: "New conversation",
        messages: [],
        isBackend: false,
        isPinned: false,
        created_at: new Date().toISOString(),
      };
      state.activeConversationId = id;
      state.backendConversationId = null;
      if (dom.chatSearchInput) {
        dom.chatSearchInput.value = "";
        state.searchQuery = "";
      }
      renderChatHistory();
      renderActiveConversation();
      saveChat();
      if (dom.messageTextarea) dom.messageTextarea.focus();
      return id;
    }

    function getActiveConversation() {
      if (!state.activeConversationId || !state.conversations[state.activeConversationId]) {
        createConversation();
      }
      return state.conversations[state.activeConversationId];
    }

    function renderActiveConversation() {
      if (!dom.chatMessages) return;
      dom.chatMessages.innerHTML = "";
      const conversation = state.conversations[state.activeConversationId];
      if (!conversation || conversation.messages.length === 0) {
        showWelcomeScreen();
        return;
      }
      hideWelcomeScreen();
      conversation.messages.forEach((message) => {
        renderMessage(message.role, message.text, message.time, message.sources);
      });
      scrollToBottom();
    }

    async function loadConversationMessages(id) {
      if (!state.conversations[id] || !state.conversations[id].isBackend) return;
      try {
        const response = await fetch(`/api/history/${id}`, { headers: getAuthHeaders() });
        if (response.ok) {
          const data = await response.json();
          if (data.conversation && data.conversation.messages) {
            state.conversations[id].messages = data.conversation.messages.map((m) => ({
              role: m.role === "user" ? "user" : "bot",
              text: m.content,
              time: m.created_at || new Date().toISOString(),
              sources: m.sources || []
            }));
          }
        }
      } catch (err) {
        console.error("Isolde: Failed to load messages for conversation", id, err);
      }
    }

    async function switchConversation(id) {
      if (!state.conversations[id]) return;
      state.activeConversationId = id;
      if (state.conversations[id].isBackend) {
        state.backendConversationId = id;
      } else {
        state.backendConversationId = null;
      }
      if (state.conversations[id].isBackend && state.conversations[id].messages.length === 0) {
        await loadConversationMessages(id);
      }
      renderChatHistory();
      renderActiveConversation();
      saveChat();
    }

    async function togglePinChatAPI(id) {
      try {
        const response = await fetch("/api/chat/pin", {
          method: "POST",
          headers: getAuthHeaders(true),
          body: JSON.stringify({ conversation_id: id }),
        });
        const data = await response.json();
        if (response.ok) {
          showBroadcastToast(data.message || "Pin status updated.");
          return data.is_pinned;
        }
      } catch (err) {
        console.error("Isolde: Failed to pin chat", err);
      }
      return null;
    }

    async function exportConversation(conversation) {
      try {
        let exportPayload;
        if (conversation.isBackend) {
          const response = await fetch(`/api/history/${conversation.id}/export`, { headers: getAuthHeaders() });
          if (!response.ok) throw new Error("Export failed");
          exportPayload = await response.json();
        } else {
          exportPayload = {
            export_version: 1,
            exported_at: new Date().toISOString(),
            conversation: {
              id: conversation.id,
              title: conversation.title,
              is_pinned: conversation.isPinned || false,
              created_at: conversation.created_at || null,
              messages: conversation.messages || [],
            },
          };
        }
        downloadJson(exportPayload, `isolde-chat-${sanitizeFilename(conversation.title || conversation.id)}.json`);
      } catch (err) {
        console.error("Isolde: Failed to export chat", err);
        alert("Failed to export chat.");
      }
    }

    function getConversationLastTime(conversation) {
      const raw = conversation.messages && conversation.messages.length > 0
        ? conversation.messages[conversation.messages.length - 1].time
        : conversation.created_at || conversation.id || "";
      const parsed = new Date(raw).getTime();
      return Number.isNaN(parsed) ? 0 : parsed;
    }

    function renderChatHistory() {
      if (!dom.chatHistoryList) return;

      let filteredConversations = Object.values(state.conversations);
      if (state.searchQuery.trim() !== "") {
        const q = state.searchQuery.toLowerCase();
        filteredConversations = filteredConversations.filter((c) => (c.title || "").toLowerCase().includes(q));
      }

      filteredConversations.sort((a, b) => {
        if (a.isPinned && !b.isPinned) return -1;
        if (!a.isPinned && b.isPinned) return 1;
        return getConversationLastTime(b) - getConversationLastTime(a);
      });

      dom.chatHistoryList.innerHTML = "";

      if (filteredConversations.length === 0) {
        const emptyMsg = document.createElement("li");
        emptyMsg.className = "chat-history-empty";
        emptyMsg.textContent = "No chats found.";
        dom.chatHistoryList.appendChild(emptyMsg);
        return;
      }

      filteredConversations.forEach((conversation) => {
        const item = document.createElement("li");
        item.className = "chat-history-item";
        if (conversation.id === state.activeConversationId) {
          item.classList.add("active");
        }

        const link = document.createElement("a");
        link.className = "chat-history-link";
        link.href = "#";
        link.textContent = conversation.title || "New conversation";
        link.addEventListener("click", async (event) => {
          event.preventDefault();
          await switchConversation(conversation.id);
        });

        const actionsDiv = document.createElement("div");
        actionsDiv.className = "chat-history-actions";

        const renameBtn = document.createElement("button");
        renameBtn.type = "button";
        renameBtn.textContent = "✏️";
        renameBtn.title = "Rename chat";
        renameBtn.style.background = "transparent";
        renameBtn.style.border = "none";
        renameBtn.style.cursor = "pointer";
        renameBtn.style.fontSize = "12px";
        renameBtn.style.padding = "2px 4px";
        renameBtn.style.opacity = "0.5";
        renameBtn.addEventListener("mouseover", () => (renameBtn.style.opacity = "1"));
        renameBtn.addEventListener("mouseout", () => (renameBtn.style.opacity = "0.5"));
        renameBtn.addEventListener("click", (event) => {
          event.stopPropagation();
          link.style.display = "none";
          actionsDiv.style.display = "none";
          const input = document.createElement("input");
          input.type = "text";
          input.value = conversation.title || "";
          input.style.flex = "1";
          input.style.background = "transparent";
          input.style.border = "1px solid #6b7280";
          input.style.color = "inherit";
          input.style.borderRadius = "4px";
          input.style.padding = "4px 8px";
          input.style.marginRight = "8px";
          input.style.outline = "none";
          input.style.fontSize = "13px";
          let committed = false;
          const commit = async () => {
            if (committed) return;
            committed = true;
            const newTitle = input.value.trim();
            if (newTitle && newTitle !== conversation.title) {
              const oldTitle = conversation.title;
              conversation.title = newTitle;
              saveChat();
              renderChatHistory();
              if (conversation.isBackend) {
                try {
                  const response = await fetch(`/api/history/${conversation.id}/update`, {
                    method: "PATCH",
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ title: newTitle }),
                  });
                  if (!response.ok) throw new Error("Rename failed");
                } catch (err) {
                  console.error("Isolde: Failed to rename chat", err);
                  conversation.title = oldTitle;
                  saveChat();
                  renderChatHistory();
                  alert("Failed to rename chat.");
                }
              }
            } else {
              renderChatHistory();
            }
          };
          input.addEventListener("blur", commit);
          input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); commit(); }
            if (e.key === "Escape") { committed = true; renderChatHistory(); }
          });
          item.insertBefore(input, actionsDiv);
          input.focus();
          input.setSelectionRange(0, input.value.length);
        });

        const pinBtn = document.createElement("button");
        pinBtn.type = "button";
        pinBtn.textContent = conversation.isPinned ? "📍" : "📌";
        pinBtn.title = conversation.isPinned ? "Unpin chat" : "Pin chat";
        pinBtn.style.background = "transparent";
        pinBtn.style.border = "none";
        pinBtn.style.cursor = "pointer";
        pinBtn.style.fontSize = "12px";
        pinBtn.style.padding = "2px 4px";
        pinBtn.style.opacity = conversation.isPinned ? "1" : "0.5";
        pinBtn.addEventListener("mouseover", () => (pinBtn.style.opacity = "1"));
        pinBtn.addEventListener("mouseout", () => (pinBtn.style.opacity = conversation.isPinned ? "1" : "0.5"));
        pinBtn.addEventListener("click", async (event) => {
          event.stopPropagation();
          if (conversation.isBackend) {
            const isNowPinned = await togglePinChatAPI(conversation.id);
            if (isNowPinned !== null) {
              conversation.isPinned = isNowPinned;
              renderChatHistory();
              saveChat();
            }
          } else {
            conversation.isPinned = !conversation.isPinned;
            renderChatHistory();
            saveChat();
          }
        });

        const exportBtn = document.createElement("button");
        exportBtn.type = "button";
        exportBtn.textContent = "📤";
        exportBtn.title = "Export chat";
        exportBtn.style.background = "transparent";
        exportBtn.style.border = "none";
        exportBtn.style.cursor = "pointer";
        exportBtn.style.fontSize = "12px";
        exportBtn.style.padding = "2px 4px";
        exportBtn.style.opacity = "0.5";
        exportBtn.addEventListener("mouseover", () => (exportBtn.style.opacity = "1"));
        exportBtn.addEventListener("mouseout", () => (exportBtn.style.opacity = "0.5"));
        exportBtn.addEventListener("click", (event) => {
          event.stopPropagation();
          exportConversation(conversation);
        });

        const deleteBtn = document.createElement("button");
        deleteBtn.type = "button";
        deleteBtn.textContent = "🗑️";
        deleteBtn.title = "Delete chat";
        deleteBtn.style.background = "transparent";
        deleteBtn.style.border = "none";
        deleteBtn.style.cursor = "pointer";
        deleteBtn.style.fontSize = "12px";
        deleteBtn.style.padding = "2px 4px";
        deleteBtn.style.opacity = "0.5";
        deleteBtn.addEventListener("mouseover", () => (deleteBtn.style.opacity = "1"));
        deleteBtn.addEventListener("mouseout", () => (deleteBtn.style.opacity = "0.5"));
        deleteBtn.addEventListener("click", async (event) => {
          event.stopPropagation();
          if (conversation.isBackend) {
            try {
              const response = await fetch(`/api/history/${conversation.id}`, {
                method: "DELETE",
                headers: getAuthHeaders(),
              });
              if (!response.ok) throw new Error("Delete failed");
            } catch (err) {
              console.error("Isolde: Failed to delete chat", err);
              alert("Failed to delete chat.");
              return;
            }
          }
          delete state.conversations[conversation.id];
          if (state.activeConversationId === conversation.id) {
            const remainingIds = Object.keys(state.conversations);
            if (remainingIds.length > 0) {
              await switchConversation(remainingIds[0]);
            } else {
              createConversation();
            }
          } else {
            renderChatHistory();
          }
          saveChat();
        });

        actionsDiv.appendChild(renameBtn);
        actionsDiv.appendChild(pinBtn);
        actionsDiv.appendChild(exportBtn);
        actionsDiv.appendChild(deleteBtn);
        item.appendChild(link);
        item.appendChild(actionsDiv);
        dom.chatHistoryList.appendChild(item);
      });
    }

    async function submitFeedback(rating, comment) {
      try {
        const response = await fetch("/api/feedback", {
          method: "POST",
          headers: getAuthHeaders(true),
          body: JSON.stringify({ rating, comment }),
        });
        if (!response.ok) throw new Error("Feedback was not accepted.");
      } catch (err) {
        console.error("Isolde: Feedback submission failed", err);
      }
    }

    async function loadMemories() {
      try {
        const response = await fetch("/api/memory/list", { headers: getAuthHeaders() });
        if (response.ok) {
          const data = await response.json();
          if (dom.memoryList) {
            dom.memoryList.innerHTML = "";
            if (!data.memories || data.memories.length === 0) {
              const empty = document.createElement("li");
              empty.className = "memory-empty";
              empty.textContent = "No memories saved yet.";
              dom.memoryList.appendChild(empty);
              return;
            }
            data.memories.forEach((mem) => {
              const li = document.createElement("li");
              const text = document.createElement("span");
              const category = document.createElement("b");
              category.textContent = `[${mem.category || "Uncategorized"}]`;
              text.append(category, document.createTextNode(` ${mem.memory || ""}`));
              const remove = document.createElement("button");
              remove.className = "delete-memory-btn";
              remove.type = "button";
              remove.dataset.id = String(mem.id);
              remove.title = "Delete memory";
              remove.textContent = "❌";
              li.append(text, document.createTextNode(" "), remove);
              dom.memoryList.appendChild(li);
            });
            dom.memoryList.querySelectorAll(".delete-memory-btn").forEach((btn) => {
              btn.addEventListener("click", async () => {
                const memId = btn.getAttribute("data-id");
                await deleteMemory(memId);
              });
            });
          }
        }
      } catch (e) {
        console.log("Memory load skipped");
      }
    }

    async function deleteMemory(id) {
      try {
        const response = await fetch(`/api/memory/${id}`, { method: "DELETE", headers: getAuthHeaders() });
        if (!response.ok) throw new Error("Memory was not deleted.");
        await loadMemories();
      } catch (err) {
        console.error("Failed to delete memory", err);
      }
    }

    async function clearAllMemories() {
      try {
        const response = await fetch("/api/memory/all", { method: "DELETE", headers: getAuthHeaders() });
        if (!response.ok) throw new Error("Memories were not cleared.");
        await loadMemories();
      } catch (err) {
        console.error("Failed to clear memories", err);
      }
    }

    function speakText(text, btnEl) {
      if (!("speechSynthesis" in window)) {
        alert("Your browser does not support Text-to-Speech.");
        return;
      }

      if (btnEl && btnEl.dataset.speaking === "true") {
        window.speechSynthesis.cancel();
        const originalLabel = btnEl.dataset.originalLabel || "🔊 Read";
        btnEl.textContent = originalLabel;
        btnEl.dataset.speaking = "false";
        return;
      }

      window.speechSynthesis.cancel();
      document.querySelectorAll('[data-speaking="true"]').forEach((el) => {
        el.dataset.speaking = "false";
        if (el.dataset.originalLabel) el.textContent = el.dataset.originalLabel;
      });

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;

      if (btnEl) {
        const originalLabel = btnEl.dataset.originalLabel || btnEl.textContent;
        btnEl.dataset.originalLabel = originalLabel;
        btnEl.textContent = "🔊 Speaking...";
        btnEl.dataset.speaking = "true";
      }

      utterance.onend = () => {
        if (btnEl) {
          btnEl.textContent = btnEl.dataset.originalLabel || "🔊 Read";
          btnEl.dataset.speaking = "false";
        }
      };

      utterance.onerror = () => {
        if (btnEl) {
          btnEl.textContent = btnEl.dataset.originalLabel || "🔊 Read";
          btnEl.dataset.speaking = "false";
        }
      };

      try {
        window.speechSynthesis.speak(utterance);
      } catch (err) {
        console.error("TTS failed:", err);
        if (btnEl) {
          btnEl.textContent = btnEl.dataset.originalLabel || "🔊 Read";
          btnEl.dataset.speaking = "false";
        }
      }
    }

    function escapeHtml(str) {
      const div = document.createElement("div");
      div.textContent = str ?? "";
      return div.innerHTML;
    }

    // Inline SVG avatar data-URIs (presentation assets; theme-neutral)
    const USER_AVATAR_SRC = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='13' r='5' fill='%2394a3b8'/%3E%3Cpath d='M6 27c1.5-5.5 5.5-8 10-8s8.5 2.5 10 8' fill='%2394a3b8'/%3E%3C/svg%3E";
    const BOT_AVATAR_SRC = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%2338bdf8'/%3E%3Cstop offset='.55' stop-color='%23818cf8'/%3E%3Cstop offset='1' stop-color='%23c084fc'/%3E%3C/linearGradient%3E%3C/defs%3E%3Ccircle cx='16' cy='16' r='16' fill='url(%23g)'/%3E%3Ccircle cx='12' cy='12' r='4' fill='%23ffffff' opacity='.35'/%3E%3C/svg%3E";

    function renderMessage(role, text, time, sources) {
      const isUser = role === "user";
      const article = document.createElement("article");
      article.className = `message ${isUser ? "message-user" : "message-bot"}`;

      const avatar = document.createElement("img");
      avatar.className = "message-avatar";
      avatar.src = isUser ? USER_AVATAR_SRC : BOT_AVATAR_SRC;
      avatar.alt = isUser ? "User avatar" : "Isolde avatar";

      const content = document.createElement("div");
      content.className = "message-content";

      const textEl = document.createElement("div");
      textEl.className = "message-text";
      if (isUser) {
        textEl.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
      } else {
        if (typeof marked !== "undefined") {
          textEl.innerHTML = sanitizeHtml(marked.parse(text || ""));
        } else {
          textEl.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
        }
      }

      const timeEl = document.createElement("span");
      timeEl.className = "message-time";
      timeEl.textContent = formatTime(time || new Date());

      content.appendChild(textEl);
      content.appendChild(timeEl);

      if (!isUser) {
        if (sources && sources.length > 0) {
          const sourcesDiv = document.createElement("div");
          sourcesDiv.className = "message-sources";
          const label = document.createElement("strong");
          label.textContent = "📎 Sources: ";
          sourcesDiv.appendChild(label);
          sources.forEach((source, index) => {
            if (index) sourcesDiv.appendChild(document.createTextNode(", "));
            const item = document.createElement("span");
            item.textContent = String(source);
            sourcesDiv.appendChild(item);
          });
          content.appendChild(sourcesDiv);
        }

        const actionsDiv = document.createElement("div");
        actionsDiv.className = "message-actions";

        const copyBtn = document.createElement("button");
        copyBtn.className = "copy-message-btn";
        copyBtn.type = "button";
        copyBtn.title = "Copy message";
        copyBtn.textContent = "📋 Copy";
        copyBtn.addEventListener("click", () => copyMessage(text, copyBtn));
        actionsDiv.appendChild(copyBtn);

        const readBtn = document.createElement("button");
        readBtn.className = "read-message-btn";
        readBtn.type = "button";
        readBtn.title = "Read aloud";
        readBtn.textContent = "🔊 Read";
        readBtn.addEventListener("click", () => {
          const currentText = article.querySelector(".message-text")?.innerText || text;
          speakText(currentText, readBtn);
        });
        actionsDiv.appendChild(readBtn);

        const regenBtn = document.createElement("button");
        regenBtn.className = "regenerate-message-btn";
        regenBtn.type = "button";
        regenBtn.title = "Regenerate response";
        regenBtn.textContent = "↻ Regenerate";
        regenBtn.addEventListener("click", () => regenerateLastResponse());
        actionsDiv.appendChild(regenBtn);

        const likeBtn = document.createElement("button");
        likeBtn.className = "feedback-btn";
        likeBtn.type = "button";
        likeBtn.title = "Good response";
        likeBtn.textContent = "👍";
        const dislikeBtn = document.createElement("button");
        dislikeBtn.className = "feedback-btn";
        dislikeBtn.type = "button";
        dislikeBtn.title = "Bad response";
        dislikeBtn.textContent = "👎";

        likeBtn.addEventListener("click", () => {
          submitFeedback("Thumbs Up", "User liked the response");
          likeBtn.textContent = "✅";
          likeBtn.disabled = true;
          dislikeBtn.disabled = true;
        });
        dislikeBtn.addEventListener("click", () => {
          submitFeedback("Thumbs Down", "User disliked the response");
          dislikeBtn.textContent = "✅";
          likeBtn.disabled = true;
          dislikeBtn.disabled = true;
        });

        actionsDiv.appendChild(likeBtn);
        actionsDiv.appendChild(dislikeBtn);
        content.appendChild(actionsDiv);
      } else {
        const userActionsDiv = document.createElement("div");
        userActionsDiv.className = "message-actions message-actions-user";

        const editBtn = document.createElement("button");
        editBtn.className = "edit-user-msg-btn";
        editBtn.type = "button";
        editBtn.title = "Edit and resend this message";
        editBtn.textContent = "✏️ Edit";
        editBtn.addEventListener("mouseover", () => {
          editBtn.classList.add("is-hover");
        });
        editBtn.addEventListener("mouseout", () => {
          editBtn.classList.remove("is-hover");
        });
        editBtn.addEventListener("click", () => {
          if (dom.messageTextarea) {
            dom.messageTextarea.value = text;
            dom.messageTextarea.focus();
            const len = dom.messageTextarea.value.length;
            try { dom.messageTextarea.setSelectionRange(len, len); } catch (e) {}
            autoResizeTextarea();
            updateSendButtonState();
          }
        });

        userActionsDiv.appendChild(editBtn);
        content.appendChild(userActionsDiv);
      }

      article.appendChild(avatar);
      article.appendChild(content);
      dom.chatMessages.appendChild(article);
      return article;
    }

    function appendUserMessage(text) {
      const conversation = getActiveConversation();
      const time = new Date();
      conversation.messages.push({ role: "user", text, time: time.toISOString() });
      if (conversation.messages.length === 1) {
        conversation.title = deriveTitle(text);
      }
      hideWelcomeScreen();
      renderMessage("user", text, time);
      renderChatHistory();
      scrollToBottom();
      saveChat();
    }

    function appendBotMessage(text) {
      const conversation = getActiveConversation();
      const time = new Date();
      conversation.messages.push({ role: "bot", text, time: time.toISOString() });
      renderMessage("bot", text, time);
      scrollToBottom();
      saveChat();
    }

    function showTyping() {
      dom.typingIndicator?.classList.add("is-visible");
      if (dom.typingIndicator) dom.typingIndicator.style.display = "flex";
      scrollToBottom();
    }

    function hideTyping() {
      dom.typingIndicator?.classList.remove("is-visible");
      if (dom.typingIndicator) dom.typingIndicator.style.display = "none";
    }

    function setLoading(isLoading) {
      state.isLoading = isLoading;
      if (dom.sendBtn) dom.sendBtn.disabled = isLoading;
      if (isLoading) showTyping();
      else hideTyping();
      updateStopButtonVisibility();
    }

    function showBroadcastToast(message) {
      const toast = document.createElement("div");
      toast.className = "broadcast-toast";
      toast.textContent = "📢 " + message;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => { if (toast.parentNode) document.body.removeChild(toast); }, 500);
      }, 8000);
    }

    async function streamBotResponse(userText, botMsgObj, textEl) {
      const model = dom.modelSelect ? dom.modelSelect.value : "Flash-Lite Extended";
      const isNewChat = !state.backendConversationId;
      const controller = new AbortController();
      state.abortController = controller;
      state.streamingBotMsgObj = botMsgObj;
      state.streamingTextEl = textEl;

      let response;
      try {
        response = await fetch("/api/chat/stream", {
          method: "POST",
          headers: getAuthHeaders(true),
          body: JSON.stringify({
            message: userText,
            conversation_id: state.backendConversationId,
            model: model,
            web_search: state.webSearchEnabled,
            research_mode: state.webSearchEnabled ? "required" : "auto",
          }),
          signal: controller.signal,
        });
      } catch (err) {
        if (err.name === "AbortError") {
          botMsgObj.text = (botMsgObj.text || "") + "\n\n[Generation Stopped by User]";
          if (typeof marked !== "undefined") textEl.innerHTML = sanitizeHtml(marked.parse(botMsgObj.text));
          else textEl.innerHTML = escapeHtml(botMsgObj.text).replace(/\n/g, "<br>");
          state.abortController = null;
          state.streamingBotMsgObj = null;
          state.streamingTextEl = null;
          return;
        }
        throw err;
      }

      if (!response.ok) {
        state.abortController = null;
        state.streamingBotMsgObj = null;
        state.streamingTextEl = null;
        const errorData = await response.json().catch(() => ({}));
        if (response.status === 401) {
          sessionStorage.removeItem("access_token");
          sessionStorage.removeItem("user");
          window.location.assign("/login.html");
        }
        if (response.status === 429) throw new Error("Rate limit reached. Please wait before retrying.");
        throw new Error(errorData.error || "AI service unavailable.");
      }

      state.generationId = response.headers.get("X-Generation-ID");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = "";
      let wasAborted = false;
      let streamDone = false;
      let eventBuffer = "";

      try {
        while (true) {
          let readResult;
          try {
            readResult = await reader.read();
          } catch (err) {
            if (err.name === "AbortError" || controller.signal.aborted) {
              wasAborted = true;
              break;
            }
            throw err;
          }

          const { value, done } = readResult;
          if (done) break;

          eventBuffer += decoder.decode(value, { stream: true });
          const lines = eventBuffer.split("\n\n");
          eventBuffer = lines.pop() || "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataText = line.replace("data: ", "").trim();
              if (dataText === "[DONE]") { streamDone = true; break; }
              if (dataText === "[ERROR]") throw new Error("Streaming encountered an error.");
              if (dataText.startsWith("[SOURCES]")) {
                const sourcesRaw = dataText.substring(9).trim();
                if (sourcesRaw && botMsgObj) {
                  botMsgObj.sources = sourcesRaw.split(",").map(s => s.trim()).filter(Boolean);
                }
                continue;
              }
              let delta = dataText;
              try {
                const parsed = JSON.parse(dataText);
                if (parsed && typeof parsed.delta === "string") {
                  delta = parsed.delta;
                } else if (parsed && typeof parsed.event === "string" && parsed.event.startsWith("research_")) {
                  // Typed research events are provenance metadata, never model
                  // text. Keeping them out of the transcript avoids a source
                  // payload being rendered as an assistant response.
                  botMsgObj.research = botMsgObj.research || { citations: [], status: "" };
                  if (parsed.event === "research_citation" && parsed.citation) {
                    botMsgObj.research.citations.push(parsed.citation);
                  }
                  if (parsed.event === "research_completed") {
                    botMsgObj.research.status = parsed.status || "COMPLETED";
                  }
                  continue;
                }
              } catch (err) {}
              accumulatedText += delta;
              botMsgObj.text = accumulatedText;
              if (typeof marked !== "undefined") textEl.innerHTML = sanitizeHtml(marked.parse(accumulatedText));
              else textEl.innerHTML = escapeHtml(accumulatedText).replace(/\n/g, "<br>");
              requestAnimationFrame(() => scrollToBottom());
            }
          }

          if (streamDone || controller.signal.aborted) {
            if (controller.signal.aborted) wasAborted = true;
            break;
          }
        }
      } finally {
        try { reader.cancel(); } catch (e) {}
        state.abortController = null;
        state.streamingBotMsgObj = null;
        state.streamingTextEl = null;
        state.generationId = null;
      }

      if (wasAborted) {
        accumulatedText += "\n\n[Generation Stopped by User]";
        botMsgObj.text = accumulatedText;
        if (typeof marked !== "undefined") textEl.innerHTML = sanitizeHtml(marked.parse(accumulatedText));
        else textEl.innerHTML = escapeHtml(accumulatedText).replace(/\n/g, "<br>");
        return;
      }

      if (botMsgObj.sources && botMsgObj.sources.length > 0 && textEl) {
        const sourcesDiv = document.createElement("div");
        sourcesDiv.className = "message-sources";
        const label = document.createElement("strong");
        label.textContent = "📎 Sources: ";
        sourcesDiv.appendChild(label);
        botMsgObj.sources.forEach((source, index) => {
          if (index) sourcesDiv.appendChild(document.createTextNode(", "));
          const item = document.createElement("span");
          item.textContent = String(source);
          sourcesDiv.appendChild(item);
        });
        const messageContent = textEl.closest(".message-content");
        if (messageContent) messageContent.appendChild(sourcesDiv);
      }

      if (botMsgObj.research?.citations?.length > 0 && textEl) {
        const citationsDiv = document.createElement("div");
        citationsDiv.className = "message-sources research-citations";
        const label = document.createElement("strong");
        label.textContent = "🔎 Web research: ";
        citationsDiv.appendChild(label);
        botMsgObj.research.citations.forEach((citation, index) => {
          if (index) citationsDiv.appendChild(document.createTextNode(", "));
          const link = document.createElement("a");
          link.href = String(citation.url || "");
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = String(citation.title || citation.domain || "Source");
          citationsDiv.appendChild(link);
        });
        const messageContent = textEl.closest(".message-content");
        if (messageContent) messageContent.appendChild(citationsDiv);
      }

      if (isNewChat) {
        await loadHistory();
        const backendConvos = Object.values(state.conversations).filter((c) => c.isBackend);
        backendConvos.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
        const oldId = state.activeConversationId;
        if (backendConvos.length > 0 && oldId && state.conversations[oldId] && !state.conversations[oldId].isBackend) {
          const newestRealId = backendConvos[0].id;
          if (oldId !== newestRealId) {
            state.conversations[newestRealId].messages = state.conversations[oldId].messages;
            state.conversations[newestRealId].title = state.conversations[oldId].title || state.conversations[newestRealId].title;
            state.conversations[newestRealId].isPinned = state.conversations[oldId].isPinned || state.conversations[newestRealId].isPinned;
            delete state.conversations[oldId];
            state.activeConversationId = newestRealId;
            state.backendConversationId = newestRealId;
          }
        }
        renderChatHistory();
        saveChat();
      }

      loadMemories();
    }

    async function sendMessage(rawText) {
      const text = (rawText ?? dom.messageTextarea?.value ?? "").trim();
      if (!text || state.isLoading) return;

      appendUserMessage(text);
      resetTextarea();
      setLoading(true);

      const conversation = getActiveConversation();
      const time = new Date();
      const botMsgObj = { role: "bot", text: "", time: time.toISOString() };
      conversation.messages.push(botMsgObj);
      const botArticle = renderMessage("bot", "", time);
      const textEl = botArticle.querySelector(".message-text");

      try {
        await streamBotResponse(text, botMsgObj, textEl);
      } catch (err) {
        console.error("Isolde: failed to get a bot response.", err);
        botMsgObj.text = `⚠ ${err.message}`;
        textEl.innerHTML = escapeHtml(botMsgObj.text);
      } finally {
        setLoading(false);
        saveChat();
      }
    }

    async function regenerateLastResponse() {
      const conversation = getActiveConversation();
      if (!conversation || conversation.messages.length === 0 || state.isLoading) return;

      let lastUserMsgIndex = -1;
      for (let i = conversation.messages.length - 1; i >= 0; i--) {
        if (conversation.messages[i].role === "user") { lastUserMsgIndex = i; break; }
      }
      if (lastUserMsgIndex === -1) return;

      const lastUserText = conversation.messages[lastUserMsgIndex].text;
      conversation.messages = conversation.messages.slice(0, lastUserMsgIndex + 1);
      renderActiveConversation();
      setLoading(true);

      const time = new Date();
      const botMsgObj = { role: "bot", text: "", time: time.toISOString() };
      conversation.messages.push(botMsgObj);
      const botArticle = renderMessage("bot", "", time);
      const textEl = botArticle.querySelector(".message-text");

      try {
        await streamBotResponse(lastUserText, botMsgObj, textEl);
      } catch (err) {
        botMsgObj.text = `⚠ ${err.message || "Failed to regenerate response."}`;
        textEl.innerHTML = escapeHtml(botMsgObj.text);
      } finally {
        setLoading(false);
        saveChat();
      }
    }

    function clearChat() {
      const conversation = state.conversations[state.activeConversationId];
      if (!conversation) return;
      conversation.messages = [];
      conversation.title = "New conversation";
      dom.chatMessages.innerHTML = "";
      showWelcomeScreen();
      hideTyping();
      renderChatHistory();
      saveChat();
    }

    function autoResizeTextarea() {
      const textarea = dom.messageTextarea;
      if (!textarea) return;
      textarea.style.height = "auto";
      const nextHeight = Math.min(textarea.scrollHeight, MAX_TEXTAREA_HEIGHT);
      textarea.style.height = `${nextHeight}px`;
      textarea.style.overflowY = textarea.scrollHeight > MAX_TEXTAREA_HEIGHT ? "auto" : "hidden";
    }

    function resetTextarea() {
      const textarea = dom.messageTextarea;
      if (!textarea) return;
      textarea.value = "";
      textarea.style.height = "auto";
      textarea.style.overflowY = "hidden";
      updateSendButtonState();
    }

    function updateSendButtonState() {
      if (!dom.sendBtn || !dom.messageTextarea) return;
      const hasText = dom.messageTextarea.value.trim().length > 0;
      dom.sendBtn.disabled = !hasText || state.isLoading;
    }

    function startVoiceRecording() {
      if (!speechRecognition) { alert("Your browser does not support Voice Recognition."); return; }
      state.isRecording = true;
      dom.voiceInputBtn?.classList.add("is-recording");
      dom.voiceInputBtn?.setAttribute("title", "Stop recording");
      try { speechRecognition.start(); } catch (e) {}
    }

    function stopVoiceRecording() {
      state.isRecording = false;
      dom.voiceInputBtn?.classList.remove("is-recording");
      dom.voiceInputBtn?.setAttribute("title", "Voice input");
      if (speechRecognition) { try { speechRecognition.stop(); } catch (e) {} }
    }

    function toggleVoiceRecording() {
      if (state.isRecording) stopVoiceRecording();
      else startVoiceRecording();
    }

    async function handleFileSelected(event) {
      const file = event.target.files?.[0];
      if (!file || state.isLoading) {
        if (event.target) event.target.value = "";
        return;
      }
      if (dom.attachmentMenu) dom.attachmentMenu.classList.remove("show");

      const formData = new FormData();
      formData.append("file", file);
      setLoading(true);

      try {
        appendBotMessage(`Uploading **${file.name}** for RAG document analysis...`);
        const response = await fetch("/api/rag/upload", {
          method: "POST",
          headers: { Authorization: `Bearer ${sessionStorage.getItem("access_token") || ""}` },
          body: formData,
        });
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) {
          sessionStorage.removeItem("access_token"); sessionStorage.removeItem("user");
          window.location.assign("/login.html"); return;
        }
        if (response.ok && data.status === "success") {
          appendBotMessage(`✅ Document **${file.name}** Indexed successfully! You can now ask questions about this document.`);
        } else {
          appendBotMessage(`⚠ Failed to upload document: ${data.message || data.error || `HTTP ${response.status}`}`);
        }
      } catch (err) {
        console.error("File upload error:", err);
        appendBotMessage("⚠ Network error during file upload.");
      } finally {
        setLoading(false);
        if (event.target) event.target.value = "";
      }
    }

    async function copyMessage(text, buttonEl) {
      try {
        await navigator.clipboard.writeText(text);
        showCopyFeedback(buttonEl);
      } catch (err) {
        fallbackCopy(text);
        showCopyFeedback(buttonEl);
      }
    }

    function fallbackCopy(text) {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      try { document.execCommand("copy"); } catch (err) {}
      document.body.removeChild(textarea);
    }

    function showCopyFeedback(buttonEl) {
      if (!buttonEl) return;
      const originalLabel = buttonEl.dataset.originalLabel ?? buttonEl.textContent;
      buttonEl.dataset.originalLabel = originalLabel;
      buttonEl.textContent = "✓ Copied!";
      clearTimeout(buttonEl._copyResetTimer);
      buttonEl._copyResetTimer = setTimeout(() => { buttonEl.textContent = originalLabel; }, COPY_FEEDBACK_DURATION);
    }

    async function logout() {
      try { await fetch("/api/logout", { method: "POST", headers: getAuthHeaders() }); } catch (e) {}
      sessionStorage.removeItem("access_token");
      sessionStorage.removeItem("user");
      clearLegacyPersistentState();
      window.location.href = "login.html";
    }

    function bindEvents() {
      if (dom.chatSearchInput) {
        dom.chatSearchInput.addEventListener("input", (e) => { state.searchQuery = e.target.value; renderChatHistory(); });
      }

      dom.messageForm?.addEventListener("submit", (event) => { event.preventDefault(); sendMessage(); });

      dom.messageTextarea?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); }
      });

      dom.messageTextarea?.addEventListener("input", () => { autoResizeTextarea(); updateSendButtonState(); });

      dom.suggestionChips?.forEach((chip) => { chip.addEventListener("click", () => { sendMessage(chip.textContent.trim()); }); });

      dom.newChatBtn?.addEventListener("click", () => { createConversation(); });
      dom.clearChatBtn?.addEventListener("click", () => { clearChat(); });
      dom.themeToggleBtn?.addEventListener("click", () => { toggleTheme(); });
      dom.voiceInputBtn?.addEventListener("click", () => { toggleVoiceRecording(); });
      dom.fileUploadInput?.addEventListener("change", handleFileSelected);

      if (dom.logoutBtn) dom.logoutBtn.addEventListener("click", () => { logout(); });
      dom.clearAllMemoriesBtn?.addEventListener("click", () => { clearAllMemories(); });

      if (dom.toggleAttachmentBtn && dom.attachmentMenu) {
        dom.toggleAttachmentBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          dom.attachmentMenu.classList.toggle("show");
        });
      }

      document.addEventListener("click", (event) => {
        if (dom.attachmentMenu && dom.attachmentMenu.classList.contains("show")) {
          if (!event.target.closest(".attachment-wrapper")) dom.attachmentMenu.classList.remove("show");
        }
      });

      if (dom.sidebarToggleBtn && dom.appSidebar) {
        dom.sidebarToggleBtn.addEventListener("click", (e) => {
          e.preventDefault();
          dom.appSidebar.classList.toggle("collapsed");
        });
      }
    }

    async function loadProfile() {
      try {
        const response = await fetch("/api/profile", {
          headers: getAuthHeaders()
        });
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        const user =
          payload &&
          typeof payload === "object" &&
          "data" in payload
            ? payload.data || {}
            : payload;
        if (dom.sidebarUserName) {
          dom.sidebarUserName.textContent = user.name || user.username || "User";
        }
        if (dom.sidebarUserEmail) {
          dom.sidebarUserEmail.textContent = user.email || "user@example.com";
        }
      } catch (e) {}
    }

    const userProfileEl = document.querySelector(".user-profile");
    if (userProfileEl) {
      userProfileEl.style.cursor = "pointer";
      userProfileEl.addEventListener("click", () => {
        const userName = dom.sidebarUserName?.textContent || "User";
        const userEmail = dom.sidebarUserEmail?.textContent || "user@example.com";
        let profileModal = document.getElementById("user-profile-modal");
        if (!profileModal) {
          profileModal = document.createElement("div");
          profileModal.id = "user-profile-modal";
          profileModal.innerHTML = `
            <div class="profile-card">
              <div class="profile-avatar">👤</div>
              <h3 class="profile-name">${escapeHtml(userName)}</h3>
              <p class="profile-email">${escapeHtml(userEmail)}</p>
              <div class="profile-plan">Plan details are available in Billing.</div>
              <button id="close-profile-modal" class="profile-close-btn" type="button">Close</button>
              <button id="modal-logout-btn" class="profile-logout-btn" type="button">Logout</button>
            </div>`;
          document.body.appendChild(profileModal);
          profileModal.querySelector("#close-profile-modal").addEventListener("click", () => { profileModal.style.display = "none"; });
          profileModal.querySelector("#modal-logout-btn").addEventListener("click", () => { logout(); });
          profileModal.addEventListener("click", (e) => { if (e.target === profileModal) profileModal.style.display = "none"; });
        } else {
          profileModal.style.display = "flex";
        }
      });
    }

    async function loadHistory() {
      try {
        const response = await fetch("/api/history", { headers: getAuthHeaders() });
        if (response.ok) {
          const data = await response.json();
          (data.conversations || []).forEach((convo) => {
            if (!state.conversations[convo.id]) {
              state.conversations[convo.id] = {
                id: convo.id,
                title: convo.title,
                created_at: convo.created_at,
                isBackend: true,
                isPinned: convo.is_pinned || false,
                messages: [],
              };
            } else {
              state.conversations[convo.id].title = convo.title;
              state.conversations[convo.id].isPinned = convo.is_pinned || false;
              state.conversations[convo.id].created_at = convo.created_at;
              state.conversations[convo.id].isBackend = true;
            }
          });
          renderChatHistory();
        }
      } catch (e) {}
    }

    async function initializeApp() {
      bindDomElements();
      loadPreferences();
      restoreTheme();
      loadChat();
      await loadProfile();
      await loadHistory();
      await loadMemories();

      if (!state.activeConversationId || !state.conversations[state.activeConversationId]) {
        createConversation();
      } else {
        if (state.conversations[state.activeConversationId].isBackend) state.backendConversationId = state.activeConversationId;
        else state.backendConversationId = null;
        if (state.conversations[state.activeConversationId].isBackend && state.conversations[state.activeConversationId].messages.length === 0) {
          await loadConversationMessages(state.activeConversationId);
        }
        renderChatHistory();
        renderActiveConversation();
      }

      if (dom.modelSelect && preferences.defaultModel) {
        const optionExists = Array.from(dom.modelSelect.options).some((o) => o.value === preferences.defaultModel);
        if (optionExists) dom.modelSelect.value = preferences.defaultModel;
      }

      updateSendButtonState();
      bindEvents();
      injectDynamicButtons();
      try {
        const response = await fetch("/api/capabilities", { headers: getAuthHeaders() });
        if (response.ok) {
          state.capabilities = (await response.json()).capabilities || {};
          if (dom.webSearchToggleBtn && state.capabilities.research !== "AVAILABLE") {
            state.webSearchEnabled = false;
            dom.webSearchToggleBtn.disabled = true;
            dom.webSearchToggleBtn.textContent = "🌐 Web: Unavailable";
            dom.webSearchToggleBtn.title = "Web research is not configured on the server";
          }
        }
      } catch (_) {
        if (dom.webSearchToggleBtn) {
          dom.webSearchToggleBtn.disabled = true;
          dom.webSearchToggleBtn.textContent = "🌐 Web: Unavailable";
        }
      }
      updateStopButtonVisibility();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initializeApp);
    else initializeApp();
  }
})();

/* ==========================================================================
   AI STUDIO WORKSPACE (Images / Videos) — logic unchanged
   ========================================================================== */
function onDocumentReady(fn) {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
  else fn();
}

async function applyPublicProductConfiguration() {
  try {
    const response = await fetch("/api/product/config");
    if (!response.ok) return;
    const config = await response.json();
    const features = config.features || {};
    const visibility = {
      ai_studio: "ai-studio-nav",
      workflows: "workflows-nav",
      files_rag: "smart-library-btn",
      billing: "billing-nav",
      organization: "organization-nav",
      image: "images-studio-btn",
      video: "videos-gen-btn",
    };
    Object.entries(visibility).forEach(([feature, id]) => {
      const element = document.getElementById(id);
      if (element && features[feature] === false) element.hidden = true;
    });
    const branding = config.branding || {};
    document.querySelectorAll(".brand-name").forEach((element) => {
      element.textContent = branding.application_name || "Isolde AI";
    });
    const footer = document.querySelector(".app-footer .disclaimer");
    if (footer && branding.footer_text) footer.textContent = branding.footer_text;
    if (branding.announcement) {
      const banner = document.createElement("div");
      banner.className = "product-announcement";
      banner.setAttribute("role", "status");
      banner.textContent = branding.announcement;
      document.querySelector(".main-content")?.prepend(banner);
    }
  } catch (_) {
    // Safe built-in branding and feature defaults remain active.
  }
}

onDocumentReady(applyPublicProductConfiguration);

onDocumentReady(() => {
  const imgStudioBtn = document.getElementById("images-studio-btn");
  const vidGenBtn = document.getElementById("videos-gen-btn");
  const modal = document.getElementById("ai-studio-workspace-modal");
  const title = document.getElementById("studio-modal-title");
  const desc = document.getElementById("studio-modal-desc");
  const input = document.getElementById("studio-prompt-input");
  const closeBtn = document.getElementById("close-studio-modal");
  const runBtn = document.getElementById("run-generation-btn");
  const resultContainer = document.getElementById("studio-result-container");
  const loader = document.getElementById("studio-loader");
  const imgOutput = document.getElementById("generated-image-output");

  if (input) {
    ["keydown", "keyup", "keypress", "input"].forEach((evt) => { input.addEventListener(evt, (e) => e.stopPropagation()); });
  }

  async function openWorkspace(type, e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    if (!modal) return;

    if (type === "image") {
      if (title) title.textContent = "ISOLDE AI IMAGE";
      if (input) input.placeholder = "e.g., A futuristic cyberpunk city in neon lights, 4k...";
    } else {
      if (title) title.textContent = "ISOLDE AI VIDEO";
      if (input) input.placeholder = "e.g., Drone shot flying across snow-capped mountains at sunrise...";
    }

    if (input) input.value = "";
    if (resultContainer) resultContainer.style.display = "none";
    modal.style.display = "flex";
    if (runBtn) runBtn.disabled = true;
    if (desc) desc.textContent = "Checking provider capability…";
    try {
      const response = await fetch("/api/studio/capabilities", { headers: getAuthHeaders() });
      const data = await response.json().catch(() => ({}));
      if (response.status === 401) {
        sessionStorage.removeItem("access_token");
        sessionStorage.removeItem("user");
        window.location.replace("/login.html");
        return;
      }
      const capability = type === "image" ? data.image : data.video;
      if (capability === "READY") {
        if (desc) desc.textContent = "Provider ready.";
        if (runBtn) runBtn.disabled = false;
      } else if (desc) {
        desc.textContent = capability === "NOT_SUPPORTED"
          ? "Configured provider is not supported — NOT_SUPPORTED"
          : "Provider not configured — NOT_CONFIGURED";
      }
    } catch (_) {
      if (desc) desc.textContent = "Capability check unavailable. Retry by reopening this panel.";
    }
    setTimeout(() => { if (input) input.focus(); }, 100);
  }

  if (imgStudioBtn) imgStudioBtn.addEventListener("click", (e) => openWorkspace("image", e));

  if (vidGenBtn) vidGenBtn.addEventListener("click", (e) => openWorkspace("video", e));

  if (closeBtn && modal) {
    closeBtn.addEventListener("click", (e) => { e.stopPropagation(); modal.style.display = "none"; });
    modal.addEventListener("click", (e) => { if (e.target === modal) modal.style.display = "none"; });
  }

  if (runBtn) {
    runBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const promptText = input ? input.value.trim() : "";
      if (!promptText) { alert("Please enter a prompt description first!"); return; }

      if (resultContainer) resultContainer.style.display = "block";
      if (loader) loader.style.display = "block";
      if (imgOutput) imgOutput.style.display = "none";

      try {
        const isImage = title && title.textContent.includes("IMAGE");
        const endpoint = isImage ? "/api/studio/generate-image" : "/api/studio/generate-video";
        const res = await fetch(endpoint, {
          method: "POST",
          headers: getAuthHeaders(),
          body: JSON.stringify({ prompt: promptText }),
        });
        const data = await res.json();

        if (res.ok && data.status === "success" && (data.image_url || data.video_url)) {
          if (loader) loader.style.display = "none";
          if (isImage && imgOutput) { imgOutput.src = data.image_url; imgOutput.style.display = "block"; }
          else if (loader) { loader.style.display = "block"; loader.textContent = `Video ready: ${data.video_url}`; }
        } else if (res.ok && data.status === "success") {
          if (loader) loader.textContent = "⚠ Provider response did not include a generated asset.";
        } else if (loader) {
          loader.textContent = "⚠ " + (data.message || data.error || "Generation is not configured.");
        }
      } catch (err) {
        if (loader) loader.textContent = "⚠ Network connection error during generation.";
      }
    });
  }
});

/* Attachment menu delegation (Create image / Create video) — unchanged */
document.addEventListener("click", (e) => {
  const attachMenu = document.getElementById("attachment-menu");
  if (!attachMenu || !attachMenu.contains(e.target)) return;
  const target = e.target.closest("li, a, button, span, div, label");
  if (!target) return;
  const text = target.textContent || "";
  if (text.includes("Create image") || text.includes("Create video")) {
    e.preventDefault();
    e.stopPropagation();
    attachMenu.classList.remove("show");
    if (text.includes("Create image")) {
      const imgBtn = document.getElementById("images-studio-btn");
      if (imgBtn) imgBtn.click();
    } else if (text.includes("Create video")) {
      const vidBtn = document.getElementById("videos-gen-btn");
      if (vidBtn) vidBtn.click();
    }
  }
});

/* ==========================================================================
   DYNAMIC SETTINGS MODAL — logic unchanged; inline dark styles moved to CSS
   ========================================================================== */
document.addEventListener("click", async (e) => {
  const target = e.target.closest("button, a, div, span, li");
  if (!target) return;
  const text = target.textContent ? target.textContent.trim().toLowerCase() : "";
  const id = target.id ? target.id.toLowerCase() : "";

  if (text === "settings" || id.includes("setting") || text.includes("settings")) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    document.querySelectorAll("#settings-modal, .settings-modal-overlay, div[id*='pref'], div[id*='global']").forEach((m) => m.remove());

    const overlay = document.createElement("div");
    overlay.id = "settings-modal";
    overlay.className = "settings-modal-overlay show";

    overlay.innerHTML = `
    <div class="settings-modal-card">
      <div class="settings-modal-rail">
        <div class="settings-modal-rail-close">
          <button id="modal-close-x" type="button" aria-label="Close settings">✕</button>
        </div>
        <button class="s-tab is-active" data-tab="general" type="button">General</button>
        <button class="s-tab" data-tab="notifications" type="button">Notifications</button>
        <button class="s-tab" data-tab="personalization" type="button">Personalization</button>
        <button class="s-tab" data-tab="security" type="button">Security and login</button>
        <button class="s-tab" data-tab="account" type="button">Account</button>
      </div>
      <div class="settings-modal-pane">
        <!-- General Panel -->
        <div class="s-panel" data-panel="general" style="display:block;">
          <h2>General Preferences</h2>
          <div class="settings-row-item">
            <span>Appearance Theme</span>
            <select id="settings-theme">
              <option value="dark">Dark Glass</option>
              <option value="light">Light Clean</option>
            </select>
          </div>
          <div class="settings-row-item">
            <span>Workspace Language</span>
            <select id="settings-general-language"></select>
          </div>
          <div id="settings-general-status" role="status" aria-live="polite"></div>
          <div class="settings-action-row">
            <button id="export-json-btn" class="btn-accent" type="button">Export Conversation Data (JSON)</button>
            <button id="delete-chats-btn" class="btn-danger" type="button">Delete All Chats</button>
          </div>
        </div>
        <!-- Notifications Panel -->
        <div class="s-panel" data-panel="notifications" style="display:none;">
          <h2>Notifications</h2>
          <p class="settings-panel-desc">Configure how you receive push and email alerts across your workspace.</p>
          <label class="settings-row-item settings-row-check">
            <span>Email Notifications</span>
            <input id="settings-email-notifications" type="checkbox">
          </label>
          <label class="settings-row-item settings-row-check">
            <span>Push Notifications</span>
            <input id="settings-push-notifications" type="checkbox">
          </label>
          <div id="settings-notifications-status" role="status" aria-live="polite"></div>
        </div>
        <!-- Personalization Panel -->
        <div class="s-panel" data-panel="personalization" style="display:none;">
          <h2>Personalization</h2>
          <p class="settings-panel-desc">Manage language, voice, and custom AI context.</p>
          <div class="settings-row-item">
            <span>Preferred Language</span>
            <select id="settings-personalization-language"></select>
          </div>
          <div class="settings-row-item">
            <span>Preferred Voice</span>
            <input id="settings-preferred-voice" type="text" placeholder="default">
          </div>
          <div class="settings-row-block">
            <span>Persona Notes</span>
            <textarea id="settings-persona-notes" rows="5" placeholder="Example: Prefer concise answers. Use professional tone."></textarea>
          </div>
          <div id="settings-personalization-status" role="status" aria-live="polite"></div>
        </div>
        <!-- Security Panel -->
        <div class="s-panel" data-panel="security" style="display:none;">
          <h2>Security and Login</h2>
          <p class="settings-panel-desc">Change your account password.</p>
          <div class="settings-stack">
            <input id="settings-old-password" type="password" placeholder="Current password" autocomplete="current-password">
            <input id="settings-new-password" type="password" placeholder="New password" autocomplete="new-password">
            <input id="settings-confirm-password" type="password" placeholder="Confirm new password" autocomplete="new-password">
            <button id="settings-change-password-btn" class="btn-accent" type="button">Change Password</button>
            <div id="settings-security-status" role="status" aria-live="polite"></div>
          </div>
        </div>
        <!-- Account Panel -->
        <div class="s-panel" data-panel="account" style="display:none;">
          <h2>Account Information</h2>
          <div class="settings-stack">
            <div class="settings-field-block">
              <label for="settings-account-name">Name</label>
              <input id="settings-account-name" type="text" placeholder="Your name">
            </div>
            <div class="settings-field-block">
              <label for="settings-account-email">Email</label>
              <input id="settings-account-email" type="email" placeholder="you@example.com">
            </div>
            <button id="settings-save-profile-btn" class="btn-accent" type="button">Save Profile</button>
            <div class="settings-danger-zone">
              <h3>Danger Zone</h3>
              <p>Deleting your account permanently removes your chats, memories, and uploaded documents.</p>
              <button id="settings-delete-account-btn" class="btn-danger" type="button">Delete Account</button>
            </div>
            <div id="settings-account-status" role="status" aria-live="polite"></div>
          </div>
        </div>
      </div>
    </div>`;

    document.body.appendChild(overlay);

    const closeModal = () => overlay.remove();
    overlay.querySelector("#modal-close-x").addEventListener("click", closeModal);
    overlay.addEventListener("click", (ev) => { if (ev.target === overlay) closeModal(); });

    const tabs = overlay.querySelectorAll(".s-tab");
    const panels = overlay.querySelectorAll(".s-panel");
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const targetPanel = tab.getAttribute("data-tab");
        tabs.forEach((t) => { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        panels.forEach((p) => { p.style.display = p.getAttribute("data-panel") === targetPanel ? "block" : "none"; });
      });
    });

    const NOTIFICATION_STORAGE_KEY = "isolde-notification-settings";
    const THEME_STORAGE_KEY = "isolde-theme";

    let currentSettings = {
      preferred_language: "en",
      preferred_voice: "default",
      persona_notes: "",
      email_notifications: true,
      push_notifications: true,
      mfa_enabled: false,
    };

    const themeSelect = overlay.querySelector("#settings-theme");
    const generalLanguageSelect = overlay.querySelector("#settings-general-language");
    const generalStatus = overlay.querySelector("#settings-general-status");
    const emailNotificationsCheckbox = overlay.querySelector("#settings-email-notifications");
    const pushNotificationsCheckbox = overlay.querySelector("#settings-push-notifications");
    const notificationsStatus = overlay.querySelector("#settings-notifications-status");
    const personalizationLanguageSelect = overlay.querySelector("#settings-personalization-language");
    const preferredVoiceInput = overlay.querySelector("#settings-preferred-voice");
    const personaNotesInput = overlay.querySelector("#settings-persona-notes");
    const personalizationStatus = overlay.querySelector("#settings-personalization-status");
    const oldPasswordInput = overlay.querySelector("#settings-old-password");
    const newPasswordInput = overlay.querySelector("#settings-new-password");
    const confirmPasswordInput = overlay.querySelector("#settings-confirm-password");
    const changePasswordBtn = overlay.querySelector("#settings-change-password-btn");
    const securityStatus = overlay.querySelector("#settings-security-status");
    const accountNameInput = overlay.querySelector("#settings-account-name");
    const accountEmailInput = overlay.querySelector("#settings-account-email");
    const saveProfileBtn = overlay.querySelector("#settings-save-profile-btn");
    const deleteAccountBtn = overlay.querySelector("#settings-delete-account-btn");
    const accountStatus = overlay.querySelector("#settings-account-status");

    const languageOptions = [
      { value: "en", label: "English" },
      { value: "ta", label: "Tamil" },
      { value: "hi", label: "Hindi" },
      { value: "te", label: "Telugu" },
      { value: "ml", label: "Malayalam" },
      { value: "kn", label: "Kannada" },
      { value: "fr", label: "French" },
      { value: "de", label: "German" },
      { value: "es", label: "Spanish" },
      { value: "ar", label: "Arabic" },
      { value: "ja", label: "Japanese" },
      { value: "ko", label: "Korean" },
      { value: "zh", label: "Chinese" },
    ];

    function showSettingsStatus(el, type, message) {
      if (!el) {
        return;
      }
      el.textContent = message || "";
      el.style.color = type === "error" ? "#f87171" : "#4ade80";
    }

    function normalizeSettingsResult(payload) {
      if (!payload || typeof payload !== "object") {
        return {
          success: true,
          message: "",
          data: payload,
        };
      }
      if ("success" in payload) {
        return {
          success: Boolean(payload.success),
          message: payload.message || payload.error || payload.msg || "",
          data: "data" in payload ? payload.data : payload,
        };
      }
      return {
        success: true,
        message: "",
        data: payload,
      };
    }

    async function settingsApi(method, url, body) {
      const headers = {};
      const token = sessionStorage.getItem("access_token");
      if (token && token !== "null" && token !== "undefined") {
        headers["Authorization"] = `Bearer ${token}`;
      }
      if (body !== undefined) {
        headers["Content-Type"] = "application/json";
      }

      let response;
      try {
        response = await fetch(url, {
          method,
          headers,
          body: body === undefined ? undefined : JSON.stringify(body),
        });
      } catch (err) {
        throw {
          success: false,
          message: "Network error. Please try again.",
        };
      }

      let payload = null;
      try {
        payload = await response.json();
      } catch (err) {
        payload = null;
      }

      const normalized = normalizeSettingsResult(payload);
      if (!response.ok || normalized.success === false) {
        throw {
          success: false,
          message: normalized.message || "Request failed.",
          status: response.status,
          data: normalized.data,
        };
      }
      return normalized;
    }

    function getSettingsData(result) {
      if (result && result.data && typeof result.data === "object") {
        return result.data;
      }
      return {};
    }

    function getLocalNotificationSettings() {
      try {
        return JSON.parse(sessionStorage.getItem(NOTIFICATION_STORAGE_KEY) || "{}");
      } catch (err) {
        return {};
      }
    }

    function persistLocalNotificationSettings(payload) {
      const existing = getLocalNotificationSettings();
      const next = { ...existing };
      Object.keys(payload).forEach((key) => {
        if (
          key === "email_notifications" ||
          key === "push_notifications" ||
          key === "mfa_enabled"
        ) {
          next[key] = Boolean(payload[key]);
        }
      });
      sessionStorage.setItem(NOTIFICATION_STORAGE_KEY, JSON.stringify(next));
    }

    function populateLanguageSelect(select, value) {
      if (!select) {
        return;
      }
      select.innerHTML = "";
      languageOptions.forEach((option) => {
        const optionEl = document.createElement("option");
        optionEl.value = option.value;
        optionEl.textContent = option.label;
        select.appendChild(optionEl);
      });
      const hasValue = Array.from(select.options).some(
        (option) => option.value === value
      );
      select.value = hasValue ? value : "en";
    }

    function applySettingsTheme(theme) {
      const nextTheme = theme === "light" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", nextTheme);
      sessionStorage.setItem(THEME_STORAGE_KEY, nextTheme);
      const themeToggleBtn = document.querySelector(".theme-toggle-btn");
      if (themeToggleBtn) {
        themeToggleBtn.setAttribute("data-theme", nextTheme);
        themeToggleBtn.setAttribute(
          "title",
          nextTheme === "dark"
            ? "Switch to light mode"
            : "Switch to dark mode"
        );
      }
    }

    async function saveSettings(payload, statusEl, successMessage) {
      const apiPayload = { ...payload };
      const onlyNotificationFields = Object.keys(payload).every(
        (key) =>
          key === "email_notifications" ||
          key === "push_notifications" ||
          key === "mfa_enabled"
      );
      if (onlyNotificationFields) {
        apiPayload.preferred_language =
          currentSettings.preferred_language || "en";
      }
      try {
        const result = await settingsApi("PATCH", "/api/settings", apiPayload);
        Object.assign(currentSettings, payload);
        persistLocalNotificationSettings(payload);
        showSettingsStatus(
          statusEl,
          "success",
          result.message || successMessage || "Settings saved."
        );
        return true;
      } catch (err) {
        showSettingsStatus(
          statusEl,
          "error",
          err.message || "Failed to save settings."
        );
        return false;
      }
    }

    async function loadSettings() {
      try {
        const result = await settingsApi("GET", "/api/settings");
        const settings = getSettingsData(result);
        const localNotifications = getLocalNotificationSettings();

        currentSettings = {
          preferred_language: settings.preferred_language || "en",
          preferred_voice: settings.preferred_voice || "default",
          persona_notes: settings.persona_notes || "",
          email_notifications:
            typeof settings.email_notifications === "boolean"
              ? settings.email_notifications
              : typeof localNotifications.email_notifications === "boolean"
                ? localNotifications.email_notifications
                : true,
          push_notifications:
            typeof settings.push_notifications === "boolean"
              ? settings.push_notifications
              : typeof localNotifications.push_notifications === "boolean"
                ? localNotifications.push_notifications
                : true,
          mfa_enabled:
            typeof settings.mfa_enabled === "boolean"
              ? settings.mfa_enabled
              : false,
        };

        populateLanguageSelect(
          generalLanguageSelect,
          currentSettings.preferred_language
        );
        populateLanguageSelect(
          personalizationLanguageSelect,
          currentSettings.preferred_language
        );

        if (preferredVoiceInput) {
          preferredVoiceInput.value = currentSettings.preferred_voice;
        }
        if (personaNotesInput) {
          personaNotesInput.value = currentSettings.persona_notes;
        }
        if (emailNotificationsCheckbox) {
          emailNotificationsCheckbox.checked =
            currentSettings.email_notifications;
        }
        if (pushNotificationsCheckbox) {
          pushNotificationsCheckbox.checked =
            currentSettings.push_notifications;
        }

        const savedTheme =
          sessionStorage.getItem(THEME_STORAGE_KEY) ||
          document.documentElement.getAttribute("data-theme") ||
          "dark";
        if (themeSelect) {
          themeSelect.value = savedTheme === "light" ? "light" : "dark";
        }
      } catch (err) {
        showSettingsStatus(
          generalStatus,
          "error",
          err.message || "Failed to load settings."
        );
      }
    }

    async function loadAccount() {
      try {
        const result = await settingsApi("GET", "/api/profile");
        const profile = getSettingsData(result);
        if (accountNameInput) {
          accountNameInput.value = profile.name || "";
        }
        if (accountEmailInput) {
          accountEmailInput.value = profile.email || "";
        }
      } catch (err) {
        showSettingsStatus(
          accountStatus,
          "error",
          err.message || "Failed to load profile."
        );
      }
    }

    if (themeSelect) {
      themeSelect.addEventListener("change", () => {
        applySettingsTheme(themeSelect.value);
        showSettingsStatus(generalStatus, "success", "Appearance updated.");
      });
    }

    if (generalLanguageSelect) {
      generalLanguageSelect.addEventListener("change", async () => {
        if (personalizationLanguageSelect) {
          personalizationLanguageSelect.value = generalLanguageSelect.value;
        }
        await saveSettings(
          { preferred_language: generalLanguageSelect.value },
          generalStatus,
          "Workspace language updated."
        );
      });
    }

    if (emailNotificationsCheckbox) {
      emailNotificationsCheckbox.addEventListener("change", async () => {
        await saveSettings(
          { email_notifications: emailNotificationsCheckbox.checked },
          notificationsStatus,
          "Email notification setting saved."
        );
      });
    }

    if (pushNotificationsCheckbox) {
      pushNotificationsCheckbox.addEventListener("change", async () => {
        if (
          pushNotificationsCheckbox.checked &&
          "Notification" in window &&
          Notification.permission === "default"
        ) {
          try {
            await Notification.requestPermission();
          } catch (err) {}
        }
        await saveSettings(
          { push_notifications: pushNotificationsCheckbox.checked },
          notificationsStatus,
          "Push notification setting saved."
        );
      });
    }

    if (personalizationLanguageSelect) {
      personalizationLanguageSelect.addEventListener("change", async () => {
        if (generalLanguageSelect) {
          generalLanguageSelect.value = personalizationLanguageSelect.value;
        }
        await saveSettings(
          { preferred_language: personalizationLanguageSelect.value },
          personalizationStatus,
          "Preferred language updated."
        );
      });
    }

    if (preferredVoiceInput) {
      preferredVoiceInput.addEventListener("change", async () => {
        await saveSettings(
          { preferred_voice: preferredVoiceInput.value.trim() || "default" },
          personalizationStatus,
          "Preferred voice updated."
        );
      });
    }

    let personaTimer = null;
    if (personaNotesInput) {
      personaNotesInput.addEventListener("input", () => {
        clearTimeout(personaTimer);
        personaTimer = setTimeout(() => {
          saveSettings(
            { persona_notes: personaNotesInput.value },
            personalizationStatus,
            "Persona notes updated."
          );
        }, 800);
      });
      personaNotesInput.addEventListener("blur", () => {
        clearTimeout(personaTimer);
        saveSettings(
          { persona_notes: personaNotesInput.value },
          personalizationStatus,
          "Persona notes updated."
        );
      });
    }

    if (changePasswordBtn) {
      changePasswordBtn.addEventListener("click", async () => {
        const oldPassword = oldPasswordInput ? oldPasswordInput.value : "";
        const newPassword = newPasswordInput ? newPasswordInput.value : "";
        const confirmPassword = confirmPasswordInput
          ? confirmPasswordInput.value
          : "";

        if (!oldPassword || !newPassword || !confirmPassword) {
          showSettingsStatus(
            securityStatus,
            "error",
            "All password fields are required."
          );
          return;
        }
        if (newPassword.length < 8) {
          showSettingsStatus(
            securityStatus,
            "error",
            "New password must be at least 8 characters long."
          );
          return;
        }
        if (!/[A-Za-z]/.test(newPassword) || !/[0-9]/.test(newPassword)) {
          showSettingsStatus(
            securityStatus,
            "error",
            "New password must contain at least one letter and one number."
          );
          return;
        }
        if (newPassword !== confirmPassword) {
          showSettingsStatus(
            securityStatus,
            "error",
            "New password and confirm password do not match."
          );
          return;
        }

        changePasswordBtn.disabled = true;
        try {
          const result = await settingsApi("POST", "/api/settings/password", {
            old_password: oldPassword,
            new_password: newPassword,
            confirm_password: confirmPassword,
          });
          if (oldPasswordInput) {
            oldPasswordInput.value = "";
          }
          if (newPasswordInput) {
            newPasswordInput.value = "";
          }
          if (confirmPasswordInput) {
            confirmPasswordInput.value = "";
          }
          showSettingsStatus(
            securityStatus,
            "success",
            result.message || "Password changed successfully."
          );
        } catch (err) {
          showSettingsStatus(
            securityStatus,
            "error",
            err.message || "Failed to change password."
          );
        } finally {
          changePasswordBtn.disabled = false;
        }
      });
    }

    if (saveProfileBtn) {
      saveProfileBtn.addEventListener("click", async () => {
        const name = accountNameInput ? accountNameInput.value.trim() : "";
        const email = accountEmailInput ? accountEmailInput.value.trim() : "";

        if (!name) {
          showSettingsStatus(accountStatus, "error", "Name cannot be empty.");
          return;
        }
        if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
          showSettingsStatus(
            accountStatus,
            "error",
            "Please enter a valid email address."
          );
          return;
        }

        saveProfileBtn.disabled = true;
        try {
          const result = await settingsApi("PATCH", "/api/profile", {
            name,
            email,
          });
          const sidebarUserName = document.getElementById("sidebar-user-name");
          const sidebarUserEmail = document.getElementById("sidebar-user-email");
          if (sidebarUserName) {
            sidebarUserName.textContent = name;
          }
          if (sidebarUserEmail) {
            sidebarUserEmail.textContent = email;
          }
          showSettingsStatus(
            accountStatus,
            "success",
            result.message || "Profile updated successfully."
          );
        } catch (err) {
          showSettingsStatus(
            accountStatus,
            "error",
            err.message || "Failed to update profile."
          );
        } finally {
          saveProfileBtn.disabled = false;
        }
      });
    }

    if (deleteAccountBtn) {
      deleteAccountBtn.addEventListener("click", async () => {
        const confirmed = confirm(
          "⚠️ Delete account permanently?\n\nThis will remove your chats, memories, documents, and account data. This cannot be undone."
        );
        if (!confirmed) {
          return;
        }
        deleteAccountBtn.disabled = true;
        try {
          await settingsApi("DELETE", "/api/account");
          sessionStorage.removeItem("access_token");
          sessionStorage.removeItem("user");
          window.location.href = "login.html";
        } catch (err) {
          showSettingsStatus(
            accountStatus,
            "error",
            err.message || "Failed to delete account."
          );
          deleteAccountBtn.disabled = false;
        }
      });
    }

    overlay.querySelector("#export-json-btn").addEventListener("click", async () => {
      try {
        const history = await fetch("/api/history", { headers: getAuthHeaders() });
        if (!history.ok) throw new Error("Backend conversation history could not be loaded.");
        const summary = await history.json();
        const conversations = await Promise.all((summary.conversations || []).map(async (conversation) => {
          const response = await fetch(`/api/history/${encodeURIComponent(conversation.id)}`, { headers: getAuthHeaders() });
          if (!response.ok) throw new Error("A conversation could not be exported.");
          const payload = await response.json();
          return payload.conversation;
        }));
        downloadJson({ conversations, exportDate: new Date().toISOString() }, `isolde-backup-${new Date().toISOString().split("T")[0]}.json`);
        alert("Conversation history exported successfully.");
      } catch (err) {
        alert(err.message || "Failed to export conversation history.");
      }
    });

    overlay.querySelector("#delete-chats-btn").addEventListener("click", async () => {
      if (
        !confirm(
          "⚠️ Are you sure you want to delete all chat histories? This cannot be undone."
        )
      ) {
        return;
      }
      try {
        const token = sessionStorage.getItem("access_token");
        if (token && token !== "null" && token !== "undefined") {
          const response = await fetch("/api/history", {
            method: "DELETE",
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });
          if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || "Backend chat history was not deleted.");
          }
        }
      } catch (err) {
        alert(err.message || "Failed to clear chat history.");
        return;
      }
      alert("🗑️ All chats cleared successfully.");
      window.location.reload();
    });

    loadSettings();
    loadAccount();
  }
}, true);
