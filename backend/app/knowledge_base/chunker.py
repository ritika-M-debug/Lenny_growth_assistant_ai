from dataclasses import dataclass, asdict
import re

@dataclass
class TextChunk:
    chunk_index: int
    content: str
    char_count: int
    token_estimate: int
    start_char: int
    end_char: int

    def to_dict(self):
        return asdict(self)


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> list[TextChunk]:
    """
    Splits normalized text into overlapping chunks.
    Attempts to break cleanly on paragraph or sentence boundaries.
    
    :param text: The normalized text string.
    :param chunk_size: Target maximum characters per chunk (default 1000).
    :param chunk_overlap: Overlapping character count between adjacent chunks (default 200).
    :return: List of TextChunk objects.
    """
    if not text or not text.strip():
        return []
    
    if chunk_size <= 0:
        chunk_size = 1000
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        chunk_overlap = min(200, chunk_size // 5)

    step = chunk_size - chunk_overlap
    chunks = []
    chunk_index = 0
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        
        # If we are not at the end of the text, try to find a natural boundary
        if end < text_len:
            # Look for paragraph boundary near end
            break_pos = text.rfind('\n\n', start + step // 2, end)
            if break_pos != -1:
                end = break_pos + 2
            else:
                # Look for sentence boundary (. ! ?)
                sentence_break = re.search(r'[.!?]\s', text[start + step // 2:end])
                if sentence_break:
                    end = start + step // 2 + sentence_break.end()

        chunk_content = text[start:end].strip()
        if chunk_content:
            token_est = len(chunk_content.split())
            chunks.append(TextChunk(
                chunk_index=chunk_index,
                content=chunk_content,
                char_count=len(chunk_content),
                token_estimate=token_est,
                start_char=start,
                end_char=end
            ))
            chunk_index += 1

        # Move window forward
        if end >= text_len:
            break
        
        # Advance by step, but do not get stuck
        next_start = end - chunk_overlap
        if next_start <= start:
            next_start = start + step
        start = next_start

    return chunks
