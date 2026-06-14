from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import MAX_TELEGRAM_CHARS, app, build_short_answer, normalize_question

client = TestClient(app)


def telegram_update(text: str | None, chat_id: int = 12345) -> dict[str, object]:
    message: dict[str, object] = {
        "message_id": 99,
        "chat": {"id": chat_id, "type": "private"},
    }
    if text is not None:
        message["text"] = text

    return {
        "update_id": 777,
        "message": message,
    }


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_telegram_demo_page_is_public() -> None:
    response = client.get("/telegram-demo")

    assert response.status_code == 200
    assert "Full explanation" in response.text
    assert "Placeholder citations" in response.text
    assert "Telegram" in response.text


def test_telegram_webhook_returns_send_message(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TELEGRAM_DEMO_URL", "https://example.test/telegram-demo")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = client.post(
        "/telegram/suppleanten/webhook",
        json=telegram_update("Hvad er budgettet for fællesudgifter?", chat_id=456),
    )

    assert response.status_code == 200
    assert response.json() == {
        "method": "sendMessage",
        "chat_id": 456,
        "text": (
            "Jeg fandt dette i budget/ejerforening_budget.xlsx: "
            "Ejerforeningen Hjortholms Allé 36 Hjortholms Allé 36, 2400 "
            "København NV — månedligt budget, fællesudgifter (DKK) "
            "Forudsætninger (fordelingstal) Lejlighed 1 | 0."
            "\n\nMere kontekst: https://example.test/telegram-demo"
        ),
        "disable_web_page_preview": False,
    }


def test_telegram_webhook_ignores_non_text_message() -> None:
    response = client.post("/telegram/suppleanten/webhook", json=telegram_update(None))

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "ignored": True,
        "reason": "no text message",
    }


def test_telegram_webhook_ignores_update_without_message() -> None:
    response = client.post(
        "/telegram/suppleanten/webhook",
        json={"update_id": 778, "callback_query": {"id": "abc"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "ignored": True,
        "reason": "no message",
    }


def test_mock_answer_stays_telegram_sized() -> None:
    answer = build_short_answer("x" * 10_000, "https://example.test/telegram-demo")

    assert len(answer) <= MAX_TELEGRAM_CHARS
    assert "https://example.test/telegram-demo" in answer


def test_normalize_question_uses_fallback_for_empty_body() -> None:
    assert normalize_question(" \n\t ") == "dit spørgsmål"
