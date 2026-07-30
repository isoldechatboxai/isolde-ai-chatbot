# Isolde — AI Chatbot (Flask + Gemini) — Fully Integrated

A single Flask app that serves both the **Isolde frontend** (HTML/CSS/JS)
and the **backend API** (auth, chat, RAG, feedback, history) from one
process on one origin — no CORS setup needed for normal use.

## What was fixed in this pass

1. **Critical: dead Gemini integration.** The project used the
   `google-generativeai` package with model `gemini-1.5-flash`. Both are
   discontinued — Google shut down all Gemini 1.0/1.5 models and deprecated
   that whole SDK in favor of the new `google-genai` package. Every `/api/chat`
   call would have failed. Rewrote `app/services/provider_router.py` to use
   `google-genai` (`google.genai.Client`, `client.chats.create`,
   `client.models.embed_content`, `client.models.generate_content` for vision),
   updated `requirements.txt` (`google-genai` replaces `google-generativeai`),
   and changed the default model to `gemini-flash-latest` (Google's
   auto-updating alias for their current recommended fast model) in
   `config.py` and `.env.example`.
2. **Frontend/backend not actually connected as "one app".** The frontend was
   a separate folder of static files with no server, and calling the API from
   `file://` would hit CORS (browsers send `Origin: null` for local files,
   which doesn't match any allowlist). Fixed by having Flask serve the
   `frontend/` folder itself (`app/__init__.py` now sets `static_folder`/
   `static_url_path` to the frontend directory and adds a `/` route for
   `index.html`). Now `python run.py` + opening `http://127.0.0.1:5000/` is
   same-origin — CORS doesn't even apply. `frontend/script.js`'s `API_URL`
   was changed from a hardcoded absolute URL to a relative `/api/chat` so it
   works automatically in this mode.
3. **Missing `.env`.** Only `.env.example` existed; the app had no real config
   to run with. Rewrote `.env.example` with working defaults and clear
   comments on which values you must fill in yourself (just the Gemini key —
   everything else has a safe default for local dev).
4. **Stray dev artifacts.** Removed a committed `isolde.db` (SQLite database
   with test data) and cached `__pycache__` folders from the delivered project
   so you start from a clean state.
5. Verified (by actually running the app end-to-end in a sandbox): app boot,
   `/`, `/style.css`, `/script.js`, `/api/health`, `/api/register`,
   `/api/login`, and `/api/chat`'s error handling all work correctly. The
   only thing I couldn't test in my sandbox is a live Gemini call, because my
   sandbox's network policy blocks `generativelanguage.googleapis.com` — the
   request was confirmed to reach that exact host correctly and fail only on
   my sandbox's firewall, not on a code error. It will work on your machine
   with a real key and normal internet access.

Nothing else in the backend (auth, JWT, conversation memory, RAG pipeline,
feedback loop, file upload, rate limiting, logging) needed changes — it was
already correct and is unchanged from the previous review.

## Step-by-step: running on Windows

1. **Install Python 3.11 or 3.12** from [python.org](https://python.org) if
   you don't have it. During install, check "Add Python to PATH".

2. **Open PowerShell** in the project folder (`isolde_backend`):
   ```powershell
   cd path\to\isolde_backend
   ```

3. **Create and activate a virtual environment:**
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```
   Your prompt should now start with `(venv)`.

4. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Create your `.env` file:**
   ```powershell
   copy .env.example .env
   ```
   Open `.env` in Notepad and set:
   - `GEMINI_API_KEY` — get a free key at
     [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   - `FLASK_SECRET_KEY` and `JWT_SECRET_KEY` — replace with any long random
     strings (e.g. mash your keyboard for 40+ characters). Everything else
     can stay as-is for local use.

6. **Run the server:**
   ```powershell
   python run.py
   ```
   You should see `Running on http://127.0.0.1:5000`.

7. **Open the app:** go to **http://127.0.0.1:5000/** in your browser.
   That's it — frontend and backend are the same app now. Type a message
   and Isolde should reply using Gemini.

### If you'd rather run the frontend separately (e.g. VS Code Live Server)

Change `frontend/script.js`'s `API_URL` back to an absolute URL:
```js
const API_URL = "http://127.0.0.1:5000/api/chat";
```
and make sure your frontend's origin (e.g. `http://127.0.0.1:5500`) is
listed in `CORS_ORIGINS` in `.env`.

## Remaining known issues / things to be aware of

- **No real Gemini key ships with this project** — you must add your own in
  `.env` (see step 5). Without it, `/api/chat` returns a clear `503` error
  rather than crashing, but obviously won't generate replies.
- **RAG vector store is a flat JSON file**, not a real vector database —
  fine for a handful of documents, will get slow at scale. See
  `app/services/rag_service.py` for the two functions to swap out if you
  later add ChromaDB/FAISS/Pinecone.
- **Email delivery isn't wired up.** `/api/forgot-password` returns the OTP
  directly in the JSON response (`dev_otp` field) instead of emailing it.
  Fine for local testing; before putting this in front of real users, add
  an SMTP integration (e.g. Flask-Mail) and remove that field.
- **SQLite by default** (`isolde.db`, created automatically on first run).
  Swap `DATABASE_URL` in `.env` for a Postgres connection string for
  production use.
- **Voice chat (`/api/voice-chat`)** expects an already-transcribed
  `transcript` string — it doesn't do its own speech-to-text. Pair it with
  the browser's built-in Web Speech API on the frontend, or a server-side
  STT provider if you want it fully server-driven.
- **No admin dashboard / streaming responses / OCR** — see the earlier
  project notes; these are still just extension points, not implemented.

## Project structure

```
isolde_backend/
├── frontend/              index.html, style.css, script.js (served by Flask)
├── app/
│   ├── models/            User, Conversation, Message, Feedback, UploadedFile
│   ├── routes/            auth, chat, upload, feedback, history, profile
│   ├── services/          provider_router, rag_service, feedback_service,
│   │                      file_service, language_service
│   ├── utils/             logger.py, validators.py
│   └── __init__.py        Flask app factory (serves frontend + registers API)
├── config.py, run.py, requirements.txt, .env.example
├── Dockerfile, docker-compose.yml
└── README.md
```

## Key endpoints

| Method | Endpoint              | Auth      | Purpose                          |
|--------|------------------------|-----------|-----------------------------------|
| GET    | /                       | none      | serves the chat frontend           |
| POST   | /api/register           | none      | create account                    |
| POST   | /api/login              | none      | get JWT                           |
| POST   | /api/forgot-password    | none      | request OTP                       |
| POST   | /api/reset-password     | none      | reset with OTP                    |
| GET/PUT| /api/profile            | JWT       | view/update profile               |
| POST   | /api/chat               | optional  | send a message, get a reply       |
| POST   | /api/voice-chat         | optional  | send a transcript, get a reply    |
| POST   | /api/upload             | optional  | upload file/image for RAG or vision |
| POST   | /api/feedback           | optional  | mark a reply correct/incorrect    |
| GET    | /api/history            | JWT       | list conversations                |
| GET    | /api/history/<id>       | JWT       | get one conversation w/ messages  |
| DELETE | /api/history/<id>       | JWT       | delete one conversation           |
| DELETE | /api/history            | JWT       | delete all history                |
| GET    | /api/health             | none      | health check                      |

`optional` auth means it works for guests (stateless) and gets richer
(saved memory, private documents) once logged in.
