// frontend/script.js
(() => {
  "use strict";

  // --- FIX: Remove the invalid dummy token if it exists from previous test ---
  if (localStorage.getItem("access_token") === "guest_token_isolde_2026") {
      localStorage.removeItem("access_token");
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
              chatHistoryList: document.querySelector(".chat-history-list"),
              themeToggleBtn: document.querySelector(".theme-toggle-btn"),
              clearChatBtn: document.querySelector(".clear-chat-btn"),
              logoutBtn: document.querySelector(".logout-btn"),
              chatArea: document.querySelector(".chat-area"),
              welcomeScreen: document.querySelector(".welcome-screen"),
              chatMessages: document.querySelector(".chat-messages"),
              suggestionChips: document.querySelectorAll(".suggestion-chip"),
              typingIndicator: document.querySelector(".typing-indicator"),
              messageForm: document.querySelector(".message-form, form"),
              messageTextarea: document.querySelector(".message-textarea, textarea"),
              sendBtn: document.querySelector(".send-btn, button[type='submit']"),
              fileUploadBtn: document.querySelector(".file-upload-btn, .attachment-btn"),
              fileUploadInput: document.querySelector(".file-upload-input, input[type='file']"),
              voiceInputBtn: document.querySelector(".voice-input-btn, .mic-btn"),
              sidebarUserName: document.getElementById("sidebar-user-name"),
              sidebarUserEmail: document.getElementById("sidebar-user-email"),
              memoryList: document.getElementById("memory-list"),
              clearAllMemoriesBtn: document.getElementById("clear-all-memories"),
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
              item.style.display = "flex";
              item.style.justifyContent = "space-between";
              item.style.alignItems = "center";

              if (conversation.id === state.activeConversationId) {
                  item.classList.add("active");
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

              const deleteBtn = document.createElement("button");
              deleteBtn.type = "button";
              deleteBtn.textContent = "🗑️";
              deleteBtn.title = "Delete chat";
              deleteBtn.style.background = "transparent";
              deleteBtn.style.border = "none";
              deleteBtn.style.cursor = "pointer";
              deleteBtn.style.fontSize = "12px";
              deleteBtn.style.padding = "2px 4px";
              deleteBtn.style.marginLeft = "6px";

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

              item.appendChild(link);
              item.appendChild(deleteBtn);
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

      async function getBotResponse(userText) {
          try {
              const response = await fetch("/api/chat", {
                  method: "POST",
                  headers: getAuthHeaders(true),
                  body: JSON.stringify({
                      message: userText,
                      conversation_id: state.backendConversationId
                  })
              });

              const data = await response.json().catch(() => ({}));

              if (!response.ok) {
                  throw new Error(data.error || "Server Error / Network Error");
              }

              if (data.broadcast) {
                  showBroadcastToast(data.broadcast);
              }

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

              loadMemories();
              return data.reply;
          } catch (err) {
              console.error("Isolde Network/Quota Error:", err);
              throw new Error(err.message || "⚠ Connection Error. Please check your network.");
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
              appendBotMessage(`⚠ ${err.message}`);
          } finally {
              setLoading(false);
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
          saveChat();

          setLoading(true);
          try {
              const reply = await getBotResponse(lastUserText);
              if (reply) {
                  appendBotMessage(reply);
              }
          } catch (err) {
              appendBotMessage(`⚠ ${err.message || "Failed to regenerate response."}`);
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

          dom.clearAllMemoriesBtn?.addEventListener("click", () => {
              clearAllMemories();
          });
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