from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from app.qa import QAAnswer, answer_question

DEFAULT_DEMO_URL = "http://localhost:8000/telegram-demo"
MAX_TELEGRAM_CHARS = 1600

app = FastAPI(title="Suppleanten Telegram POC")


class TelegramChat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int


class TelegramMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: int | None = None
    chat: TelegramChat
    text: str | None = None


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    update_id: int
    message: TelegramMessage | None = None


class TelegramWebhookResponse(BaseModel):
    method: str
    chat_id: int
    text: str
    disable_web_page_preview: bool = False


class IgnoredTelegramUpdate(BaseModel):
    ok: bool = True
    ignored: bool = True
    reason: str


def get_demo_url() -> str:
    return os.getenv("TELEGRAM_DEMO_URL", DEFAULT_DEMO_URL)


def normalize_question(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return "dit spørgsmål"
    return normalized[:120]


def build_short_answer(answer: str, demo_url: str) -> str:
    normalized_answer = " ".join(answer.split())
    if not normalized_answer:
        normalized_answer = "Jeg kunne ikke finde et svar i dokumenterne."

    message = f"{normalized_answer}\n\nMere kontekst: {demo_url}"
    if len(message) <= MAX_TELEGRAM_CHARS:
        return message

    suffix = f"\n\nMere kontekst: {demo_url}"
    budget = MAX_TELEGRAM_CHARS - len(suffix)
    clipped_answer = normalized_answer[: max(0, budget)].rstrip()
    return f"{clipped_answer}{suffix}"


def build_mock_answer(question: str, demo_url: str) -> str:
    normalized_question = normalize_question(question)
    answer = (
        f"Kort svar: Vi har modtaget: {normalized_question}. "
        f"Se forklaring og kilder: {demo_url}"
    )
    if len(answer) <= MAX_TELEGRAM_CHARS:
        return answer

    suffix = f" Se forklaring og kilder: {demo_url}"
    budget = MAX_TELEGRAM_CHARS - len(suffix) - len("Kort svar: ")
    clipped_question = normalized_question[: max(0, budget)].rstrip()
    return f"Kort svar: {clipped_question}{suffix}"


def build_telegram_reply(chat_id: int, text: str) -> TelegramWebhookResponse:
    return TelegramWebhookResponse(
        method="sendMessage",
        chat_id=chat_id,
        text=text,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class QARequest(BaseModel):
    question: str


@app.post("/qa")
async def qa(request: QARequest) -> QAAnswer:
    return await answer_question(request.question)


@app.get("/telegram-demo", response_class=HTMLResponse)
def telegram_demo() -> str:
    return """
<!doctype html>
<html lang="da">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Suppleanten Telegram demo</title>
    <style>
      body {
        font-family: system-ui, sans-serif;
        margin: 2rem;
        line-height: 1.5;
        max-width: 760px;
      }
      .badge {
        display: inline-block;
        padding: .25rem .5rem;
        background: #eef2ff;
        border-radius: .5rem;
      }
      blockquote {
        border-left: 4px solid #c7d2fe;
        margin-left: 0;
        padding-left: 1rem;
        color: #374151;
      }
    </style>
  </head>
  <body>
    <span class="badge">POC placeholder</span>
    <h1>Full explanation</h1>
    <p>
      This page stands in for the future Docanizer full-answer view. Telegram
      replies stay short while this page carries the explanation, citations,
      and source snippets from the example documents.
    </p>
    <h2>Mock answer</h2>
    <p>
      The current POC answers from two example documents: vedtægter and budget.
      Ask the Telegram bot about pets, subletting, renovation, maintenance,
      reserves, or housing-fee changes.
    </p>
    <h2>Placeholder citations</h2>
    <blockquote>
      Source chunk A: Rules may require approval before changes or special use.
    </blockquote>
    <blockquote>
      Source chunk B: Deadlines and exceptions depend on the specific document
      section.
    </blockquote>
  </body>
</html>
"""


@app.post("/telegram/suppleanten/webhook")
async def telegram_webhook(
    update: TelegramUpdate,
) -> TelegramWebhookResponse | IgnoredTelegramUpdate:
    if update.message is None:
        return IgnoredTelegramUpdate(reason="no message")

    if update.message.text is None:
        return IgnoredTelegramUpdate(reason="no text message")

    qa_answer = await answer_question(update.message.text)
    reply = build_short_answer(qa_answer.answer, get_demo_url())
    return build_telegram_reply(update.message.chat.id, reply)
