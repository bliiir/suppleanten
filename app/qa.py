from __future__ import annotations

import os

import httpx
from pydantic import BaseModel

from app.documents import DocumentChunk, retrieve_chunks

DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


class AnswerSource(BaseModel):
    source: str
    title: str
    quote: str


class QAAnswer(BaseModel):
    question: str
    answer: str
    sources: list[AnswerSource]
    used_llm: bool


async def answer_question(question: str) -> QAAnswer:
    chunks = retrieve_chunks(question)
    sources = [source_from_chunk(chunk) for chunk in chunks]
    if not chunks:
        return QAAnswer(
            question=question,
            answer="Jeg fandt ingen eksempel-dokumenter at svare ud fra.",
            sources=[],
            used_llm=False,
        )

    llm_answer = await generate_llm_answer(question, chunks)
    if llm_answer is not None:
        return QAAnswer(
            question=question,
            answer=llm_answer,
            sources=sources,
            used_llm=True,
        )

    return QAAnswer(
        question=question,
        answer=build_fallback_answer(question, chunks),
        sources=sources,
        used_llm=False,
    )


def source_from_chunk(chunk: DocumentChunk) -> AnswerSource:
    return AnswerSource(
        source=chunk.source,
        title=chunk.title,
        quote=chunk.text[:500],
    )


async def generate_llm_answer(question: str, chunks: list[DocumentChunk]) -> str | None:
    provider = os.getenv("LLM_PROVIDER", "openai").casefold()
    prompt = build_prompt(question, chunks)
    try:
        if provider == "anthropic":
            return await call_anthropic(prompt)
        return await call_openai(prompt)
    except httpx.HTTPError:
        return None


def build_prompt(question: str, chunks: list[DocumentChunk]) -> str:
    context = "\n\n".join(
        f"Kilde: {chunk.source}\nDokumenttitel: {chunk.title}\n{chunk.text}"
        for chunk in chunks
    )
    return f"""
Du er Suppleanten, en kortfattet dansk assistent for en boligforening.
Svar kun ud fra konteksten, men brug hele konteksten aktivt.
Hvis spørgsmålet bruger almindelige ord, så forbind dem med dokumenternes termer:
"penge vi bruger" kan betyde budget, udgifter eller fællesudgifter.
Lav simple beregninger, hvis tallene findes i tabellerne.
Giv det bedste konkrete svar, du kan, og nævn kun usikkerhed hvis konteksten
reelt mangler de nødvendige tal.
Svar på dansk i højst 6 korte sætninger.

Kontekst:
{context}

Spørgsmål:
{question}
""".strip()


async def call_openai(prompt: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            OPENAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": prompt},
        )
    response.raise_for_status()
    payload = response.json()
    return extract_openai_text(payload)


def extract_openai_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    output = payload.get("output")
    if not isinstance(output, list):
        return None

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

    answer = "\n".join(parts).strip()
    if answer:
        return answer
    return None


async def call_anthropic(prompt: str) -> str | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            ANTHROPIC_MESSAGES_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": model,
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    response.raise_for_status()
    payload = response.json()
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    parts = [part.get("text", "") for part in content if isinstance(part, dict)]
    answer = "".join(parts).strip()
    return answer or None


def build_fallback_answer(question: str, chunks: list[DocumentChunk]) -> str:
    del question
    best_chunk = chunks[0]
    first_sentence = best_chunk.text.split(".", maxsplit=1)[0].strip()
    return f"Jeg fandt dette i {best_chunk.source}: {first_sentence}."
