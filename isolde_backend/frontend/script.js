// frontend/script.js
(() => {
  "use strict";

  // --- SMART AUTH GUARD ---
  const isLoginPage = window.location.pathname.includes("login.html") || window.location.pathname.endsWith("login");
  const token = localStorage.getItem("access_token");

  if (!token && !isLoginPage) {
      window.location.href = "/login.html";
      return;
  }

  if (token && isLoginPage) {
      window.location.href = "/";
      return;
  }

  if (isLoginPage) {
      initLoginPage();
  } else {
      initChatbotApp();
  }

  // ==========================================================================
  // LOGIN PAGE LOGIC
  // ==========================================================================
  function initLoginPage() {
      document.addEventListener('DOMContentLoaded', () => {
          const loginForm = document.getElementById('login-form');
          const loginBtn = document.getElementById('login-btn');
          const guestBtn = document.getElementById('guest-btn');
          const btnText = loginBtn?.querySelector('.btn-text');
          const spinner = loginBtn?.querySelector('.spinner');
          const messageContainer = document.getElementById('message-container');

          const setLoading = (isLoading) => {
              if (isLoading) {
                  btnText?.classList.add('hidden');
                  spinner?.classList.remove('hidden');
                  loginBtn.disabled = true;
                  loginBtn.style.opacity = '0.8';
              } else {
                  btnText?.classList.remove('hidden');
                  spinner?.classList.add('hidden');
                  loginBtn.disabled = false;
                  loginBtn.style.opacity = '1';
              }
          };

          const showMessage = (type, text) => {
              if (!messageContainer) return;
              messageContainer.textContent = text;
              messageContainer.className = `message ${type}`;
              setTimeout(() => {
                  messageContainer.classList.add('hidden');
                  messageContainer.className = 'message hidden';
              }, 4000);
          };

          if (loginForm) {
              loginForm.addEventListener('submit', async (e) => {
                  e.preventDefault();
                  
                  const email = document.getElementById('email').value;
                  const password = document.getElementById('password').value;

                  if (!email || !password) {
                      showMessage('error', 'Please fill in all fields.');
                      return;
                  }

                  setLoading(true);

                  try {
                      const response = await fetch('/api/login', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ email, password })
                      });

                      const data = await response.json();

                      if (response.ok && data.access_token) {
                          localStorage.setItem('access_token', data.access_token);
                          showMessage('success', 'Welcome back! Redirecting...');
                          setTimeout(() => {
                              window.location.href = "/";
                          }, 1000);
                      } else {
                          showMessage('error', data.error || 'Invalid email or password.');
                          setLoading(false);
                      }
                  } catch (err) {
                      console.error('Login failed', err);
                      showMessage('error', 'Server error. Please try again later.');
                      setLoading(false);
                  }
              });
          }

          if (guestBtn) {
              guestBtn.addEventListener('click', () => {
                  localStorage.removeItem('access_token');
                  window.location.href = "/"; 
              });
          }
      });
  }

  // ==========================================================================
  // CHATBOT APP LOGIC (ISOLDE) + PHASE 1 FEATURES
  // ==========================================================================
  function initChatbotApp() {
      const STORAGE_KEYS = {
          THEME: "isolde-theme",
          CONVERSATIONS: "isolde-conversations",
          ACTIVE_CONVERSATION: "isolde-active-conversation",
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
      };

      function bindDomElements() {
          dom = {
              app: document.querySelector(".app"),
              sidebar: document.querySelector(".sidebar"),
              newChatBtn: document.querySelector(".new-chat-btn"),
              chatHistoryList: document.querySelector(".chat-history-list"),
              themeToggleBtn: document.querySelector(".theme-toggle-btn"),
              clearChatBtn: document.querySelector(".clear-chat-btn"),
              logoutBtn: document.querySelector(".logout-btn"),
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
      }

      function generateId() {
          return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
      }

      function formatTime(date) {
          return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      }

      function deriveTitle(text) {
          const trimmed = text.trim().replace(/\s+/g, " ");
          return trimmed.length > 42 ? `${trimmed.slice(0, 42)}…` : trimmed || "New conversation";
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
              console.error("Isolde: failed to load theme from localStorage.", err);
              return null;
          }
      }

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

      function createConversation() {
          const id = generateId();
          state.conversations[id] = { id, title: "New conversation", messages: [], isBackend: false };
          state.activeConversationId = id;
          state.backendConversationId = null; 

          renderChatHistory();
          renderActiveConversation();
          saveChat();

          return id;
      }

      function getActiveConversation() {
          if (!state.activeConversationId || !state.conversations[state.activeConversationId]) {
              createConversation();
          }
          return state.conversations[state.activeConversationId];
      }

      async function loadConversationMessages(id) {
          if (!state.conversations[id] || !state.conversations[id].isBackend) return;

          try {
              const response = await fetch(`/api/history/${id}`, {
                  headers: {
                      "Authorization": `Bearer ${localStorage.getItem("access_token")}`
                  }
              });

              if (response.ok) {
                  const data = await response.json();
                  if (data.conversation && data.conversation.messages) {
                      state.conversations[id].messages = data.conversation.messages.map(m => ({
                          role: m.role,
                          text: m.content,
                          time: m.created_at
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

      function renderChatHistory() {
          if (!dom.chatHistoryList) return;

          const conversations = Object.values(state.conversations).sort((a, b) => {
              const aLast = (a.messages && a.messages.length > 0) ? a.messages[a.messages.length - 1].time : (a.created_at || 0);
              const bLast = (b.messages && b.messages.length > 0) ? b.messages[b.messages.length - 1].time : (b.created_at || 0);
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
              
              link.addEventListener("click", async (event) => {
                  event.preventDefault();
                  await switchConversation(conversation.id);
              });

              item.appendChild(link);
              dom.chatHistoryList.appendChild(item);
          });
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
              renderMessage(message.role, message.text, new Date(message.time));
          });
          scrollToBottom();
      }

      // --- PHASE 1 ENHANCED RENDER MESSAGE (Markdown & Highlighting & Regenerate) ---
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

          // Parse Markdown for bot messages, escape for user
          if (isUser) {
              textEl.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
          } else {
              if (typeof marked !== 'undefined') {
                  textEl.innerHTML = marked.parse(text);
              } else {
                  textEl.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
              }
          }

          const timeEl = document.createElement("span");
          timeEl.className = "message-time";
          timeEl.textContent = formatTime(time);

          content.appendChild(textEl);
          content.appendChild(timeEl);

          if (!isUser) {
              const actionsDiv = document.createElement("div");
              actionsDiv.className = "message-actions";
              actionsDiv.style.display = "flex";
              actionsDiv.style.gap = "8px";
              actionsDiv.style.marginTop = "6px";

              const copyBtn = document.createElement("button");
              copyBtn.className = "copy-message-btn";
              copyBtn.type = "button";
              copyBtn.title = "Copy message";
              copyBtn.textContent = "📋 Copy";
              copyBtn.addEventListener("click", () => copyMessage(text, copyBtn));
              actionsDiv.appendChild(copyBtn);

              // Regenerate Button
              const regenBtn = document.createElement("button");
              regenBtn.className = "regenerate-message-btn";
              regenBtn.type = "button";
              regenBtn.title = "Regenerate response";
              regenBtn.textContent = "↻ Regenerate";
              regenBtn.addEventListener("click", () => regenerateLastResponse());
              actionsDiv.appendChild(regenBtn);

              content.appendChild(actionsDiv);
          }

          article.appendChild(avatar);
          article.appendChild(content);
          dom.chatMessages.appendChild(article);

          // Apply Code Syntax Highlighting if hljs is available
          if (!isUser && typeof hljs !== 'undefined') {
              article.querySelectorAll('pre code').forEach((block) => {
                  hljs.highlightElement(block);
              });
          }

          return article;
      }

      function escapeHtml(str) {
          const div = document.createElement("div");
          div.textContent = str ?? "";
          return div.innerHTML;
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
          if (dom.sendBtn) {
              dom.sendBtn.disabled = isLoading;
          }
          if (isLoading) {
              showTyping();
          } else {
              hideTyping();
          }
      }

      async function getBotResponse(userText) {
          try {
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

              if (response.status === 401) {
                  localStorage.removeItem("access_token");
                  window.location.href = "/login.html";
                  return;
              }

              if (!response.ok) {
                  throw new Error("Server Error / Network Error");
              }

              const data = await response.json();
              const realId = data.conversation_id;

              if (realId && state.activeConversationId !== realId) {
                  const oldId = state.activeConversationId;
                  
                  if (state.conversations[oldId]) {
                      if (!state.conversations[realId]) {
                          state.conversations[realId] = state.conversations[oldId];
                          state.conversations[realId].id = realId;
                          state.conversations[realId].isBackend = true;
                      } else {
                          state.conversations[realId].messages = state.conversations[oldId].messages;
                          state.conversations[realId].isBackend = true;
                      }
                      delete state.conversations[oldId];
                  }

                  state.activeConversationId = realId;
                  state.backendConversationId = realId;
                  
                  renderChatHistory();
                  saveChat();
              } else if (realId) {
                  state.backendConversationId = realId;
                  if (state.conversations[realId]) {
                      state.conversations[realId].isBackend = true;
                  }
              }

              return data.reply;
          } catch (err) {
              console.error("Isolde Network/Quota Error:", err);
              return "⚠ Connection Error / Quota Limit reached. Please check your network or try again later.";
          }
      }

      async function sendMessage(rawText) {
          const text = (rawText ?? dom.messageTextarea?.value ?? "").trim();
          if (!text || state.isLoading) return;

          appendUserMessage(text);
          resetTextarea();
          setLoading(true);

          try {
              const reply = await getBotResponse(text);
              if (reply) {
                  appendBotMessage(reply);
              }
          } catch (err) {
              console.error("Isolde: failed to get a bot response.", err);
              appendBotMessage("⚠ Sorry, something went wrong while generating a response.");
          } finally {
              setLoading(false);
          }
      }

      // Regenerate Last Response Feature
      async function regenerateLastResponse() {
          const conversation = getActiveConversation();
          if (!conversation || conversation.messages.length === 0 || state.isLoading) return;

          // Find last user message
          let lastUserMsgIndex = -1;
          for (let i = conversation.messages.length - 1; i >= 0; i--) {
              if (conversation.messages[i].role === 'user') {
                  lastUserMsgIndex = i;
                  break;
              }
          }

          if (lastUserMsgIndex === -1) return;

          const lastUserText = conversation.messages[lastUserMsgIndex].text;

          // Remove trailing bot messages after the last user message
          conversation.messages = conversation.messages.slice(0, lastUserMsgIndex + 1);
          renderActiveConversation();
          saveChat();

          setLoading(true);
          try {
              const reply = await getBotResponse(lastUserText);
              if (reply) {
                  appendBotMessage(reply);
              }
          } catch (err) {
              appendBotMessage("⚠ Failed to regenerate response.");
          } finally {
              setLoading(false);
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
          state.isRecording = true;
          dom.voiceInputBtn?.classList.add("is-recording");
          dom.voiceInputBtn?.setAttribute("title", "Stop recording");
      }

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

      function openFilePicker() {
          dom.fileUploadInput?.click();
      }

      function handleFileSelected(event) {
          const file = event.target.files?.[0];
          if (!file) return;

          const textarea = dom.messageTextarea;
          if (textarea) {
              const prefix = textarea.value.trim().length > 0 ? `${textarea.value.trim()}\n` : "";
              textarea.value = `${prefix}📎 ${file.name}`;
              autoResizeTextarea();
              updateSendButtonState();
              textarea.focus();
          }

          event.target.value = "";
      }

      async function copyMessage(text, buttonEl) {
          try {
              await navigator.clipboard.writeText(text);
              showCopyFeedback(buttonEl);
          } catch (err) {
              console.error("Isolde: failed to copy message.", err);
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
                  headers: {
                      "Authorization": `Bearer ${localStorage.getItem("access_token")}`
                  }
              });
          } catch (err) {
              console.error("API logout failed, clearing local storage anyway.", err);
          } finally {
              localStorage.removeItem("access_token");
              localStorage.removeItem("user");
              window.location.href = "/login.html";
          }
      }

      function bindEvents() {
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

          dom.fileUploadBtn?.addEventListener("click", () => {
              openFilePicker();
          });
          
          dom.fileUploadInput?.addEventListener("change", handleFileSelected);

          dom.logoutBtn?.addEventListener("click", () => {
              logout();
          });
      }

      async function loadProfile() {
          const response = await fetch("/api/profile", {
              headers: {
                  "Authorization": `Bearer ${localStorage.getItem("access_token")}`
              }
          });

          if (response.status === 401) {
              localStorage.removeItem("access_token");
              window.location.href = "/login.html";
              return;
          }

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

          if (response.status === 401) {
              localStorage.removeItem("access_token");
              window.location.href = "/login.html";
              return;
          }

          if (!response.ok) return;

          const data = await response.json();

          data.conversations.forEach(convo => {
              if (!state.conversations[convo.id]) {
                  state.conversations[convo.id] = {
                      id: convo.id,
                      title: convo.title,
                      created_at: convo.created_at, 
                      isBackend: true, 
                      messages: []
                  };
              } else {
                  state.conversations[convo.id].created_at = convo.created_at;
                  state.conversations[convo.id].isBackend = true;
              }
          });

          renderChatHistory();
      }

      async function initializeApp() {
          bindDomElements();
          restoreTheme();
          loadChat();

          if (localStorage.getItem("access_token")) {
              await loadProfile();
              await loadHistory();
          }

          if (!state.activeConversationId || !state.conversations[state.activeConversationId]) {
              createConversation();
          } else {
              if (state.conversations[state.activeConversationId].isBackend) {
                  state.backendConversationId = state.activeConversationId;
              } else {
                  state.backendConversationId = null;
              }
              
              if (state.conversations[state.activeConversationId].isBackend && state.conversations[state.activeConversationId].messages.length === 0) {
                  await loadConversationMessages(state.activeConversationId);
              }
              
              renderChatHistory();
              renderActiveConversation();
          }

          updateSendButtonState();
          bindEvents();
      }

      document.addEventListener("DOMContentLoaded", initializeApp);
  }
})();