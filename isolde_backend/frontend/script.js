// frontend/script.js
(() => {
  "use strict";

  if (localStorage.getItem("access_token") === "guest_token_isolde_2026") {
      localStorage.removeItem("access_token");
  }

  if (typeof marked !== 'undefined') {
      marked.setOptions({
          highlight: function(code, lang) {
              if (typeof hljs !== 'undefined' && hljs.getLanguage(lang)) {
                  return hljs.highlight(code, { language: lang }).value;
              }
              return typeof hljs !== 'undefined' ? hljs.highlightAuto(code).value : code;
          },
          breaks: true,
          gfm: true
      });
  }

  const isLoginPage = window.location.pathname.includes("login.html") || window.location.pathname.endsWith("login");
  
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
          searchQuery: "" 
      };

      let speechRecognition = null;
      if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
          const SpeechAuth = window.SpeechRecognition || window.webkitSpeechRecognition;
          speechRecognition = new SpeechAuth();
          speechRecognition.continuous = false;
          speechRecognition.interimResults = false;
          
          speechRecognition.onresult = function(event) {
              const transcript = event.results[0][0].transcript;
              if (dom.messageTextarea) {
                  const currentVal = dom.messageTextarea.value.trim();
                  dom.messageTextarea.value = currentVal ? `${currentVal} ${transcript}` : transcript;
                  autoResizeTextarea();
                  updateSendButtonState();
              }
              stopVoiceRecording();
          };
          
          speechRecognition.onerror = function(event) {
              console.error("Speech recognition error:", event.error);
              stopVoiceRecording();
          };
          
          speechRecognition.onend = function() {
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
              messageTextarea: document.getElementById("chat-message-input") || document.querySelector(".message-textarea, textarea"),
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
              settingsModal: document.getElementById("settings-modal"),
              closeSettingsBtn: document.getElementById("close-settings-btn"),
              sidebarToggleBtn: document.getElementById("sidebar-toggle-btn"),
              appSidebar: document.getElementById("app-sidebar")
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
          state.conversations[id] = { id, title: "New conversation", messages: [], isBackend: false, isPinned: false };
          state.activeConversationId = id;
          state.backendConversationId = null; 
          
          if(dom.chatSearchInput) {
              dom.chatSearchInput.value = "";
              state.searchQuery = "";
          }

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

      async function loadConversationMessages(id) {
          if (!state.conversations[id] || !state.conversations[id].isBackend) return;

          try {
              const response = await fetch(`/api/history/${id}`, {
                  headers: getAuthHeaders()
              });

              if (response.ok) {
                  const data = await response.json();
                  if (data.conversation && data.conversation.messages) {
                      state.conversations[id].messages = data.conversation.messages.map(m => ({
                          role: (m.role === 'user') ? 'user' : 'bot',
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

      async function togglePinChatAPI(id) {
          try {
              const response = await fetch('/api/chat/pin', {
                  method: 'POST',
                  headers: getAuthHeaders(true),
                  body: JSON.stringify({ conversation_id: id })
              });
              const data = await response.json();
              if (response.ok) {
                  showBroadcastToast(data.message);
                  return data.is_pinned;
              }
          } catch (err) {
              console.error("Isolde: Failed to pin chat", err);
          }
          return null;
      }

      function renderChatHistory() {
          if (!dom.chatHistoryList) return;

          let filteredConversations = Object.values(state.conversations);
          if (state.searchQuery.trim() !== "") {
              const q = state.searchQuery.toLowerCase();
              filteredConversations = filteredConversations.filter(c => c.title.toLowerCase().includes(q));
          }

          filteredConversations.sort((a, b) => {
              if (a.isPinned && !b.isPinned) return -1;
              if (!a.isPinned && b.isPinned) return 1;

              const aLast = (a.messages && a.messages.length > 0) ? a.messages[a.messages.length - 1].time : (a.created_at || 0);
              const bLast = (b.messages && b.messages.length > 0) ? b.messages[b.messages.length - 1].time : (b.created_at || 0);
              return new Date(bLast) - new Date(aLast);
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
              link.textContent = conversation.title;
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
              
              renameBtn.addEventListener("mouseover", () => renameBtn.style.opacity = "1");
              renameBtn.addEventListener("mouseout", () => renameBtn.style.opacity = "0.5");

              renameBtn.addEventListener("click", (event) => {
                  event.stopPropagation();
                  link.style.display = "none";
                  actionsDiv.style.display = "none";
                  
                  const input = document.createElement("input");
                  input.type = "text";
                  input.value = conversation.title;
                  input.style.flex = "1";
                  input.style.background = "transparent";
                  input.style.border = "1px solid #6b7280";
                  input.style.color = "inherit";
                  input.style.borderRadius = "4px";
                  input.style.padding = "4px 8px";
                  input.style.marginRight = "8px";
                  input.style.outline = "none";
                  input.style.fontSize = "13px";

                  const saveEdit = async () => {
                      const newTitle = input.value.trim();
                      if (newTitle && newTitle !== conversation.title) {
                          conversation.title = newTitle;
                          saveChat();
                      }
                      renderChatHistory();
                  };

                  input.addEventListener("blur", saveEdit);
                  input.addEventListener("keydown", (e) => {
                      if (e.key === "Enter") saveEdit();
                      if (e.key === "Escape") renderChatHistory();
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
              
              pinBtn.addEventListener("mouseover", () => pinBtn.style.opacity = "1");
              pinBtn.addEventListener("mouseout", () => pinBtn.style.opacity = conversation.isPinned ? "1" : "0.5");

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

              deleteBtn.addEventListener("mouseover", () => deleteBtn.style.opacity = "1");
              deleteBtn.addEventListener("mouseout", () => deleteBtn.style.opacity = "0.5");

              deleteBtn.addEventListener("click", async (event) => {
                  event.stopPropagation();
                  
                  if (conversation.isBackend) {
                      try {
                          await fetch(`/api/history/${conversation.id}`, {
                              method: "DELETE",
                              headers: getAuthHeaders()
                          });
                      } catch (e) {}
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
                  body: JSON.stringify({ rating, comment })
              });
          } catch (err) {
              console.error("Isolde: Feedback submission failed", err);
          }
      }

      async function loadMemories() {
          try {
              const response = await fetch("/api/memory/list", {
                  headers: getAuthHeaders()
              });
              if (response.ok) {
                  const data = await response.json();
                  if (dom.memoryList) {
                      dom.memoryList.innerHTML = "";
                      if (!data.memories || data.memories.length === 0) {
                          dom.memoryList.innerHTML = `<li style="color: #6b7280; font-style: italic;">No memories saved yet.</li>`;
                          return;
                      }
                      data.memories.forEach(mem => {
                          const li = document.createElement("li");
                          li.style.display = "flex";
                          li.style.justifyContent = "space-between";
                          li.style.alignItems = "center";
                          li.style.marginBottom = "4px";
                          li.innerHTML = `<span><b>[${mem.category}]</b> ${escapeHtml(mem.memory)}</span> <button class="delete-memory-btn" data-id="${mem.id}" title="Delete memory" style="background:transparent; border:none; color:#ef4444; cursor:pointer; font-size:10px;">❌</button>`;
                          dom.memoryList.appendChild(li);
                      });

                      dom.memoryList.querySelectorAll(".delete-memory-btn").forEach(btn => {
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
                  headers: getAuthHeaders()
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
                  headers: getAuthHeaders()
              });
              loadMemories();
          } catch (err) {
              console.error("Failed to clear memories", err);
          }
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
              likeBtn.addEventListener("click", () => {
                  submitFeedback("Thumbs Up", "User liked the response");
                  likeBtn.textContent = "✅";
                  likeBtn.disabled = true;
                  dislikeBtn.disabled = true;
              });
              actionsDiv.appendChild(likeBtn);

              const dislikeBtn = document.createElement("button");
              dislikeBtn.type = "button";
              dislikeBtn.title = "Bad response";
              dislikeBtn.textContent = "👎";
              dislikeBtn.style.cursor = "pointer";
              dislikeBtn.style.background = "none";
              dislikeBtn.style.border = "none";
              dislikeBtn.style.fontSize = "14px";
              dislikeBtn.addEventListener("click", () => {
                  submitFeedback("Thumbs Down", "User disliked the response");
                  dislikeBtn.textContent = "✅";
                  likeBtn.disabled = true;
                  dislikeBtn.disabled = true;
              });
              actionsDiv.appendChild(dislikeBtn);

              content.appendChild(actionsDiv);
          }

          article.appendChild(avatar);
          article.appendChild(content);
          dom.chatMessages.appendChild(article);

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
              setTimeout(() => document.body.removeChild(toast), 500);
          }, 8000);
      }

      async function streamBotResponse(userText, botMsgObj, textEl) {
          const model = dom.modelSelect ? dom.modelSelect.value : "Flash-Lite Extended";
          const isNewChat = !state.backendConversationId;

          const response = await fetch("/api/chat/stream", {
              method: "POST",
              headers: getAuthHeaders(true),
              body: JSON.stringify({
                  message: userText,
                  conversation_id: state.backendConversationId,
                  model: model
              })
          });

          if (!response.ok) {
              throw new Error("Server Error / Network Error");
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let accumulatedText = "";

          while (true) {
              const { value, done } = await reader.read();
              if (done) break;

              const chunk = decoder.decode(value, { stream: true });
              const lines = chunk.split("\n\n");

              for (const line of lines) {
                  if (line.startsWith("data: ")) {
                      const dataText = line.replace("data: ", "").trim();
                      if (dataText === "[DONE]") break;
                      if (dataText === "[ERROR]") {
                          throw new Error("Streaming encountered an error.");
                      }

                      accumulatedText += dataText + " ";
                      botMsgObj.text = accumulatedText;

                      if (typeof marked !== 'undefined') {
                          textEl.innerHTML = marked.parse(accumulatedText);
                      } else {
                          textEl.innerHTML = escapeHtml(accumulatedText).replace(/\n/g, "<br>");
                      }
                      scrollToBottom();
                  }
              }
          }

          if (isNewChat) {
              await loadHistory();
              const backendConvos = Object.values(state.conversations).filter(c => c.isBackend);
              if (backendConvos.length > 0) {
                  backendConvos.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
                  const newestRealId = backendConvos[0].id;
                  
                  const oldId = state.activeConversationId;
                  if (oldId !== newestRealId && state.conversations[oldId]) {
                      state.conversations[newestRealId].messages = state.conversations[oldId].messages;
                      state.conversations[newestRealId].isPinned = state.conversations[oldId].isPinned;
                      delete state.conversations[oldId];
                      state.activeConversationId = newestRealId;
                      state.backendConversationId = newestRealId;
                  }
              }
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
              if (conversation.messages[i].role === 'user') {
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
          if (!speechRecognition) {
              alert("Your browser does not support Voice Recognition.");
              return;
          }
          state.isRecording = true;
          dom.voiceInputBtn?.classList.add("is-recording");
          dom.voiceInputBtn?.setAttribute("title", "Stop recording");
          try {
              speechRecognition.start();
          } catch(e) {}
      }

      function stopVoiceRecording() {
          state.isRecording = false;
          dom.voiceInputBtn?.classList.remove("is-recording");
          dom.voiceInputBtn?.setAttribute("title", "Voice input");
          if (speechRecognition) {
              try {
                  speechRecognition.stop();
              } catch(e) {}
          }
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

      async function handleFileSelected(event) {
          const file = event.target.files?.[0];
          if (!file) return;

          if (dom.attachmentMenu) dom.attachmentMenu.classList.remove("show");

          const formData = new FormData();
          formData.append("file", file);

          setLoading(true);
          try {
              appendBotMessage(`Uploading **${file.name}** for RAG document analysis...`);

              const response = await fetch('/api/rag/upload', {
                  method: 'POST',
                  headers: {
                      'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                  },
                  body: formData
              });
              const data = await response.json();

              if (response.ok && data.status === 'success') {
                  appendBotMessage(`✅ Document **${file.name}** Indexed successfully! You can now ask questions about this document.`);
              } else {
                  appendBotMessage(`⚠ Failed to upload document: ${data.message}`);
              }
          } catch (err) {
              console.error("File upload error:", err);
              appendBotMessage(`⚠ Network error during file upload.`);
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
              await fetch('/api/logout', { method: 'POST', headers: getAuthHeaders() });
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

          // 🌟 Robust Toggle for Attachment Menu
          if (dom.toggleAttachmentBtn && dom.attachmentMenu) {
              dom.toggleAttachmentBtn.addEventListener("click", (e) => {
                  e.stopPropagation();
                  dom.attachmentMenu.classList.toggle("show");
              });
          }

          dom.fileUploadInput?.addEventListener("change", handleFileSelected);

          if (dom.logoutBtn) {
              dom.logoutBtn.addEventListener("click", () => {
                  logout();
              });
          }

          dom.clearAllMemoriesBtn?.addEventListener("click", () => {
              clearAllMemories();
          });

          // 🌟 Sidebar Collapse Toggle
          if (dom.sidebarToggleBtn && dom.sidebar) {
              dom.sidebarToggleBtn.addEventListener("click", () => {
                  dom.sidebar.classList.toggle("collapsed");
              });
          }

          document.addEventListener('click', (event) => {
              if (dom.attachmentMenu && dom.toggleAttachmentBtn) {
                  const isClickInside = dom.attachmentMenu.contains(event.target) || dom.toggleAttachmentBtn.contains(event.target);
                  if (!isClickInside) {
                      dom.attachmentMenu.classList.remove("show");
                  }
              }
          });

          if (dom.settingsBtn && dom.settingsModal) {
              dom.settingsBtn.addEventListener("click", () => dom.settingsModal.classList.add("show"));
          }
          if (dom.closeSettingsBtn && dom.settingsModal) {
              dom.closeSettingsBtn.addEventListener("click", () => dom.settingsModal.classList.remove("show"));
          }
      }

      async function loadProfile() {
          try {
              const response = await fetch("/api/profile", {
                  headers: getAuthHeaders()
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

      async function loadHistory() {
          try {
              const response = await fetch("/api/history", {
                  headers: getAuthHeaders()
              });
              if (response.ok) {
                  const data = await response.json();
                  data.conversations?.forEach(convo => {
                      if (!state.conversations[convo.id]) {
                          state.conversations[convo.id] = {
                              id: convo.id,
                              title: convo.title,
                              created_at: convo.created_at, 
                              isBackend: true,
                              isPinned: convo.is_pinned || false, 
                              messages: []
                          };
                      }
                  });
                  renderChatHistory();
              }
          } catch (e) {}
      }

      async function initializeApp() {
          bindDomElements();
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