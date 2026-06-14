from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

DOCUMENT_DIR = Path(__file__).resolve().parent.parent / "documents"
TOKEN_PATTERN = re.compile(r"[\wæøåÆØÅ]+", re.UNICODE)
SPREADSHEET_NAMESPACE = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
QUERY_EXPANSIONS = {
    "andelsforeningen": {"ejerforeningen", "foreningen", "vedtægter"},
    "beløb": {"budget", "udgift", "udgifter", "fællesudgifter", "kr", "dkk"},
    "betaler": {"betaling", "betale", "udgift", "udgifter", "fællesudgifter"},
    "bruger": {"budget", "udgift", "udgifter", "fællesudgifter", "betaler"},
    "dyr": {"husdyr", "husorden", "benyttelse", "vedtægter"},
    "forbrug": {"budget", "udgift", "udgifter", "fællesudgifter"},
    "holde": {"husdyr", "husorden", "benyttelse", "tilladt", "vedtægter"},
    "hund": {"husdyr", "husorden", "benyttelse", "vedtægter"},
    "kat": {"husdyr", "husorden", "benyttelse", "vedtægter"},
    "krokodille": {"dyr", "husdyr", "husorden", "benyttelse", "vedtægter"},
    "kæledyr": {"husdyr", "husorden", "benyttelse", "vedtægter"},
    "må": {"tilladt", "husorden", "vedtægter", "godkendelse", "samtykke"},
    "måneden": {"måned", "månedligt", "månedsvis", "månedlig", "pr"},
    "måned": {"månedligt", "månedsvis", "månedlig", "pr"},
    "månedligt": {"måned", "månedsvis", "månedlig", "pr"},
    "penge": {"budget", "udgift", "udgifter", "fællesudgifter", "kr", "dkk"},
    "pris": {"beløb", "total", "subtotal", "kr", "dkk"},
    "udgift": {"budget", "udgifter", "fællesudgifter", "kr", "dkk"},
    "udgifter": {"budget", "udgift", "fællesudgifter", "kr", "dkk"},
}


@dataclass(frozen=True)
class DocumentChunk:
    source: str
    title: str
    text: str


def load_document_chunks(document_dir: Path = DOCUMENT_DIR) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for path in sorted(iter_document_paths(document_dir)):
        source = path.relative_to(document_dir).as_posix()
        if path.suffix.casefold() == ".md":
            content = path.read_text(encoding="utf-8")
            title = extract_title(content, path)
            chunks.extend(split_markdown_document(source, title, content))
        if path.suffix.casefold() == ".xlsx":
            chunks.extend(load_xlsx_chunks(path, source))
    return chunks


def iter_document_paths(document_dir: Path) -> list[Path]:
    return [
        path
        for path in document_dir.rglob("*")
        if path.suffix.casefold() in {".md", ".xlsx"}
    ]


def extract_title(content: str, path: Path) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.removeprefix("# ").strip()
    return path.stem.replace("_", " ").title()


def split_markdown_document(
    source: str,
    title: str,
    content: str,
) -> list[DocumentChunk]:
    sections = re.split(r"(?m)^##\s+", content)
    chunks: list[DocumentChunk] = []
    for section in sections:
        text = section.strip()
        if not text:
            continue
        if text.startswith("# "):
            text = strip_heading(text)
            if not text:
                continue
        chunks.append(DocumentChunk(source=source, title=title, text=text))
    return chunks


def load_xlsx_chunks(path: Path, source: str) -> list[DocumentChunk]:
    with ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        chunks: list[DocumentChunk] = []
        for sheet_path, sheet_name in read_sheet_paths(archive):
            rows = read_sheet_rows(archive, sheet_path, shared_strings)
            text = "\n".join(" | ".join(row) for row in rows if row)
            if text:
                chunks.append(
                    DocumentChunk(
                        source=source,
                        title=f"{path.stem.replace('_', ' ').title()} - {sheet_name}",
                        text=text,
                    )
                )
        return chunks


def read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("x:si", SPREADSHEET_NAMESPACE):
        parts = [
            text.text or ""
            for text in item.findall(".//x:t", SPREADSHEET_NAMESPACE)
        ]
        values.append("".join(parts))
    return values


def read_sheet_paths(archive: ZipFile) -> list[tuple[str, str]]:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    relationships = read_workbook_relationships(archive)
    sheets: list[tuple[str, str]] = []
    for sheet in workbook.findall(".//x:sheet", SPREADSHEET_NAMESPACE):
        name = sheet.attrib.get("name", "Sheet")
        relation_id = sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        target = relationships.get(relation_id or "")
        if target:
            sheets.append((f"xl/{target}", name))
    return sheets


def read_workbook_relationships(archive: ZipFile) -> dict[str, str]:
    root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationships: dict[str, str] = {}
    for relation in root:
        relation_id = relation.attrib.get("Id")
        target = relation.attrib.get("Target")
        if relation_id and target and target.startswith("worksheets/"):
            relationships[relation_id] = target
    return relationships


def read_sheet_rows(
    archive: ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> list[list[str]]:
    root = ElementTree.fromstring(archive.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//x:row", SPREADSHEET_NAMESPACE):
        values = [read_cell_value(cell, shared_strings) for cell in row]
        rows.append([value for value in values if value])
    return rows


def read_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            text.text or ""
            for text in cell.findall(".//x:t", SPREADSHEET_NAMESPACE)
        ).strip()

    value = cell.find("x:v", SPREADSHEET_NAMESPACE)
    if value is None or value.text is None:
        return ""

    raw_value = value.text.strip()
    if cell_type == "s" and raw_value.isdigit():
        index = int(raw_value)
        if 0 <= index < len(shared_strings):
            return shared_strings[index].strip()
    return raw_value


def strip_heading(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def retrieve_chunks(
    question: str,
    chunks: list[DocumentChunk] | None = None,
    limit: int = 4,
) -> list[DocumentChunk]:
    available_chunks = chunks if chunks is not None else load_document_chunks()
    question_tokens = expand_query_tokens(tokenize(question))
    if not question_tokens:
        return available_chunks[:limit]

    scored = [
        (score_chunk(question_tokens, chunk), chunk)
        for chunk in available_chunks
    ]
    ranked = [
        chunk
        for score, chunk in sorted(
            scored,
            key=lambda item: item[0],
            reverse=True,
        )
        if score > 0
    ]
    return ranked[:limit] or available_chunks[:limit]


def tokenize(text: str) -> set[str]:
    return {match.group(0).casefold() for match in TOKEN_PATTERN.finditer(text)}


def expand_query_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for token in tokens:
        expanded.update(QUERY_EXPANSIONS.get(token, set()))
    return expanded


def score_chunk(question_tokens: set[str], chunk: DocumentChunk) -> int:
    chunk_tokens = tokenize(f"{chunk.title} {chunk.text}")
    return len(question_tokens & chunk_tokens)
