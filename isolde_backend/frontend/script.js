/* ==========================================================================
   ISOLDE — AI Chatbot Interface
   Production JavaScript · ES6+ · No frameworks, no dependencies

   Wires up the existing HTML/CSS:
   - Chat send/receive, typing indicator, auto-scroll
   - Welcome screen hide/restore
   - Multi-conversation chat history (create, switch, highlight active)
   - Clear chat
   - Theme toggle (light/dark) via [data-theme] + localStorage
   - Auto-resizing textarea (max 200px, matches CSS max-height)
   - Voice button visual-only recording state (.is-recording)
   - File upload filename preview (no backend upload)
   - Copy message button with "Copied!" feedback
   - Loading state (disables send button, shows typing indicator)
   - Persists theme + all conversations to localStorage, restores on load
   ========================================================================== */

(() => {
  "use strict";

  /* ========================================================================
     CONSTANTS
     ======================================================================== */

  const STORAGE_KEYS = {
    THEME: "isolde-theme",
    CONVERSATIONS: "isolde-conversations",
    ACTIVE_CONVERSATION: "isolde-active-conversation",
  };

  const MAX_TEXTAREA_HEIGHT = 200; // px — matches .message-textarea max-height in CSS
  const BOT_REPLY_DELAY = 900; // ms — simulated "thinking" delay before a reply appears
  const COPY_FEEDBACK_DURATION = 1600; // ms — how long "Copied!" stays visible

  /* ========================================================================
     DOM REFERENCES
     ======================================================================== */

  const dom = {
    app: document.querySelector(".app"),
    sidebar: document.querySelector(".sidebar"),

    newChatBtn: document.querySelector(".new-chat-btn"),
    chatHistoryList: document.querySelector(".chat-history-list"),

    themeToggleBtn: document.querySelector(".theme-toggle-btn"),
    clearChatBtn: document.querySelector(".clear-chat-btn"),

    chatArea: document.querySelector(".chat-area"),
    welcomeScreen: document.querySelector(".welcome-screen"),
    chatMessages: document.querySelector(".chat-messages"),
    suggestionChips: document.querySelectorAll(".suggestion-chip"),

    typingIndicator: document.querySelector(".typing-indicator"),

    messageForm: document.querySelector(".message-form"),
    messageTextarea: document.querySelector(".message-textarea"),
    sendBtn: document.querySelector(".send-btn"),

    fileUploadBtn: document.querySelector(".file-upload-btn"),
    fileUploadInput: document.querySelector(".file-upload-input"),

    voiceInputBtn: document.querySelector(".voice-input-btn"),
  };

  /* ========================================================================
     STATE
     ======================================================================== */

  /**
   * conversations: {
   *   [id]: { id, title, messages: [{ role, text, time }] }
   * }
   */
  let state = {
  conversations: {},
  activeConversationId: null,
  backendConversationId: null,
  isLoading: false,
  isRecording: false,
};

  /* ========================================================================
     UTILITY FUNCTIONS
     ======================================================================== */

  /** Generate a reasonably unique id without external libraries. */
  function generateId() {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }

  /** Format a Date as a short local time string, e.g. "10:04 AM". */
  function formatTime(date) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  /** Escape HTML special characters to prevent markup injection from text content. */
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  /** Derive a short conversation title from the first user message. */
  function deriveTitle(text) {
    const trimmed = text.trim().replace(/\s+/g, " ");
    return trimmed.length > 42 ? `${trimmed.slice(0, 42)}…` : trimmed || "New conversation";
  }

  /** Scroll the chat area smoothly to the latest message. */
  function scrollToBottom() {
    if (!dom.chatArea) return;
    dom.chatArea.scrollTo({ top: dom.chatArea.scrollHeight, behavior: "smooth" });
  }

  /* ========================================================================
     LOCAL STORAGE
     ======================================================================== */

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

      state.conversations = rawConversations ? JSON.parse(rawConversations) : {};
      state.activeConversationId = rawActiveId || null;
    } catch (err) {
      console.error("Isolde: failed to load chat from localStorage.", err);
      state.conversations = {};
      state.activeConversationId = null;
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
      console.error("Isolde: failed to load theme from localStorage.", err);
      return null;
    }
  }

  /* ========================================================================
     THEME
     ======================================================================== */

  function applyTheme(theme) {
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
    const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    const next = current === "dark" ? "light" : "dark";
    applyTheme(next);
    saveTheme(next);
  }

  function restoreTheme() {
    const saved = loadTheme();
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
    const theme = saved || (prefersDark ? "dark" : "light");
    applyTheme(theme);
  }

  /* ========================================================================
     WELCOME SCREEN
     ======================================================================== */

  function hideWelcomeScreen() {
    if (dom.welcomeScreen) {
      dom.welcomeScreen.style.display = "none";
    }
  }

  function showWelcomeScreen() {
    if (dom.welcomeScreen) {
      dom.welcomeScreen.style.display = "";
    }
  }

  /* ========================================================================
     CONVERSATIONS / CHAT HISTORY
     ======================================================================== */

  /** Create a brand new empty conversation and make it active. */
  function createConversation() {
    const id = generateId();
    state.conversations[id] = { id, title: "New conversation", messages: [] };
    state.activeConversationId = id;

    renderChatHistory();
    renderActiveConversation();
    saveChat();

    return id;
  }

  /** Get the currently active conversation object, creating one if needed. */
  function getActiveConversation() {
    if (!state.activeConversationId || !state.conversations[state.activeConversationId]) {
      createConversation();
    }
    return state.conversations[state.activeConversationId];
  }

  /** Switch to a different conversation by id and re-render the chat area. */
  function switchConversation(id) {
    if (!state.conversations[id]) return;
    state.activeConversationId = id;
    renderChatHistory();
    renderActiveConversation();
    saveChat();
  }

  /** Render the sidebar's chat-history list from current state. */
  function renderChatHistory() {
    if (!dom.chatHistoryList) return;

    const conversations = Object.values(state.conversations).sort((a, b) => {
      const aLast = a.messages[a.messages.length - 1]?.time ?? 0;
      const bLast = b.messages[b.messages.length - 1]?.time ?? 0;
      return new Date(bLast) - new Date(aLast);
    });

    dom.chatHistoryList.innerHTML = "";

    conversations.forEach((conversation) => {
      const item = document.createElement("li");
      item.className = "chat-history-item";
      if (conversation.id === state.activeConversationId) {
        item.classList.add("active");
      }

      const link = document.createElement("a");
      link.className = "chat-history-link";
      link.href = "#";
      link.textContent = conversation.title;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        switchConversation(conversation.id);
      });

      item.appendChild(link);
      dom.chatHistoryList.appendChild(item);
    });
  }

  /** Re-render the chat message list to reflect the active conversation. */
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
      renderMessage(message.role, message.text, new Date(message.time));
    });
    scrollToBottom();
  }

  /* ========================================================================
     MESSAGE RENDERING
     ======================================================================== */

  /** Build and insert a message bubble into the DOM. Returns the created element. */
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

    const textEl = document.createElement("p");
    textEl.className = "message-text";
    textEl.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");

    const timeEl = document.createElement("span");
    timeEl.className = "message-time";
    timeEl.textContent = formatTime(time);

    content.appendChild(textEl);
    content.appendChild(timeEl);

    if (!isUser) {
      const copyBtn = document.createElement("button");
      copyBtn.className = "copy-message-btn";
      copyBtn.type = "button";
      copyBtn.title = "Copy message";
      copyBtn.textContent = "Copy";
      copyBtn.addEventListener("click", () => copyMessage(text, copyBtn));
      content.appendChild(copyBtn);
    }

    article.appendChild(avatar);
    article.appendChild(content);
    dom.chatMessages.appendChild(article);

    return article;
  }

  /** Append a user message to state + DOM. */
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

  /** Append a bot message to state + DOM. */
  function appendBotMessage(text) {
    const conversation = getActiveConversation();
    const time = new Date();

    conversation.messages.push({ role: "bot", text, time: time.toISOString() });

    renderMessage("bot", text, time);
    scrollToBottom();
    saveChat();
  }

  /* ========================================================================
     TYPING INDICATOR
     ======================================================================== */

  function showTyping() {
    dom.typingIndicator?.classList.add("is-visible");
    scrollToBottom();
  }

  function hideTyping() {
    dom.typingIndicator?.classList.remove("is-visible");
  }

  /* ========================================================================
     LOADING STATE
     ======================================================================== */

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
  }

  /* ========================================================================
     BOT RESPONSE (placeholder — swap with a real API call when ready)
     ======================================================================== */

  /**
   * Placeholder "AI" response generator. Replace the body of this function
   * with a real API call (e.g. fetch to your backend) when ready — the rest
   * of the app only depends on this function resolving with a string.
   */
 async function getBotResponse(userText) {

    const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${localStorage.getItem("access_token")}`
},
    body: JSON.stringify({
        message: userText,
        conversation_id: state.backendConversationId
    })
});

    if (!response.ok) {
        throw new Error("Server Error");
    }

    const data = await response.json();

state.backendConversationId = data.conversation_id;

return data.reply;
}

  /* ========================================================================
     SEND MESSAGE
     ======================================================================== */

  async function sendMessage(rawText) {
    const text = (rawText ?? dom.messageTextarea?.value ?? "").trim();
    if (!text || state.isLoading) return;

    appendUserMessage(text);
    resetTextarea();
    setLoading(true);

    try {
      const reply = await getBotResponse(text);
      appendBotMessage(reply);
    } catch (err) {
      console.error("Isolde: failed to get a bot response.", err);
      appendBotMessage("Sorry, something went wrong while generating a response.");
    } finally {
      setLoading(false);
    }
  }

  /* ========================================================================
     CLEAR CHAT
     ======================================================================== */

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

  /* ========================================================================
     TEXTAREA AUTO-RESIZE
     ======================================================================== */

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

  /* ========================================================================
     VOICE INPUT (visual only — no speech recognition implemented)
     ======================================================================== */

  /** Placeholder: start "recording" visual state. Wire up real STT here later. */
  function startVoiceRecording() {
    state.isRecording = true;
    dom.voiceInputBtn?.classList.add("is-recording");
    dom.voiceInputBtn?.setAttribute("title", "Stop recording");
  }

  /** Placeholder: stop "recording" visual state. */
  function stopVoiceRecording() {
    state.isRecording = false;
    dom.voiceInputBtn?.classList.remove("is-recording");
    dom.voiceInputBtn?.setAttribute("title", "Voice input");
  }

  function toggleVoiceRecording() {
    if (state.isRecording) {
      stopVoiceRecording();
    } else {
      startVoiceRecording();
    }
  }

  /* ========================================================================
     FILE UPLOAD (filename preview only — no backend upload)
     ======================================================================== */

  function openFilePicker() {
    dom.fileUploadInput?.click();
  }

  function handleFileSelected(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    // Drop the filename into the composer so the user sees what's attached.
    const textarea = dom.messageTextarea;
    if (textarea) {
      const prefix = textarea.value.trim().length > 0 ? `${textarea.value.trim()}\n` : "";
      textarea.value = `${prefix}📎 ${file.name}`;
      autoResizeTextarea();
      updateSendButtonState();
      textarea.focus();
    }

    // Reset the input so selecting the same file again still fires "change".
    event.target.value = "";
  }

  /* ========================================================================
     COPY MESSAGE
     ======================================================================== */

  async function copyMessage(text, buttonEl) {
    try {
      await navigator.clipboard.writeText(text);
      showCopyFeedback(buttonEl);
    } catch (err) {
      console.error("Isolde: failed to copy message.", err);
      // Fallback for browsers without Clipboard API support.
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
    } catch (err) {
      console.error("Isolde: fallback copy failed.", err);
    }
    document.body.removeChild(textarea);
  }

  function showCopyFeedback(buttonEl) {
    if (!buttonEl) return;
    const originalLabel = buttonEl.dataset.originalLabel ?? buttonEl.textContent;
    buttonEl.dataset.originalLabel = originalLabel;
    buttonEl.textContent = "Copied!";

    clearTimeout(buttonEl._copyResetTimer);
    buttonEl._copyResetTimer = setTimeout(() => {
      buttonEl.textContent = originalLabel;
    }, COPY_FEEDBACK_DURATION);
  }

  /* ========================================================================
     EVENT BINDINGS
     ======================================================================== */

  function bindEvents() {
    // Send message: form submit (covers Send button click + Enter-to-submit
    // fallback), plus explicit Enter/Shift+Enter handling on the textarea.
    dom.messageForm?.addEventListener("submit", (event) => {
      event.preventDefault();
      sendMessage();
    });

    dom.messageTextarea?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
      // Shift + Enter falls through and inserts a newline naturally.
    });

    dom.messageTextarea?.addEventListener("input", () => {
      autoResizeTextarea();
      updateSendButtonState();
    });

    // Suggestion chips on the welcome screen send their label as a message.
    dom.suggestionChips?.forEach((chip) => {
      chip.addEventListener("click", () => {
        sendMessage(chip.textContent.trim());
      });
    });

    // New chat.
    dom.newChatBtn?.addEventListener("click", () => {
      createConversation();
    });

    // Clear chat.
    dom.clearChatBtn?.addEventListener("click", () => {
      clearChat();
    });

    // Theme toggle.
    dom.themeToggleBtn?.addEventListener("click", () => {
      toggleTheme();
    });

    // Voice input (visual only).
    dom.voiceInputBtn?.addEventListener("click", () => {
      toggleVoiceRecording();
    });

    // File upload.
    dom.fileUploadBtn?.addEventListener("click", () => {
      openFilePicker();
    });
    dom.fileUploadInput?.addEventListener("change", handleFileSelected);
}

async function loadProfile() {
    console.log("TOKEN:", localStorage.getItem("access_token"));

    const response = await fetch("/api/profile", {
        headers: {
            "Authorization": `Bearer ${localStorage.getItem("access_token")}`
        }
    });

    if (!response.ok) {
        console.log("Profile not loaded");
        return;
    }

    const user = await response.json();

    console.log("Logged in User:", user);
}

async function loadHistory() {
    const response = await fetch("/api/history", {
        headers: {
            "Authorization": `Bearer ${localStorage.getItem("access_token")}`
        }
    });

    if (!response.ok) return;

    const data = await response.json();

    state.conversations = {};
    state.activeConversationId = null;

    data.conversations.forEach(convo => {
        state.conversations[convo.id] = {
            id: convo.id,
            title: convo.title,
            messages: []
        };
    });

    renderChatHistory();
}
  /* ========================================================================
     INITIALIZATION
     ======================================================================== */

  function initializeApp() {
    restoreTheme();
    loadProfile();
    loadHistory();
    loadChat();

    if (!state.activeConversationId || !state.conversations[state.activeConversationId]) {
        createConversation();
    } else {
        renderChatHistory();
        renderActiveConversation();
    }

    updateSendButtonState();
    bindEvents();
}

  document.addEventListener("DOMContentLoaded", initializeApp);
})();