// frontend/script.js
(() => {
  "use strict";

  if (localStorage.getItem("access_token") === "guest_token_isolde_2026") {
    localStorage.removeItem("access_token");
  }

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

      return `<div class="code-block-wrapper" style="background:#0d1117;border-radius:10px;overflow:hidden;margin:14px 0;border:1px solid #30363d;box-shadow:0 4px 12px rgba(0,0,0,0.25);">
        <div class="code-block-header" style="display:flex;justify-content:space-between;align-items:center;padding:8px 14px;background:#161b22;border-bottom:1px solid #30363d;font-size:12px;color:#c9d1d9;font-family:ui-monospace,'SF Mono',monospace;">
          <span class="code-block-lang" style="letter-spacing:0.5px;font-weight:700;color:#8b949e;">${langLabel}</span>
          <button type="button" class="code-copy-btn" data-code-b64="${encodedCode}" style="background:transparent;border:1px solid #30363d;color:#c9d1d9;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:11px;font-weight:600;transition:background 0.15s ease;">📋 Copy Code</button>
        </div>
        <pre style="margin:0;padding:14px;overflow-x:auto;background:#0d1117;color:#c9d1d9;font-size:13px;line-height:1.5;"><code class="hljs ${validLang}">${highlighted}</code></pre>
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
      btn.style.color = "#4ade80";

      clearTimeout(btn._codeCopyTimer);
      btn._codeCopyTimer = setTimeout(() => {
        btn.textContent = originalLabel;
        btn.style.color = "#c9d1d9";
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

          try {
            document.execCommand("copy");
          } catch (e) {}

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

      try {
        document.execCommand("copy");
      } catch (e) {}

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

    const token = localStorage.getItem("access_token");

    if (token && token !== "null" && token !== "undefined") {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
  }

  function initLoginPage() {
    const init = () => {
      const loginForm = document.getElementById("login-form");
      const loginBtn = document.getElementById("login-btn");
      const guestBtn = document.getElementById("guest-btn");
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
              localStorage.setItem("access_token", data.access_token);
              showMessage("success", "Welcome back! Redirecting...");

              setTimeout(() => {
                window.location.href = "/";
              }, 1000);
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

      if (guestBtn) {
        guestBtn.addEventListener("click", () => {
          localStorage.removeItem("access_token");
          window.location.href = "/";
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
    const STORAGE_KEYS = {
      THEME: "isolde-theme",
      CONVERSATIONS: "isolde-conversations",
      ACTIVE_CONVERSATION: "isolde-active-conversation",
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
      webSearchEnabled: false,
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
        chatHistoryList:
          document.getElementById("chat-history-list") ||
          document.querySelector(".chat-history-list"),
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
        messageTextarea:
          document.getElementById("messageInput") ||
          document.getElementById("chat-message-input") ||
          document.querySelector(".message-textarea, textarea"),
        sendBtn: document.querySelector(".send-btn, button[type='submit']"),
        fileUploadBtn: document.querySelector(".file-upload-btn, .attachment-btn"),
        fileUploadInput:
          document.getElementById("file-upload-input") ||
          document.querySelector(".file-upload-input, input[type='file']"),
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
        webBtn.textContent = "🌐 Web: OFF";
        webBtn.title = "Toggle web search";
        webBtn.style.cssText =
          "background:transparent;border:1px solid rgba(148,163,184,0.4);color:#94a3b8;padding:6px 12px;border-radius:20px;cursor:pointer;font-size:12px;font-weight:600;transition:all 0.2s ease;margin:0 6px;white-space:nowrap;";

        webBtn.addEventListener("click", (e) => {
          e.preventDefault();

          state.webSearchEnabled = !state.webSearchEnabled;

          if (state.webSearchEnabled) {
            webBtn.textContent = "🌐 Web: ON";
            webBtn.style.background = "rgba(34,197,94,0.15)";
            webBtn.style.borderColor = "#22c55e";
            webBtn.style.color = "#22c55e";
          } else {
            webBtn.textContent = "🌐 Web: OFF";
            webBtn.style.background = "transparent";
            webBtn.style.borderColor = "rgba(148,163,184,0.4)";
            webBtn.style.color = "#94a3b8";
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
        stopBtn.style.cssText =
          "position:absolute;left:50%;transform:translateX(-50%);bottom:calc(100% + 12px);background:#1f2937;color:#f87171;border:1px solid #f87171;padding:8px 18px;border-radius:22px;cursor:pointer;font-size:13px;font-weight:600;box-shadow:0 6px 18px rgba(0,0,0,0.35);z-index:50;display:none;transition:all 0.15s ease;";

        stopBtn.addEventListener("mouseover", () => {
          stopBtn.style.background = "#f87171";
          stopBtn.style.color = "#111827";
        });

        stopBtn.addEventListener("mouseout", () => {
          stopBtn.style.background = "#1f2937";
          stopBtn.style.color = "#f87171";
        });

        stopBtn.addEventListener("click", (e) => {
          e.preventDefault();

          if (state.abortController) {
            try {
              state.abortController.abort();
            } catch (err) {}
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
      return new Date(date).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
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
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });

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

      template.content
        .querySelectorAll("script,iframe,object,embed,link,style,meta,base")
        .forEach((el) => el.remove());

      template.content.querySelectorAll("*").forEach((el) => {
        Array.from(el.attributes).forEach((attr) => {
          const name = attr.name.toLowerCase();
          const value = (attr.value || "").trim().toLowerCase();

          if (name.startsWith("on")) {
            el.removeAttribute(attr.name);
          } else if (
            ["href", "src", "xlink:href", "action", "formaction", "data", "background"].includes(
              name
            ) &&
            value.startsWith("javascript:")
          ) {
            el.removeAttribute(attr.name);
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
      try {
        localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(state.conversations));
        localStorage.setItem(STORAGE_KEYS.ACTIVE_CONVERSATION, state.activeConversationId ?? "");
      } catch (err) {
        console.error("Isolde: failed to save chat to localStorage.", err);
      }
    }

    function loadChat() {
      try {
        const rawConversations = localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
        const rawActiveId = localStorage.getItem(STORAGE_KEYS.ACTIVE_CONVERSATION);

        if (rawConversations) {
          const parsed = JSON.parse(rawConversations);
          state.conversations = { ...parsed, ...state.conversations };
        }

        if (rawActiveId && state.conversations[rawActiveId]) {
          state.activeConversationId = rawActiveId;
        }
      } catch (err) {
        console.error("Isolde: failed to load chat from localStorage.", err);
      }
    }

    function saveTheme(theme) {
      try {
        localStorage.setItem(STORAGE_KEYS.THEME, theme);
      } catch (err) {
        console.error("Isolde: failed to save theme to localStorage.", err);
      }
    }

    function loadTheme() {
      try {
        return localStorage.getItem(STORAGE_KEYS.THEME);
      } catch (err) {
        return null;
      }
    }

    function applyTheme(theme) {
      if (!document.documentElement) return;

      document.documentElement.setAttribute("data-theme", theme);

      if (dom.themeToggleBtn) {
        dom.themeToggleBtn.setAttribute("data-theme", theme);
        dom.themeToggleBtn.setAttribute(
          "title",
          theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
        );
      }
    }

    function toggleTheme() {
      const current =
        document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
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
      try {
        localStorage.setItem(STORAGE_KEYS.PREFERENCES, JSON.stringify(preferences));
      } catch (err) {
        console.error("Isolde: failed to save preferences.", err);
      }
    }

    function loadPreferences() {
      try {
        const raw = localStorage.getItem(STORAGE_KEYS.PREFERENCES);

        if (raw) {
          const parsed = JSON.parse(raw);
          preferences = { ...preferences, ...parsed };
        }
      } catch (err) {
        console.error("Isolde: failed to load preferences.", err);
      }

      const savedTheme = loadTheme();

      if (savedTheme) {
        preferences.theme = savedTheme;
      }
    }

    function hideWelcomeScreen() {
      if (dom.welcomeScreen) {
        dom.welcomeScreen.style.display = "none";
      }

      if (dom.chatMessages) {
        dom.chatMessages.style.display = "flex";
        dom.chatMessages.removeAttribute("hidden");
      }
    }

    function showWelcomeScreen() {
      if (dom.welcomeScreen) {
        dom.welcomeScreen.style.display = "flex";
      }

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

      if (dom.messageTextarea) {
        dom.messageTextarea.focus();
      }

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
        renderMessage(message.role, message.text, message.time);
      });

      scrollToBottom();
    }

    async function loadConversationMessages(id) {
      if (!state.conversations[id] || !state.conversations[id].isBackend) return;

      try {
        const response = await fetch(`/api/history/${id}`, {
          headers: getAuthHeaders(),
        });

        if (response.ok) {
          const data = await response.json();

          if (data.conversation && data.conversation.messages) {
            state.conversations[id].messages = data.conversation.messages.map((m) => ({
              role: m.role === "user" ? "user" : "bot",
              text: m.content,
              time: m.created_at || new Date().toISOString(),
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
          const response = await fetch(`/api/history/${conversation.id}/export`, {
            headers: getAuthHeaders(),
          });

          if (!response.ok) {
            throw new Error("Export failed");
          }

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

        downloadJson(
          exportPayload,
          `isolde-chat-${sanitizeFilename(conversation.title || conversation.id)}.json`
        );
      } catch (err) {
        console.error("Isolde: Failed to export chat", err);
        alert("Failed to export chat.");
      }
    }

    function getConversationLastTime(conversation) {
      const raw =
        conversation.messages && conversation.messages.length > 0
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
        filteredConversations = filteredConversations.filter((c) =>
          (c.title || "").toLowerCase().includes(q)
        );
      }

      filteredConversations.sort((a, b) => {
        if (a.isPinned && !b.isPinned) return -1;
        if (!a.isPinned && b.isPinned) return 1;
        return getConversationLastTime(b) - getConversationLastTime(a);
      });

      dom.chatHistoryList.innerHTML = "";

      if (filteredConversations.length === 0) {
        const emptyMsg = document.createElement("li");
        emptyMsg.style.color = "#9ca3af";
        emptyMsg.style.fontSize = "12px";
        emptyMsg.style.textAlign = "center";
        emptyMsg.style.padding = "10px";
        emptyMsg.textContent = "No chats found.";
        dom.chatHistoryList.appendChild(emptyMsg);
        return;
      }

      filteredConversations.forEach((conversation) => {
        const item = document.createElement("li");
        item.className = "chat-history-item";
        item.style.display = "flex";
        item.style.justifyContent = "space-between";
        item.style.alignItems = "center";
        item.style.padding = "8px 12px";
        item.style.position = "relative";

        if (conversation.id === state.activeConversationId) {
          item.classList.add("active");
          item.style.backgroundColor = "rgba(255, 255, 255, 0.1)";
          item.style.borderRadius = "8px";
        }

        const link = document.createElement("a");
        link.className = "chat-history-link";
        link.href = "#";
        link.textContent = conversation.title || "New conversation";
        link.style.flex = "1";
        link.style.overflow = "hidden";
        link.style.textOverflow = "ellipsis";
        link.style.whiteSpace = "nowrap";

        link.addEventListener("click", async (event) => {
          event.preventDefault();
          await switchConversation(conversation.id);
        });

        const actionsDiv = document.createElement("div");
        actionsDiv.style.display = "flex";
        actionsDiv.style.alignItems = "center";

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

                  if (!response.ok) {
                    throw new Error("Rename failed");
                  }
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
            if (e.key === "Enter") {
              e.preventDefault();
              commit();
            }

            if (e.key === "Escape") {
              committed = true;
              renderChatHistory();
            }
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
        pinBtn.addEventListener(
          "mouseout",
          () => (pinBtn.style.opacity = conversation.isPinned ? "1" : "0.5")
        );

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

              if (!response.ok) {
                throw new Error("Delete failed");
              }
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
        await fetch("/api/feedback", {
          method: "POST",
          headers: getAuthHeaders(true),
          body: JSON.stringify({ rating, comment }),
        });
      } catch (err) {
        console.error("Isolde: Feedback submission failed", err);
      }
    }

    async function loadMemories() {
      try {
        const response = await fetch("/api/memory/list", {
          headers: getAuthHeaders(),
        });

        if (response.ok) {
          const data = await response.json();

          if (dom.memoryList) {
            dom.memoryList.innerHTML = "";

            if (!data.memories || data.memories.length === 0) {
              dom.memoryList.innerHTML = `<li style="color: #6b7280; font-style: italic;">No memories saved yet.</li>`;
              return;
            }

            data.memories.forEach((mem) => {
              const li = document.createElement("li");
              li.style.display = "flex";
              li.style.justifyContent = "space-between";
              li.style.alignItems = "center";
              li.style.marginBottom = "4px";
              li.innerHTML = `<span><b>[${mem.category}]</b> ${escapeHtml(
                mem.memory
              )}</span> <button class="delete-memory-btn" data-id="${mem.id}" title="Delete memory" style="background:transparent; border:none; color:#ef4444; cursor:pointer; font-size:10px;">❌</button>`;

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
        await fetch(`/api/memory/${id}`, {
          method: "DELETE",
          headers: getAuthHeaders(),
        });

        loadMemories();
      } catch (err) {
        console.error("Failed to delete memory", err);
      }
    }

    async function clearAllMemories() {
      try {
        await fetch("/api/memory/all", {
          method: "DELETE",
          headers: getAuthHeaders(),
        });

        loadMemories();
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

        if (el.dataset.originalLabel) {
          el.textContent = el.dataset.originalLabel;
        }
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

    function renderMessage(role, text, time) {
      const isUser = role === "user";

      const article = document.createElement("article");
      article.className = `message ${isUser ? "message-user" : "message-bot"}`;

      const avatar = document.createElement("img");
      avatar.className = "message-avatar";
      avatar.src = "";
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
        const actionsDiv = document.createElement("div");
        actionsDiv.className = "message-actions";
        actionsDiv.style.display = "flex";
        actionsDiv.style.gap = "8px";
        actionsDiv.style.marginTop = "8px";
        actionsDiv.style.alignItems = "center";

        const copyBtn = document.createElement("button");
        copyBtn.className = "copy-message-btn";
        copyBtn.type = "button";
        copyBtn.title = "Copy message";
        copyBtn.textContent = "📋 Copy";
        copyBtn.style.cursor = "pointer";
        copyBtn.addEventListener("click", () => copyMessage(text, copyBtn));
        actionsDiv.appendChild(copyBtn);

        const readBtn = document.createElement("button");
        readBtn.className = "read-message-btn";
        readBtn.type = "button";
        readBtn.title = "Read aloud";
        readBtn.textContent = "🔊 Read";
        readBtn.style.cursor = "pointer";
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
        regenBtn.style.cursor = "pointer";
        regenBtn.addEventListener("click", () => regenerateLastResponse());
        actionsDiv.appendChild(regenBtn);

        const likeBtn = document.createElement("button");
        likeBtn.type = "button";
        likeBtn.title = "Good response";
        likeBtn.textContent = "👍";
        likeBtn.style.cursor = "pointer";
        likeBtn.style.background = "none";
        likeBtn.style.border = "none";
        likeBtn.style.fontSize = "14px";

        const dislikeBtn = document.createElement("button");
        dislikeBtn.type = "button";
        dislikeBtn.title = "Bad response";
        dislikeBtn.textContent = "👎";
        dislikeBtn.style.cursor = "pointer";
        dislikeBtn.style.background = "none";
        dislikeBtn.style.border = "none";
        dislikeBtn.style.fontSize = "14px";

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
        userActionsDiv.style.display = "flex";
        userActionsDiv.style.gap = "8px";
        userActionsDiv.style.marginTop = "6px";
        userActionsDiv.style.alignItems = "center";
        userActionsDiv.style.justifyContent = "flex-end";

        const editBtn = document.createElement("button");
        editBtn.className = "edit-user-msg-btn";
        editBtn.type = "button";
        editBtn.title = "Edit and resend this message";
        editBtn.textContent = "✏️ Edit";
        editBtn.style.cssText =
          "background:transparent;border:1px solid rgba(148,163,184,0.35);color:#94a3b8;padding:4px 10px;border-radius:14px;cursor:pointer;font-size:12px;font-weight:500;";

        editBtn.addEventListener("mouseover", () => {
          editBtn.style.background = "rgba(59,130,246,0.15)";
          editBtn.style.borderColor = "#3b82f6";
          editBtn.style.color = "#3b82f6";
        });

        editBtn.addEventListener("mouseout", () => {
          editBtn.style.background = "transparent";
          editBtn.style.borderColor = "rgba(148,163,184,0.35)";
          editBtn.style.color = "#94a3b8";
        });

        editBtn.addEventListener("click", () => {
          if (dom.messageTextarea) {
            dom.messageTextarea.value = text;
            dom.messageTextarea.focus();

            const len = dom.messageTextarea.value.length;

            try {
              dom.messageTextarea.setSelectionRange(len, len);
            } catch (e) {}

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

      conversation.messages.push({
        role: "user",
        text,
        time: time.toISOString(),
      });

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

      conversation.messages.push({
        role: "bot",
        text,
        time: time.toISOString(),
      });

      renderMessage("bot", text, time);
      scrollToBottom();
      saveChat();
    }

    function showTyping() {
      dom.typingIndicator?.classList.add("is-visible");

      if (dom.typingIndicator) {
        dom.typingIndicator.style.display = "flex";
      }

      scrollToBottom();
    }

    function hideTyping() {
      dom.typingIndicator?.classList.remove("is-visible");

      if (dom.typingIndicator) {
        dom.typingIndicator.style.display = "none";
      }
    }

    function setLoading(isLoading) {
      state.isLoading = isLoading;

      if (dom.sendBtn) {
        dom.sendBtn.disabled = isLoading;
      }

      if (isLoading) {
        showTyping();
      } else {
        hideTyping();
      }

      updateStopButtonVisibility();
    }

    function showBroadcastToast(message) {
      const toast = document.createElement("div");
      toast.textContent = "📢 " + message;
      toast.style.position = "fixed";
      toast.style.top = "20px";
      toast.style.left = "50%";
      toast.style.transform = "translateX(-50%)";
      toast.style.backgroundColor = "#EF4444";
      toast.style.color = "#FFF";
      toast.style.padding = "12px 24px";
      toast.style.borderRadius = "8px";
      toast.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
      toast.style.zIndex = "9999";
      toast.style.fontWeight = "bold";
      toast.style.transition = "opacity 0.5s ease";

      document.body.appendChild(toast);

      setTimeout(() => {
        toast.style.opacity = "0";

        setTimeout(() => {
          if (toast.parentNode) {
            document.body.removeChild(toast);
          }
        }, 500);
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
          }),
          signal: controller.signal,
        });
      } catch (err) {
        if (err.name === "AbortError") {
          botMsgObj.text = (botMsgObj.text || "") + "\n\n[Generation Stopped by User]";

          if (typeof marked !== "undefined") {
            textEl.innerHTML = sanitizeHtml(marked.parse(botMsgObj.text));
          } else {
            textEl.innerHTML = escapeHtml(botMsgObj.text).replace(/\n/g, "<br>");
          }

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
        throw new Error("Server Error / Network Error");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let accumulatedText = "";
      let wasAborted = false;
      let streamDone = false;

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

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataText = line.replace("data: ", "").trim();

              if (dataText === "[DONE]") {
                streamDone = true;
                break;
              }

              if (dataText === "[ERROR]") {
                throw new Error("Streaming encountered an error.");
              }

              accumulatedText += dataText + " ";
              botMsgObj.text = accumulatedText;

              if (typeof marked !== "undefined") {
                textEl.innerHTML = sanitizeHtml(marked.parse(accumulatedText));
              } else {
                textEl.innerHTML = escapeHtml(accumulatedText).replace(/\n/g, "<br>");
              }

              requestAnimationFrame(() => scrollToBottom());
            }
          }

          if (streamDone || controller.signal.aborted) {
            if (controller.signal.aborted) {
              wasAborted = true;
            }

            break;
          }
        }
      } finally {
        try {
          reader.cancel();
        } catch (e) {}

        state.abortController = null;
        state.streamingBotMsgObj = null;
        state.streamingTextEl = null;
      }

      if (wasAborted) {
        accumulatedText += "\n\n[Generation Stopped by User]";
        botMsgObj.text = accumulatedText;

        if (typeof marked !== "undefined") {
          textEl.innerHTML = sanitizeHtml(marked.parse(accumulatedText));
        } else {
          textEl.innerHTML = escapeHtml(accumulatedText).replace(/\n/g, "<br>");
        }

        return;
      }

      if (isNewChat) {
        await loadHistory();

        const backendConvos = Object.values(state.conversations).filter((c) => c.isBackend);

        backendConvos.sort(
          (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
        );

        const oldId = state.activeConversationId;

        if (
          backendConvos.length > 0 &&
          oldId &&
          state.conversations[oldId] &&
          !state.conversations[oldId].isBackend
        ) {
          const newestRealId = backendConvos[0].id;

          if (oldId !== newestRealId) {
            state.conversations[newestRealId].messages = state.conversations[oldId].messages;
            state.conversations[newestRealId].title =
              state.conversations[oldId].title || state.conversations[newestRealId].title;
            state.conversations[newestRealId].isPinned =
              state.conversations[oldId].isPinned ||
              state.conversations[newestRealId].isPinned;

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

      const botMsgObj = {
        role: "bot",
        text: "",
        time: time.toISOString(),
      };

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
        if (conversation.messages[i].role === "user") {
          lastUserMsgIndex = i;
          break;
        }
      }

      if (lastUserMsgIndex === -1) return;

      const lastUserText = conversation.messages[lastUserMsgIndex].text;

      conversation.messages = conversation.messages.slice(0, lastUserMsgIndex + 1);
      renderActiveConversation();

      setLoading(true);

      const time = new Date();

      const botMsgObj = {
        role: "bot",
        text: "",
        time: time.toISOString(),
      };

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
      textarea.style.overflowY =
        textarea.scrollHeight > MAX_TEXTAREA_HEIGHT ? "auto" : "hidden";
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
      if (!speechRecognition) {
        alert("Your browser does not support Voice Recognition.");
        return;
      }

      state.isRecording = true;

      dom.voiceInputBtn?.classList.add("is-recording");
      dom.voiceInputBtn?.setAttribute("title", "Stop recording");

      try {
        speechRecognition.start();
      } catch (e) {}
    }

    function stopVoiceRecording() {
      state.isRecording = false;

      dom.voiceInputBtn?.classList.remove("is-recording");
      dom.voiceInputBtn?.setAttribute("title", "Voice input");

      if (speechRecognition) {
        try {
          speechRecognition.stop();
        } catch (e) {}
      }
    }

    function toggleVoiceRecording() {
      if (state.isRecording) {
        stopVoiceRecording();
      } else {
        startVoiceRecording();
      }
    }

    async function handleFileSelected(event) {
      const file = event.target.files?.[0];

      if (!file) return;

      if (dom.attachmentMenu) {
        dom.attachmentMenu.classList.remove("show");
      }

      const formData = new FormData();
      formData.append("file", file);

      setLoading(true);

      try {
        appendBotMessage(`Uploading **${file.name}** for RAG document analysis...`);

        const response = await fetch("/api/rag/upload", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token") || ""}`,
          },
          body: formData,
        });

        const data = await response.json();

        if (response.ok && data.status === "success") {
          appendBotMessage(
            `✅ Document **${file.name}** Indexed successfully! You can now ask questions about this document.`
          );
        } else {
          appendBotMessage(`⚠ Failed to upload document: ${data.message}`);
        }
      } catch (err) {
        console.error("File upload error:", err);
        appendBotMessage("⚠ Network error during file upload.");
      } finally {
        setLoading(false);
        event.target.value = "";
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

      try {
        document.execCommand("copy");
      } catch (err) {}

      document.body.removeChild(textarea);
    }

    function showCopyFeedback(buttonEl) {
      if (!buttonEl) return;

      const originalLabel = buttonEl.dataset.originalLabel ?? buttonEl.textContent;
      buttonEl.dataset.originalLabel = originalLabel;
      buttonEl.textContent = "✓ Copied!";

      clearTimeout(buttonEl._copyResetTimer);
      buttonEl._copyResetTimer = setTimeout(() => {
        buttonEl.textContent = originalLabel;
      }, COPY_FEEDBACK_DURATION);
    }

    async function logout() {
      try {
        await fetch("/api/logout", {
          method: "POST",
          headers: getAuthHeaders(),
        });
      } catch (e) {}

      localStorage.removeItem("access_token");
      localStorage.removeItem("user");

      window.location.href = "login.html";
    }

    function bindEvents() {
      if (dom.chatSearchInput) {
        dom.chatSearchInput.addEventListener("input", (e) => {
          state.searchQuery = e.target.value;
          renderChatHistory();
        });
      }

      dom.messageForm?.addEventListener("submit", (event) => {
        event.preventDefault();
        sendMessage();
      });

      dom.messageTextarea?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          sendMessage();
        }
      });

      dom.messageTextarea?.addEventListener("input", () => {
        autoResizeTextarea();
        updateSendButtonState();
      });

      dom.suggestionChips?.forEach((chip) => {
        chip.addEventListener("click", () => {
          sendMessage(chip.textContent.trim());
        });
      });

      dom.newChatBtn?.addEventListener("click", () => {
        createConversation();
      });

      dom.clearChatBtn?.addEventListener("click", () => {
        clearChat();
      });

      dom.themeToggleBtn?.addEventListener("click", () => {
        toggleTheme();
      });

      dom.voiceInputBtn?.addEventListener("click", () => {
        toggleVoiceRecording();
      });

      dom.fileUploadInput?.addEventListener("change", handleFileSelected);

      if (dom.logoutBtn) {
        dom.logoutBtn.addEventListener("click", () => {
          logout();
        });
      }

      dom.clearAllMemoriesBtn?.addEventListener("click", () => {
        clearAllMemories();
      });

      if (dom.toggleAttachmentBtn && dom.attachmentMenu) {
        dom.toggleAttachmentBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          dom.attachmentMenu.classList.toggle("show");
        });
      }

      document.addEventListener("click", (event) => {
        if (dom.attachmentMenu && dom.attachmentMenu.classList.contains("show")) {
          if (!event.target.closest(".attachment-wrapper")) {
            dom.attachmentMenu.classList.remove("show");
          }
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
          headers: getAuthHeaders(),
        });

        if (response.ok) {
          const user = await response.json();

          if (dom.sidebarUserName) {
            dom.sidebarUserName.textContent = user.name || user.username || "User";
          }

          if (dom.sidebarUserEmail) {
            dom.sidebarUserEmail.textContent = user.email || "user@example.com";
          }
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
          profileModal.style.cssText =
            "position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); backdrop-filter:blur(5px); display:flex; justify-content:center; align-items:center; z-index:9999;";

          profileModal.innerHTML = `
            <div style="background:var(--bg-surface, #1e293b); color:var(--text-primary, #fff); padding:30px; border-radius:16px; width:100%; max-width:380px; box-shadow:0 20px 25px -5px rgba(0,0,0,0.3); border:1px solid var(--border-default, rgba(255,255,255,0.1)); text-align:center;">
              <div style="font-size:48px; margin-bottom:10px;">👤</div>
              <h3 style="margin:0 0 5px; font-size:20px; font-weight:700;">${escapeHtml(
                userName
              )}</h3>
              <p style="color:var(--text-secondary, #94a3b8); font-size:13px; margin:0 0 20px;">${escapeHtml(
                userEmail
              )}</p>
              <div style="background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.3); padding:10px; border-radius:8px; font-size:12px; color:#60A5FA; margin-bottom:20px;">
                🚀 Plan: Pro Glass Workspace (Active)
              </div>
              <button id="close-profile-modal" style="width:100%; padding:10px; background:#3B82F6; color:white; border:none; border-radius:8px; font-weight:600; cursor:pointer; margin-bottom:8px;">Close</button>
              <button id="modal-logout-btn" style="width:100%; padding:10px; background:transparent; color:#EF4444; border:1px solid rgba(239,68,68,0.3); border-radius:8px; font-weight:600; cursor:pointer;">Logout</button>
            </div>
          `;

          document.body.appendChild(profileModal);

          profileModal.querySelector("#close-profile-modal").addEventListener("click", () => {
            profileModal.style.display = "none";
          });

          profileModal.querySelector("#modal-logout-btn").addEventListener("click", () => {
            logout();
          });

          profileModal.addEventListener("click", (e) => {
            if (e.target === profileModal) {
              profileModal.style.display = "none";
            }
          });
        } else {
          profileModal.style.display = "flex";
        }
      });
    }

    async function loadHistory() {
      try {
        const response = await fetch("/api/history", {
          headers: getAuthHeaders(),
        });

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
        if (state.conversations[state.activeConversationId].isBackend) {
          state.backendConversationId = state.activeConversationId;
        } else {
          state.backendConversationId = null;
        }

        if (
          state.conversations[state.activeConversationId].isBackend &&
          state.conversations[state.activeConversationId].messages.length === 0
        ) {
          await loadConversationMessages(state.activeConversationId);
        }

        renderChatHistory();
        renderActiveConversation();
      }

      if (dom.modelSelect && preferences.defaultModel) {
        const optionExists = Array.from(dom.modelSelect.options).some(
          (o) => o.value === preferences.defaultModel
        );

        if (optionExists) {
          dom.modelSelect.value = preferences.defaultModel;
        }
      }

      updateSendButtonState();
      bindEvents();

      injectDynamicButtons();
      updateStopButtonVisibility();
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initializeApp);
    } else {
      initializeApp();
    }
  }
})();

