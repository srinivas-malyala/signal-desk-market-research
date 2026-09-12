"""Deterministic HTML normalization, section extraction, and research chunking."""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser

BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "header",
        "hr",
        "li",
        "p",
        "section",
        "table",
        "tr",
    }
)
IGNORED_TAGS = frozenset({"script", "style", "noscript"})
ITEM_HEADING = re.compile(r"(?im)^\s*(item\s+(?:1a|1b|1c|1|2|3|7a|7|8)[.]?\s*[^\n]*)$")
SELECTED_ITEM = re.compile(r"(?i)^item\s+(?:1|1a|2|7|7a|8)\b")
BOILERPLATE = re.compile(
    r"(?i)^(?:united states )?securities and exchange commission$|^form (?:10-[kq]|8-k)$|^page \d+$"
)


class FilingHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = tag.lower()
        if normalized in IGNORED_TAGS:
            self.ignored_depth += 1
        elif not self.ignored_depth and normalized in BLOCK_TAGS:
            self.parts.append("\n")
        elif not self.ignored_depth and normalized in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in IGNORED_TAGS and self.ignored_depth:
            self.ignored_depth -= 1
        elif not self.ignored_depth and normalized in BLOCK_TAGS | {"td", "th"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    parser = FilingHTMLParser()
    parser.feed(html)
    parser.close()
    lines: list[str] = []
    seen_boilerplate: set[str] = set()
    for raw_line in "".join(parser.parts).splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" |")
        if not line:
            continue
        key = line.casefold()
        if BOILERPLATE.match(line) and key in seen_boilerplate:
            continue
        if BOILERPLATE.match(line):
            seen_boilerplate.add(key)
        lines.append(line)
    return "\n".join(lines)


def extract_selected_sections(text: str) -> tuple[str, list[str]]:
    matches = list(ITEM_HEADING.finditer(text))
    selected: list[str] = []
    sections: list[str] = []
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        if not SELECTED_ITEM.match(heading):
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.start() : end].strip()
        if section:
            selected.append(heading)
            sections.append(section)
    return ("\n\n".join(sections), selected) if sections else (text.strip(), [])


def normalized_filing(html: str | None) -> dict[str, object]:
    full_text = html_to_text(html)
    selected_text, selected_sections = extract_selected_sections(full_text)
    return {
        "document_text": selected_text,
        "selected_sections": selected_sections,
    }


def build_research_chunks(
    source_type: str,
    source_id: str,
    text: str | None,
    *,
    title: str | None = None,
    ticker: str | None = None,
    source_date: object | None = None,
    document_kind: str | None = None,
    target_tokens: int | None = None,
    max_tokens: int | None = None,
    overlap_tokens: int | None = None,
    parent_tokens: int = 1600,
) -> list[dict[str, object]]:
    """Build stable, section-aware parent/child passages.

    Counts use deterministic whitespace-delimited lexical tokens rather than a
    model-specific tokenizer. This keeps the Spark pipeline lightweight while
    maintaining a conservative bound for the serving embedding model.
    """
    is_article = source_type.casefold() == "article"
    target = target_tokens if target_tokens is not None else (375 if is_article else 500)
    maximum = max_tokens if max_tokens is not None else (450 if is_article else 650)
    overlap = overlap_tokens if overlap_tokens is not None else (50 if is_article else 75)
    if target < 50 or maximum < target or overlap < 0 or overlap >= target:
        raise ValueError("invalid child token targets")
    if parent_tokens < maximum or parent_tokens <= overlap:
        raise ValueError("parent_tokens must be at least max_tokens")

    clean = "\n".join(
        line.strip() for line in re.sub(r"[ \t]+", " ", (text or "")).splitlines() if line.strip()
    )
    if not clean:
        return []
    source_content_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()

    heading_matches = list(ITEM_HEADING.finditer(clean)) if not is_article else []
    sections: list[tuple[str | None, str]] = []
    if heading_matches:
        for section_index, match in enumerate(heading_matches):
            end = heading_matches[section_index + 1].start() if section_index + 1 < len(heading_matches) else len(clean)
            section_text = clean[match.start() : end].strip()
            if section_text:
                sections.append((match.group(1).strip(), section_text))
    else:
        sections.append((None, clean))

    def windows(tokens: list[str], size: int, token_overlap: int = 0) -> list[list[str]]:
        result: list[list[str]] = []
        start = 0
        while start < len(tokens):
            end = min(start + size, len(tokens))
            result.append(tokens[start:end])
            if end == len(tokens):
                break
            start = end - token_overlap
        return result

    context_values = [
        ("Company", title),
        ("Ticker", ticker),
        ("Document", document_kind or source_type),
        ("Date", str(source_date) if source_date is not None else None),
    ]
    context_lines = [f"{label}: {value}" for label, value in context_values if value]
    chunks: list[dict[str, object]] = []
    for section_index, (section_name, section_text) in enumerate(sections):
        section_tokens = section_text.split()
        for parent_index, parent_window in enumerate(windows(section_tokens, parent_tokens)):
            parent_text = " ".join(parent_window)
            parent_id = hashlib.sha256(
                f"{source_type}|{source_id}|{source_content_hash}|{section_index}|{parent_index}".encode()
            ).hexdigest()
            for child_index, child_window in enumerate(windows(parent_window, target, overlap)):
                chunk_text = " ".join(child_window)
                chunk_index = len(chunks)
                chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                chunk_id = hashlib.sha256(
                    f"{parent_id}|{child_index}|{chunk_hash}".encode()
                ).hexdigest()
                embedding_context = [*context_lines]
                if section_name:
                    embedding_context.append(f"Section: {section_name}")
                embedding_context.append(chunk_text)
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "parent_id": parent_id,
                        "chunk_index": chunk_index,
                        "section_name": section_name,
                        "chunk_text": chunk_text,
                        "chunk_to_retrieve": chunk_text,
                        "chunk_to_embed": "\n".join(embedding_context),
                        "chunk_token_count": len(child_window),
                        "parent_text": parent_text,
                        "parent_token_count": len(parent_window),
                        "chunk_content_hash": chunk_hash,
                        "source_content_hash": source_content_hash,
                    }
                )
    return chunks
