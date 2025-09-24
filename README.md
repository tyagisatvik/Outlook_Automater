# Modular AI Email Assistant (Polling + Real-time via Webhooks)

Automates Outlook email triage: fetch via Microsoft Graph, summarize with Google Gemini (or a fast local fallback), and notify via Telegram or console. Supports real-time notifications using Microsoft Graph webhooks with FastAPI.

## Project Structure

```
.
├─ .env
├─ .gitignore
├─ requirements.txt
├─ logger_setup.py
├─ config.py
├─ email_client.py
├─ ai_processor.py
├─ main.py              # On-demand polling workflow
├─ webhook_server.py    # FastAPI server for Graph webhooks (real-time)
└─ notifiers/
   ├─ __init__.py
   ├─ base_notifier.py
   ├─ telegram_notifier.py
   └─ console_notifier.py
```

## Prerequisites

- Python 3.10+
- Azure AD application (App registration)
  - Delegated permissions: Microsoft Graph → `Mail.Read`
  - Under Authentication, enable "Allow public client flows" (for Device Code flow)
- A Google API key enabled for Gemini (optional; app has a local summarizer fallback)
- Optional: Telegram bot token and your chat ID (for Telegram notifications)

## Setup

1. Create and populate the `.env` file (already scaffolded):

```"C:\Program Files\Cloudflare\Cloudflared\cloudflared.exe" tunnel --url http://localhost:8000"C:\Program Files\Cloudflare\Cloudflared\cloudflared.exe" tunnel --url http://localhost:8000
# --- AI & Email ---
GOOGLE_API_KEY="your_gemini_api_key_here"             # Optional; used when SUMMARIZER_MODE=gemini
MICROSOFT_CLIENT_ID="your_azure_app_client_id"
MICROSOFT_TENANT_ID="your_azure_app_tenant_id"
TARGET_EMAIL_ADDRESS="your_full_outlook_email@address.com"  # For display/logging only in delegated mode

# --- Auth Mode ---
# Use delegated (interactive Device Code) auth
AUTH_MODE=delegated

# --- Summarizer Mode ---
# fallback (fast local), or gemini (requires GOOGLE_API_KEY)
SUMMARIZER_MODE=fallback
GEMINI_MODEL=gemini-1.5-flash

# --- Notifier Settings ---
# Choose notifier type: "telegram" or "console" (for testing)
NOTIFIER_TYPE="telegram"

# --- Telegram Bot Credentials ---
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
TELEGRAM_CHAT_ID="your_personal_telegram_chat_id"

# --- Webhook Settings (for real-time) ---
# Public HTTPS URL pointing to this server (e.g., your ngrok URL)
WEBHOOK_PUBLIC_URL="https://<your-ngrok-subdomain>.ngrok.io"

# Shared secret to validate notifications (choose a random string)
CLIENT_STATE_SECRET="change-me"

# Subscription expiration in minutes (Graph allows up to ~4230 for messages; keep smaller and renew)
SUBSCRIPTION_EXP_MIN=60
```

2. Install dependencies:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Ensure your Azure AD app has Graph delegated permissions:

- Add delegated permission `Mail.Read` to Microsoft Graph
- Under Authentication, enable "Allow public client flows"

4. Run the polling app (on-demand digest):

```bat
.venv\Scripts\activate
python main.py
```

If `NOTIFIER_TYPE` is `console`, summaries will print to the terminal and `app.log`.
If `telegram`, a digest is sent to your configured chat.

## Real-time Notifications (Webhooks)

1. Start the FastAPI server:

```bat
.venv\Scripts\activate
uvicorn webhook_server:app --host 0.0.0.0 --port 8000
```

2. Expose it publicly via HTTPS (example using ngrok):

```bat
ngrok http 8000
```

Copy the `https://...ngrok.io` URL and set it as `WEBHOOK_PUBLIC_URL` in `.env`.

3. Seed the delegated token cache (one time, if needed):

- In another terminal, run `python main.py` once and complete the Device Code sign-in.

4. Create the Graph subscription:

With the FastAPI server running and `WEBHOOK_PUBLIC_URL` set, call the subscribe endpoint:

```bat
curl -X POST http://localhost:8000/subscribe
```

If successful, you'll see a subscription id and expiration time. Graph will now POST notifications to `WEBHOOK_PUBLIC_URL/graph/notifications` whenever a new message arrives in your Inbox.

5. Validation handshake:

When you first set the subscription, Graph sends a GET with `validationToken` which our server echoes back automatically.

6. Renewal:

Subscriptions expire. You can:

- Re-run step 4 periodically
- Or keep the server running; it will react to certain lifecycle events by attempting best-effort renewal

## Notes

- The app logs to `app.log` with rotation. Check this file if anything goes wrong.
- Telegram messages are truncated conservatively to avoid Telegram limits.
- Polling fetches unread emails from `/me` Inbox (delegated). Webhooks receive "created" events for new messages and fetch each message by id.
- Keep `AUTH_MODE=delegated`. If you later switch to app-only, you'll need Application permissions and admin consent, and to adjust resource paths.