function onDocumentReady(fn) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fn);
  } else {
    fn();
  }
}

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
    ["keydown", "keyup", "keypress", "input"].forEach((evt) => {
      input.addEventListener(evt, (e) => e.stopPropagation());
    });
  }

  function openWorkspace(type, e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }

    if (!modal) return;

    if (type === "image") {
      if (title) title.textContent = "🎨 Images Studio Workspace";
      if (desc)
        desc.textContent =
          "Transform text prompts into stunning high-definition AI artworks instantly.";
      if (input) input.placeholder = "e.g., A futuristic cyberpunk city in neon lights, 4k...";
    } else {
      if (title) title.textContent = "🎬 Videos Generation Suite";
      if (desc)
        desc.textContent =
          "Synthesize high-framerate dynamic videos from textual descriptions.";
      if (input)
        input.placeholder = "e.g., Drone shot flying across snow-capped mountains at sunrise...";
    }

    if (input) input.value = "";
    if (resultContainer) resultContainer.style.display = "none";

    modal.style.display = "flex";

    setTimeout(() => {
      if (input) input.focus();
    }, 100);
  }

  if (imgStudioBtn) {
    imgStudioBtn.addEventListener("click", (e) => openWorkspace("image", e));
  }

  if (vidGenBtn) {
    vidGenBtn.addEventListener("click", (e) => openWorkspace("video", e));
  }

  if (closeBtn && modal) {
    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      modal.style.display = "none";
    });

    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.style.display = "none";
      }
    });
  }

  if (runBtn) {
    runBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();

      const promptText = input ? input.value.trim() : "";

      if (!promptText) {
        alert("Please enter a prompt description first!");
        return;
      }

      if (resultContainer) resultContainer.style.display = "block";
      if (loader) loader.style.display = "block";
      if (imgOutput) imgOutput.style.display = "none";

      try {
        const isImage = title && title.textContent.includes("Images");
        const endpoint = isImage ? "/api/studio/generate-image" : "/api/studio/generate-video";

        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: promptText }),
        });

        const data = await res.json();

        if (res.ok && data.status === "success") {
          if (loader) loader.style.display = "none";

          if (isImage && imgOutput) {
            imgOutput.src = data.image_url;
            imgOutput.style.display = "block";
          } else if (loader) {
            loader.style.display = "block";
            loader.textContent = "✅ Job Completed Successfully! Pipeline output ready.";
          }
        } else if (loader) {
          loader.textContent = "⚠ Generation failed: " + (data.message || "Unknown error");
        }
      } catch (err) {
        if (loader) loader.textContent = "⚠ Network connection error during generation.";
      }
    });
  }
});

