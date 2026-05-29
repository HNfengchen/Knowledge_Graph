from __future__ import annotations

from kg_system.core.config import get_settings


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """按字符长度滑窗分块。骨架阶段不做语义切分，避免引入 tiktoken/分词器。"""
    s = get_settings()
    cs = chunk_size if chunk_size is not None else s.TEXT_CHUNK_SIZE
    ov = overlap if overlap is not None else s.TEXT_CHUNK_OVERLAP
    if cs <= 0:
        raise ValueError("chunk_size must be > 0")
    if ov < 0 or ov >= cs:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    text = text.strip()
    if not text:
        return []
    if len(text) <= cs:
        return [text]

    chunks: list[str] = []
    step = cs - ov
    i = 0
    while i < len(text):
        chunks.append(text[i : i + cs])
        if i + cs >= len(text):
            break
        i += step
    return chunks
