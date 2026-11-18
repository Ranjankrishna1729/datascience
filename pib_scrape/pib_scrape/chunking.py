from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from .article import Article

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘(])")


@dataclass
class TextChunk:
    chunk_id: str
    text: str
    title: str
    prid: str
    url: str
    ministry: str
    posted_on: str
    listing_date: str
    split_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def document(self) -> str:
        header_bits = [self.title]
        if self.ministry:
            header_bits.insert(0, self.ministry)
        if self.posted_on:
            header_bits.append(self.posted_on)
        header = " | ".join(header_bits)
        return f"{header}\n\n{self.text.strip()}"


def chunk_article(
    article: Article,
    *,
    listing_date: str = "",
    max_chars: int = 1800,
) -> list[TextChunk]:
    """
    Paragraph-first chunking with sentence-aware packing.

    - Prefer whole paragraphs.
    - Pack consecutive paragraphs until max_chars.
    - Oversized paragraphs split on sentence boundaries (not mid-sentence).
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", article.body_text) if p.strip()]
    if not paragraphs:
        paragraphs = [article.body_text.strip()] if article.body_text.strip() else []

    packed = _pack_paragraphs(paragraphs, max_chars=max_chars)
    chunks: list[TextChunk] = []
    for i, text in enumerate(packed):
        chunk_id = f"pib-{article.prid}-{i}"
        meta = {
            "prid": article.prid,
            "url": article.url,
            "page_url": article.page_url,
            "title": article.title[:300],
            "ministry": article.ministry[:200],
            "posted_on": article.posted_on,
            "listing_date": listing_date or article.posted_on,
            "split_index": i,
            "char_len": len(text),
            "content_sha1": hashlib.sha1(text.encode("utf-8")).hexdigest()[:12],
            "source": "pib.gov.in",
        }
        chunks.append(
            TextChunk(
                chunk_id=chunk_id,
                text=text,
                title=article.title,
                prid=article.prid,
                url=article.url,
                ministry=article.ministry,
                posted_on=article.posted_on,
                listing_date=listing_date or article.posted_on,
                split_index=i,
                metadata=meta,
            )
        )
    return chunks


def _pack_paragraphs(paragraphs: Sequence[str], *, max_chars: int) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            out.append("\n\n".join(buf))
            buf = []
            buf_len = 0

    for para in paragraphs:
        if len(para) > max_chars:
            flush()
            out.extend(_split_long_paragraph(para, max_chars=max_chars))
            continue
        extra = len(para) + (2 if buf else 0)
        if buf and buf_len + extra > max_chars:
            flush()
        buf.append(para)
        buf_len += extra
    flush()
    return out


def _split_long_paragraph(para: str, *, max_chars: int) -> list[str]:
    sentences = _SENTENCE_END.split(para.strip())
    if len(sentences) == 1:
        # No sentence boundaries — hard wrap on whitespace as last resort
        return _hard_wrap(para, max_chars=max_chars)

    out: list[str] = []
    buf = ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) > max_chars:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(_hard_wrap(sent, max_chars=max_chars))
            continue
        candidate = f"{buf} {sent}".strip() if buf else sent
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            buf = sent
    if buf:
        out.append(buf)
    return out


def _hard_wrap(text: str, *, max_chars: int) -> list[str]:
    words = text.split()
    out: list[str] = []
    buf: list[str] = []
    n = 0
    for w in words:
        add = len(w) + (1 if buf else 0)
        if buf and n + add > max_chars:
            out.append(" ".join(buf))
            buf = [w]
            n = len(w)
        else:
            buf.append(w)
            n += add
    if buf:
        out.append(" ".join(buf))
    return out
