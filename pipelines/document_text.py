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
    chunk_size: int = 1800,
    overlap: int = 200,
) -> list[dict[str, object]]:
    if chunk_size < 200 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be >= 200 and overlap must be smaller than chunk_size")
    clean = re.sub(r"[ \t]+", " ", (text or "")).strip()
    if not clean:
        return []
    source_content_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
    chunks: list[dict[str, object]] = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        if end < len(clean):
            boundary = max(clean.rfind("\n", start + chunk_size // 2, end), clean.rfind(" ", start + chunk_size // 2, end))
            if boundary > start:
                end = boundary
        chunk_text = clean[start:end].strip()
        index = len(chunks)
        chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        chunk_id = hashlib.sha256(
            f"{source_type}|{source_id}|{source_content_hash}|{index}".encode()
        ).hexdigest()
        chunks.append(
            {
                "chunk_id": chunk_id,
                "chunk_index": index,
                "chunk_text": chunk_text,
                "chunk_content_hash": chunk_hash,
                "source_content_hash": source_content_hash,
            }
        )
        if end == len(clean):
            break
        start = max(end - overlap, start + 1)
    return chunks
