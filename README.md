# Suppleanten

Telegram proof of concept for short answers over example documents, with links
to a full-explanation page.

Phase 1 proves the channel loop only:

```text
Telegram -> FastAPI webhook -> document QA -> Telegram reply with static link
```

It answers from local documents only. It does not call Docanizer, store
conversations, validate Telegram webhook secrets, or create answer-specific
share links. Those belong to later phases.

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Open the placeholder page:

```text
http://localhost:8000/telegram-demo
```

Health check:

```bash
curl http://localhost:8000/health
```

## Configuration

`TELEGRAM_DEMO_URL` controls the link included in Telegram replies.

```bash
export TELEGRAM_DEMO_URL="https://example.trycloudflare.com/telegram-demo"
```

If unset, replies use `http://localhost:8000/telegram-demo`.

For local fallback QA, no LLM key is required. The app uses naive retrieval and
returns the most relevant source snippet.

For LLM-backed answers, use OpenAI by default:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4.1-mini"
```

Or use Anthropic:

```bash
export LLM_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="..."
export ANTHROPIC_MODEL="claude-3-5-haiku-latest"
```

`TELEGRAM_BOT_TOKEN` is only needed when registering the real Telegram webhook:

```bash
export TELEGRAM_BOT_TOKEN="123456:secret"
```

Do not commit API keys or bot tokens.

## Local webhook test

```bash
curl -i -X POST http://localhost:8000/telegram/suppleanten/webhook \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 777,
    "message": {
      "message_id": 99,
      "chat": {"id": 12345, "type": "private"},
      "text": "Må jeg holde hund?"
    }
  }'
```

Expected response shape:

```json
{
  "method": "sendMessage",
  "chat_id": 12345,
  "text": "Kort svar: ... Se forklaring og kilder: ...",
  "disable_web_page_preview": false
}
```

Telegram can execute this method response for a real webhook. Local tests can
also inspect the JSON directly without calling Telegram.

## Local QA test

```bash
curl -sS -X POST http://localhost:8000/qa \
  -H 'Content-Type: application/json' \
  -d '{"question":"Må jeg holde hund?"}'
```

Expected response includes an answer and source snippets from `documents/`.

## Telegram demo setup

1. Create or reuse a bot with BotFather in Telegram.
2. Copy the bot token and keep it in your local shell only:

   ```bash
   export TELEGRAM_BOT_TOKEN="123456:secret"
   ```

3. Start the app locally.
4. Expose it with a tunnel:

   ```bash
   cloudflared tunnel --url http://localhost:8000
   # or
   ngrok http 8000
   ```

5. Restart the app with the public demo URL and optional LLM key:

   ```bash
   source ~/.config/shell/secrets.sh
   export TELEGRAM_DEMO_URL="https://<public-tunnel-host>/telegram-demo"
   export TELEGRAM_BOT_TOKEN="${TELEGRAM_TOKEN_SUPPLEANTEN}"
   export OPENAI_API_KEY="..."  # optional; fallback QA works without it
   uvicorn app.main:app --reload
   ```

6. Register the webhook:

   ```bash
   curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
     -d "url=https://<public-tunnel-host>/telegram/suppleanten/webhook"
   ```

7. Send a message to the bot in Telegram.
8. Confirm the reply contains a short document-grounded answer and the
   `/telegram-demo` link.

Inspect the registered webhook:

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

Clear the webhook:

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"
```

## Demo script

1. Message the Telegram bot, for example: `Må jeg holde hund?`
2. Receive short Telegram answer based on files under `documents/`.
3. Open the included link.
4. Show the placeholder full explanation with citations.

## Tests

```bash
pytest
ruff check .
```

## Known limitations

- Example document QA only. No Docanizer Q/A integration.
- Static placeholder link only. No answer-specific share token.
- No database, chat mapping, or conversation state.
- No Telegram webhook secret validation or update idempotency.
- No outbound Telegram Bot API client.
- Naive keyword retrieval only. No embeddings or vector database.
