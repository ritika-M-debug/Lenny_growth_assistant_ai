import re

def normalize_text(text: str) -> str:
    """
    Normalizes text content by cleaning whitespace, control characters,
    and standardizing line breaks.
    """
    if not text:
        return ""
    
    # Standardize line endings to \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove control characters except standard whitespace (\n, \t)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Collapse multiple spaces on individual lines
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.split('\n')]
    
    # Rejoin lines while preserving double newlines for paragraphs
    normalized = '\n'.join(lines)
    normalized = re.sub(r'\n{3,}', '\n\n', normalized)
    
    return normalized.strip()
