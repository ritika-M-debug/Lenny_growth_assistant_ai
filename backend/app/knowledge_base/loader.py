from dataclasses import dataclass
import json
import os
import yaml

from app.knowledge_base.metadata import DocumentMetadata, extract_metadata
from app.knowledge_base.normalizer import normalize_text

@dataclass
class LoadedDocument:
    metadata: DocumentMetadata
    raw_content: str
    normalized_content: str


def validate_file_path(file_path: str, allowed_base_dirs: list[str] = None) -> str:
    """
    Validates input file path to prevent path traversal attacks.
    Ensures the path resides strictly within the designated base directories or matches an allowed path.
    """
    abs_path = os.path.abspath(file_path)
    if allowed_base_dirs:
        is_safe = False
        for base_dir in allowed_base_dirs:
            base_abs = os.path.abspath(base_dir)
            if abs_path == base_abs:
                is_safe = True
                break
            try:
                if os.path.commonpath([abs_path, base_abs]) == base_abs:
                    is_safe = True
                    break
            except ValueError:
                # Different drive letters on Windows
                continue
        if not is_safe:
            raise ValueError(f"Access denied: file path '{file_path}' is outside permitted directories.")
    return abs_path


def load_document(file_path: str, allowed_base_dirs: list[str] = None) -> LoadedDocument:
    """
    Loads text content and metadata from a local file.
    Supports .txt, .md, .json files cleanly. Handles .pdf if PyPDF/pdfplumber is available.
    Safely separates YAML frontmatter from transcript body content.
    """
    safe_path = validate_file_path(file_path, allowed_base_dirs)

    if not os.path.exists(safe_path):
        raise FileNotFoundError(f"Source file not found: {file_path}")

    ext = os.path.splitext(safe_path)[1].lower()
    frontmatter = None
    body_content = ""

    if ext in ['.txt', '.md']:
        with open(safe_path, 'r', encoding='utf-8', errors='replace') as f:
            raw_content = f.read()

        # Parse YAML frontmatter safely and separate from body
        if raw_content.startswith("---"):
            parts = raw_content.split("---", 2)
            if len(parts) >= 3:
                try:
                    parsed = yaml.safe_load(parts[1])
                    if isinstance(parsed, dict):
                        frontmatter = parsed
                except Exception as yaml_err:
                    print(f"Notice: Malformed frontmatter in {file_path} ({yaml_err}). Using raw text.")
                    frontmatter = None

                body_content = parts[2].strip()
            else:
                body_content = raw_content.strip()
        else:
            body_content = raw_content.strip()

    elif ext == '.json':
        with open(safe_path, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
            if isinstance(data, dict):
                raw_content = data.get('content') or data.get('text') or json.dumps(data, indent=2)
                frontmatter = data.get('metadata') if isinstance(data.get('metadata'), dict) else None
            else:
                raw_content = json.dumps(data, indent=2)
        body_content = raw_content

    elif ext == '.pdf':
        try:
            import pypdf
            reader = pypdf.PdfReader(safe_path)
            pages = [page.extract_text() for page in reader.pages if page.extract_text()]
            raw_content = "\n\n".join(pages)
            body_content = raw_content
        except ImportError:
            raise ValueError("PDF parsing requires 'pypdf' package to be installed.")
    else:
        raise ValueError(f"Unsupported file format: '{ext}'. Supported formats: .txt, .md, .json, .pdf")

    if not raw_content or not raw_content.strip():
        raise ValueError(f"File '{file_path}' is empty.")

    # If body content ended up empty (e.g. only frontmatter was in file), fall back to raw content
    if not body_content:
        body_content = raw_content

    metadata = extract_metadata(safe_path, raw_content, frontmatter=frontmatter)
    normalized = normalize_text(body_content)

    return LoadedDocument(
        metadata=metadata,
        raw_content=raw_content,
        normalized_content=normalized
    )
