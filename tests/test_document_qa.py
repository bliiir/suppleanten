from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

import app.qa as qa_module
from app.documents import load_document_chunks, retrieve_chunks
from app.main import app
from app.qa import build_prompt, extract_openai_text

client = TestClient(app)


def test_loads_example_documents() -> None:
    chunks = load_document_chunks()

    sources = {chunk.source for chunk in chunks}

    assert "vedtægter/vedtaegter.md" in sources
    assert "budget/ejerforening_budget.xlsx" in sources


def test_retrieves_association_rules_for_name_question() -> None:
    chunks = retrieve_chunks("Hvad hedder foreningen?")

    assert chunks[0].source == "vedtægter/vedtaegter.md"
    assert chunks[0].title == "Ejerforeningen Hjortholms Allé 36"


def test_retrieves_xlsx_budget_rows_for_budget_question() -> None:
    chunks = retrieve_chunks("Hvad er budgettet for fællesudgifter?")

    assert chunks[0].source == "budget/ejerforening_budget.xlsx"
    assert "fællesudgifter" in chunks[0].text.casefold()


def test_retrieves_xlsx_budget_for_natural_monthly_spend_question() -> None:
    chunks = retrieve_chunks("Hvor mange penge bruger vi om måneden?")

    assert chunks[0].source == "budget/ejerforening_budget.xlsx"
    assert "månedligt budget" in chunks[0].text.casefold()


def test_retrieves_house_rules_for_animal_permission_question() -> None:
    chunks = retrieve_chunks("Må jeg holde krokodille i andelsforeningen?")

    sources = {chunk.source for chunk in chunks}
    combined_text = "\n".join(chunk.text for chunk in chunks).casefold()
    assert sources == {"vedtægter/vedtaegter.md"}
    assert "husdyr" in combined_text
    assert "husorden" in combined_text


def test_prompt_includes_document_title_for_forening_name_question() -> None:
    chunks = retrieve_chunks("Hvad hedder foreningen?")

    prompt = build_prompt("Hvad hedder foreningen?", chunks)

    assert "Ejerforeningen Hjortholms Allé 36" in prompt


def test_qa_endpoint_returns_fallback_answer_without_api_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = client.post("/qa", json={"question": "Hvorfor stiger boligafgiften?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "Hvorfor stiger boligafgiften?"
    assert payload["used_llm"] is False
    assert "budget/ejerforening_budget.xlsx" in {
        source["source"] for source in payload["sources"]
    }
    assert payload["answer"]


def test_qa_endpoint_falls_back_when_openai_is_rate_limited(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def rate_limited(_prompt: str) -> str | None:
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError(
            "rate limited",
            request=request,
            response=response,
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(qa_module, "call_openai", rate_limited)

    response = client.post("/qa", json={"question": "Må jeg holde hund?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["used_llm"] is False
    assert "vedtægter/vedtaegter.md" in {
        source["source"] for source in payload["sources"]
    }
    assert payload["answer"]


def test_extract_openai_text_supports_output_text() -> None:
    assert extract_openai_text({"output_text": "  Kort svar.  "}) == "Kort svar."


def test_extract_openai_text_supports_structured_response_output() -> None:
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "Første sætning."},
                    {"type": "output_text", "text": "Anden sætning."},
                ],
            }
        ]
    }

    assert extract_openai_text(payload) == "Første sætning.\nAnden sætning."