document.addEventListener("click", (e) => {
  const attachMenu = document.getElementById("attachment-menu");

  if (!attachMenu || !attachMenu.contains(e.target)) return;

  const target = e.target.closest("li, a, button, span, div");

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

document.addEventListener(
  "click",
  async (e) => {
    const target = e.target.closest("button, a, div, span, li");

    if (!target) return;

    const text = target.textContent ? target.textContent.trim().toLowerCase() : "";
    const id = target.id ? target.id.toLowerCase() : "";

    if (text === "settings" || id.includes("setting") || text.includes("settings")) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      document
        .querySelectorAll("#settings-modal, .settings-modal-overlay, div[id*='pref'], div[id*='global']")
        .forEach((m) => m.remove());

      const overlay = document.createElement("div");
      overlay.id = "settings-modal";
      overlay.className = "settings-modal-overlay show";
      overlay.style.cssText =
        "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.75);backdrop-filter:blur(8px);display:flex;justify-content:center;align-items:center;z-index:999999;";

      overlay.innerHTML = `
        <div style="width:850px;height:580px;background:#212121;color:#ececec;border-radius:14px;display:flex;flex-direction:row;box-shadow:0 24px 48px rgba(0,0,0,0.6);border:1px solid rgba(255,255,255,0.1);overflow:hidden;position:relative;">
          <div style="width:240px;min-width:240px;height:100%;background:#171717;border-right:1px solid #2f2f2f;display:flex;flex-direction:column;padding:16px 12px;gap:6px;box-sizing:border-box;overflow-y:auto;">
            <div style="display:flex;justify-content:flex-end;margin-bottom:8px;">
              <button id="modal-close-x" style="background:transparent;border:none;color:#aaa;font-size:18px;cursor:pointer;padding:4px 8px;border-radius:4px;">✕</button>
            </div>
            <button class="s-tab is-active" data-tab="general" style="text-align:left;padding:10px 12px;background:#2f2f2f;border:none;color:#fff;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px;">General</button>
            <button class="s-tab" data-tab="notifications" style="text-align:left;padding:10px 12px;background:transparent;border:none;color:#b4b4b4;border-radius:8px;cursor:pointer;font-size:14px;">Notifications</button>
            <button class="s-tab" data-tab="personalization" style="text-align:left;padding:10px 12px;background:transparent;border:none;color:#b4b4b4;border-radius:8px;cursor:pointer;font-size:14px;">Personalization</button>
            <button class="s-tab" data-tab="security" style="text-align:left;padding:10px 12px;background:transparent;border:none;color:#b4b4b4;border-radius:8px;cursor:pointer;font-size:14px;">Security and login</button>
            <button class="s-tab" data-tab="account" style="text-align:left;padding:10px 12px;background:transparent;border:none;color:#b4b4b4;border-radius:8px;cursor:pointer;font-size:14px;">Account</button>
          </div>
          <div style="flex:1;height:100%;background:#212121;padding:32px;overflow-y:auto;display:flex;flex-direction:column;box-sizing:border-box;">
            <div class="s-panel" data-panel="general" style="display:block;">
              <h2 style="margin:0 0 24px 0;font-size:20px;font-weight:600;color:#fff;">General Preferences</h2>
              <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 0;border-bottom:1px solid #2f2f2f;">
                <span style="font-size:14px;">Appearance Theme</span>
                <select id="set-appearance" style="padding:8px 12px;border-radius:6px;background:#2f2f2f;color:#fff;border:1px solid #444;font-size:13px;outline:none;">
                  <option value="dark">Dark Glass</option>
                  <option value="light">Light Clean</option>
                </select>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 0;border-bottom:1px solid #2f2f2f;">
                <span style="font-size:14px;">Workspace Language</span>
                <select id="set-lang" style="padding:8px 12px;border-radius:6px;background:#2f2f2f;color:#fff;border:1px solid #444;font-size:13px;outline:none;">
                  <option value="en">English (US)</option>
                  <option value="ta">Tamil (தமிழ்)</option>
                </select>
              </div>
              <div style="margin-top:32px;display:flex;gap:12px;">
                <button id="export-json-btn" style="background:#3B82F6;color:#fff;border:none;padding:10px 18px;border-radius:8px;cursor:pointer;font-weight:600;font-size:13px;">Export Conversation Data (JSON)</button>
                <button id="delete-chats-btn" style="background:#EF4444;color:#fff;border:none;padding:10px 18px;border-radius:8px;cursor:pointer;font-weight:600;font-size:13px;">Delete All Chats</button>
              </div>
            </div>
            <div class="s-panel" data-panel="notifications" style="display:none;">
              <h2 style="margin:0 0 12px 0;font-size:20px;font-weight:600;color:#fff;">Notifications</h2>
              <p style="color:#9ca3af;font-size:14px;">Configure how you receive push and email alerts across your enterprise workspace.</p>
            </div>
            <div class="s-panel" data-panel="personalization" style="display:none;">
              <h2 style="margin:0 0 12px 0;font-size:20px;font-weight:600;color:#fff;">Personalization</h2>
              <p style="color:#9ca3af;font-size:14px;">Manage custom instructions and context memory behavior for Isolde AI.</p>
            </div>
            <div class="s-panel" data-panel="security" style="display:none;">
              <h2 style="margin:0 0 12px 0;font-size:20px;font-weight:600;color:#fff;">Security and Login</h2>
              <p style="color:#9ca3af;font-size:14px;">Manage multi-factor authentication (MFA) and active session tokens.</p>
            </div>
            <div class="s-panel" data-panel="account" style="display:none;">
              <h2 style="margin:0 0 12px 0;font-size:20px;font-weight:600;color:#fff;">Account Information</h2>
              <p style="color:#9ca3af;font-size:14px;">Workspace Owner</p>
              <p style="color:#9ca3af;font-size:14px;margin-top:8px;">Plan: Enterprise Pro Unlimited</p>
            </div>
          </div>
        </div>
      `;

      document.body.appendChild(overlay);

      const closeModal = () => overlay.remove();

      overlay.querySelector("#modal-close-x").addEventListener("click", closeModal);

      overlay.addEventListener("click", (ev) => {
        if (ev.target === overlay) closeModal();
      });

      const tabs = overlay.querySelectorAll(".s-tab");
      const panels = overlay.querySelectorAll(".s-panel");

      tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
          const targetPanel = tab.getAttribute("data-tab");

          tabs.forEach((t) => {
            t.style.background = "transparent";
            t.style.color = "#b4b4b4";
            t.style.fontWeight = "normal";
          });

          tab.style.background = "#2f2f2f";
          tab.style.color = "#fff";
          tab.style.fontWeight = "600";

          panels.forEach((p) => {
            p.style.display = p.getAttribute("data-panel") === targetPanel ? "block" : "none";
          });
        });
      });

      overlay.querySelector("#export-json-btn").addEventListener("click", () => {
        const rawConvos = localStorage.getItem("isolde-conversations") || "{}";

        const exportData = {
          conversations: JSON.parse(rawConvos),
          exportDate: new Date().toISOString(),
        };

        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
          type: "application/json",
        });

        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");

        a.href = url;
        a.download = `isolde-backup-${new Date().toISOString().split("T")[0]}.json`;
        a.click();

        setTimeout(() => URL.revokeObjectURL(url), 1000);

        alert("✅ Conversation history exported successfully!");
      });

      overlay.querySelector("#delete-chats-btn").addEventListener("click", async () => {
        if (!confirm("⚠️ Are you sure you want to delete all chat histories? This cannot be undone.")) {
          return;
        }

        try {
          const token = localStorage.getItem("access_token");

          if (token && token !== "null" && token !== "undefined") {
            await fetch("/api/history", {
              method: "DELETE",
              headers: {
                Authorization: `Bearer ${token}`,
              },
            });
          }
        } catch (err) {
          console.error("Failed to clear backend history", err);
        }

        localStorage.removeItem("isolde-conversations");
        localStorage.removeItem("isolde-active-conversation");

        alert("🗑️ All chats cleared successfully.");
        window.location.reload();
      });
    }
  },
  true
);