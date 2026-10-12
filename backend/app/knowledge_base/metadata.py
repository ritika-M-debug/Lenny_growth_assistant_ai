from dataclasses import dataclass, asdict
import hashlib
import os
import re
from typing import Optional, List, Dict, Any

@dataclass
class DocumentMetadata:
    title: str
    source_type: str  # e.g., 'podcast', 'newsletter', 'document', 'synthetic_test'
    file_path: str
    file_hash: str
    author: Optional[str] = None
    guest: Optional[str] = None
    episode_title: Optional[str] = None
    publication_date: Optional[str] = None
    source_url: Optional[str] = None
    youtube_url: Optional[str] = None
    video_id: Optional[str] = None
    description: Optional[str] = None
    channel: Optional[str] = None
    keywords: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def compute_file_hash(content: str | bytes) -> str:
    """Computes SHA256 hash of content for idempotent duplicate detection."""
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


def extract_metadata(
    file_path: str,
    raw_content: str,
    frontmatter: Optional[Dict[str, Any]] = None
) -> DocumentMetadata:
    """
    Extracts metadata from frontmatter or content headers if available,
    falling back to clean filename derivation. Does not fabricate non-existent fields.
    """
    filename = os.path.basename(file_path)
    base_name = os.path.splitext(filename)[0]

    # Defaults derived strictly from filename/path
    default_title = base_name.replace('_', ' ').replace('-', ' ').title()
    if default_title.lower() == "transcript":
        # Derive title from parent directory (e.g. episodes/elena-verna/transcript.md)
        parent_dir = os.path.basename(os.path.dirname(os.path.abspath(file_path)))
        if parent_dir and parent_dir.lower() not in ["raw", "episodes"]:
            default_title = parent_dir.replace('_', ' ').replace('-', ' ').title()

    title = default_title
    source_type = "document"
    author = None
    guest = None
    episode_title = None
    publication_date = None
    source_url = None
    youtube_url = None
    video_id = None
    description = None
    channel = None
    keywords = None

    if "podcast" in file_path.lower() or "transcript" in file_path.lower() or "episode" in file_path.lower():
        source_type = "podcast"
    elif "newsletter" in file_path.lower():
        source_type = "newsletter"
    elif "test" in file_path.lower() or "synthetic" in file_path.lower():
        source_type = "synthetic_test"

    # 1. Use parsed frontmatter dict if provided
    if frontmatter and isinstance(frontmatter, dict):
        if frontmatter.get("title"):
            title = str(frontmatter["title"]).strip()
        if frontmatter.get("guest"):
            guest = str(frontmatter["guest"]).strip()
            author = guest
        elif frontmatter.get("author"):
            author = str(frontmatter["author"]).strip()
        elif frontmatter.get("speaker"):
            author = str(frontmatter["speaker"]).strip()

        if frontmatter.get("episode_title"):
            episode_title = str(frontmatter["episode_title"]).strip()
        elif title and title != default_title:
            episode_title = title

        if frontmatter.get("publish_date"):
            publication_date = str(frontmatter["publish_date"]).strip()
        elif frontmatter.get("publication_date"):
            publication_date = str(frontmatter["publication_date"]).strip()
        elif frontmatter.get("date"):
            publication_date = str(frontmatter["date"]).strip()

        if frontmatter.get("youtube_url"):
            youtube_url = str(frontmatter["youtube_url"]).strip()
            source_url = youtube_url
        elif frontmatter.get("source_url"):
            source_url = str(frontmatter["source_url"]).strip()
        elif frontmatter.get("url"):
            source_url = str(frontmatter["url"]).strip()

        if frontmatter.get("video_id"):
            video_id = str(frontmatter["video_id"]).strip()
        if frontmatter.get("description"):
            description = str(frontmatter["description"]).strip()
        if frontmatter.get("channel"):
            channel = str(frontmatter["channel"]).strip()
        if frontmatter.get("keywords") and isinstance(frontmatter["keywords"], list):
            keywords = [str(k).strip() for k in frontmatter["keywords"] if k]

        if frontmatter.get("source_type"):
            source_type = str(frontmatter["source_type"]).strip()
        elif frontmatter.get("type"):
            source_type = str(frontmatter["type"]).strip()

    # 2. Fall back to manual line-by-line parsing if frontmatter dict not passed
    elif raw_content.startswith("---"):
        parts = raw_content.split("---", 2)
        if len(parts) >= 3:
            header_lines = parts[1].strip().split("\n")
            for line in header_lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip().lower()
                    val = val.strip().strip('"\'')
                    if key == "title" and val:
                        title = val
                    elif key in ["source_type", "type"] and val:
                        source_type = val
                    elif key == "guest" and val:
                        guest = val
                        author = val
                    elif key in ["author", "speaker"] and val:
                        author = val
                    elif key in ["episode_title", "episode"] and val:
                        episode_title = val
                    elif key in ["publish_date", "publication_date", "date"] and val:
                        publication_date = val
                    elif key in ["youtube_url", "source_url", "url"] and val:
                        source_url = val
                        if "youtube.com" in val:
                            youtube_url = val
                    elif key == "video_id" and val:
                        video_id = val

    file_hash = compute_file_hash(raw_content)

    return DocumentMetadata(
        title=title,
        source_type=source_type,
        file_path=file_path,
        file_hash=file_hash,
        author=author,
        guest=guest,
        episode_title=episode_title,
        publication_date=publication_date,
        source_url=source_url,
        youtube_url=youtube_url,
        video_id=video_id,
        description=description,
        channel=channel,
        keywords=keywords
    )
