"""
doc_registry.py
Document Lineage Tracking & Book Metadata Registry for the Full Astronomy Corpus.

Features:
1. Scans bilingual_output/ across all 155 books (numeric and named folders).
2. Maps immutable doc_id, standardized bilingual book titles, publication metadata,
   file paths, MD5 checksums, file sizes, and estimated chunk counts.
3. Provides instantaneous lookup for LightRAG chunk contextualization and citation routing.
4. Persists the registry to astronomy_books_registry.json for reproducible orchestration.
"""
import re
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("astronomy_lightrag.doc_registry")

# File & Directory Paths
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

BILINGUAL_OUTPUT_DIR = WORKSPACE_ROOT / "bilingual_output"
QUALITY_REPORTS_DIR = WORKSPACE_ROOT / "quality_reports"
FINAL_REPORT_PATH = QUALITY_REPORTS_DIR / "FINAL_TRANSLATION_REPORT.md"
REGISTRY_JSON_PATH = CURRENT_DIR / "astronomy_books_registry.json"


def compute_file_md5(filepath: Path) -> str:
    """Computes MD5 hash of file contents for change and checkpoint detection."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _parse_final_translation_report(report_path: Path = FINAL_REPORT_PATH) -> Dict[int, str]:
    """Parses authoritative book titles from FINAL_TRANSLATION_REPORT.md table."""
    titles = {}
    if not report_path.exists():
        return titles

    try:
        text = report_path.read_text(encoding="utf-8")
        rows = re.findall(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", text, re.MULTILINE)
        for num_str, title in rows:
            clean_title = title.strip()
            # Remove trailing ellipsis or dots from markdown table formatting
            clean_title = re.sub(r"[…\.]{2,}$", "", clean_title).strip()
            titles[int(num_str)] = clean_title
    except Exception as e:
        logger.warning(f"Error parsing final report titles: {e}")

    return titles


def _get_title_from_quality_report(book_num: int, qr_dir: Path = QUALITY_REPORTS_DIR) -> Optional[str]:
    """Extracts title from individual book quality report if available."""
    qr_file = qr_dir / f"book_{book_num}_quality_report.md"
    if not qr_file.exists():
        return None
    try:
        content = qr_file.read_text(encoding="utf-8")
        match = re.search(r"\*\*书名\*\*[:：]\s*(.+)", content)
        if match:
            t = match.group(1).strip()
            if t and t.lower() != "test book":
                return t
    except Exception:
        pass
    return None


def build_book_registry(
    corpus_dir: Path = BILINGUAL_OUTPUT_DIR,
    compute_hashes: bool = True
) -> Dict[str, Dict[str, Any]]:
    """
    Scans the corpus directory and builds the complete registry for all 155 books.

    Returns:
        dict keyed by canonical doc_id mapping to full book metadata.
    """
    if not corpus_dir.exists():
        logger.error(f"Corpus directory not found: {corpus_dir}")
        return {}

    final_report_titles = _parse_final_translation_report()
    folders = sorted(
        [d for d in corpus_dir.iterdir() if d.is_dir() and d.name.startswith("book_")],
        key=lambda x: x.name
    )

    registry: Dict[str, Dict[str, Any]] = {}

    for folder in folders:
        folder_name = folder.name
        md_files = list(folder.rglob("*_bilingual.md"))
        if not md_files:
            continue

        primary_md = md_files[0]
        file_size = primary_md.stat().st_size

        # Determine doc_id and title
        title = ""
        doc_id = ""

        # Check named POC books
        if folder_name.startswith("book_The ") or folder_name.startswith("book_Hidden") or folder_name.startswith("book_Southern"):
            clean_name = folder_name.replace("book_", "")
            title = clean_name
            # Slugify doc_id: book_the_caldwell_objects_2003
            slug = re.sub(r"[^\w]+", "_", clean_name.lower()).strip("_")
            doc_id = f"book_{slug}"
        else:
            # Numeric books
            m = re.match(r"book_(\d+)", folder_name)
            if m:
                book_num = int(m.group(1))
                doc_id = f"book_{book_num:03d}"

                # 1. Prefer quality report if not generic "Test Book"
                qr_title = _get_title_from_quality_report(book_num)
                if qr_title:
                    title = qr_title
                # 2. Prefer final report title
                elif book_num in final_report_titles:
                    title = final_report_titles[book_num]

        # 3. Fallback to first line of markdown
        if not title or title.lower() == "test book":
            try:
                with open(primary_md, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        l = line.strip()
                        if l.startswith("# "):
                            title = l.replace("# ", "").strip()
                            break
                        elif l and not l.startswith("!") and not l.startswith("<") and len(l) < 80:
                            title = l
                            break
            except Exception:
                pass

        if not title:
            title = folder_name

        standard_title = f"《{title}》"

        file_hash = compute_file_md5(primary_md) if compute_hashes else ""

        # Estimate chunks based on ~1,200 chars per chunk
        estimated_chunks = max(1, file_size // 1200)

        registry[doc_id] = {
            "doc_id": doc_id,
            "folder_name": folder_name,
            "title": title,
            "standard_title": standard_title,
            "file_path": str(primary_md.resolve()),
            "relative_path": str(primary_md.relative_to(corpus_dir)),
            "file_size_bytes": file_size,
            "file_hash": file_hash,
            "estimated_chunks": estimated_chunks,
        }

    return registry


def save_registry_to_json(
    registry: Dict[str, Dict[str, Any]],
    target_path: Path = REGISTRY_JSON_PATH
) -> Path:
    """Saves the book registry to a formatted JSON file."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved registry containing {len(registry)} books to {target_path}")
    return target_path


_LOADED_REGISTRY: Optional[Dict[str, Dict[str, Any]]] = None
_PATH_TO_TITLE_MAP: Optional[Dict[str, str]] = None


def get_book_registry(reload: bool = False) -> Dict[str, Dict[str, Any]]:
    """Returns the cached book registry, loading or generating if necessary."""
    global _LOADED_REGISTRY
    if _LOADED_REGISTRY is not None and not reload:
        return _LOADED_REGISTRY

    if REGISTRY_JSON_PATH.exists() and not reload:
        try:
            with open(REGISTRY_JSON_PATH, "r", encoding="utf-8") as f:
                _LOADED_REGISTRY = json.load(f)
                return _LOADED_REGISTRY
        except Exception as e:
            logger.warning(f"Error reading existing registry ({e}), rebuilding...")

    _LOADED_REGISTRY = build_book_registry()
    save_registry_to_json(_LOADED_REGISTRY, REGISTRY_JSON_PATH)
    return _LOADED_REGISTRY


def get_standard_title_for_chunk(file_path_str: str) -> str:
    """
    Given a chunk's file_path string or book identifier, returns the clean standard title.
    Fast O(1) in-memory lookup.
    """
    global _PATH_TO_TITLE_MAP
    if _PATH_TO_TITLE_MAP is None:
        reg = get_book_registry()
        _PATH_TO_TITLE_MAP = {}
        for doc_id, meta in reg.items():
            st = meta["standard_title"]
            _PATH_TO_TITLE_MAP[doc_id] = st
            _PATH_TO_TITLE_MAP[meta["folder_name"]] = st
            _PATH_TO_TITLE_MAP[meta["title"]] = st
            _PATH_TO_TITLE_MAP[st] = st
            # Relative and normalized paths
            p = meta["file_path"].replace("\\", "/")
            _PATH_TO_TITLE_MAP[p] = st
            _PATH_TO_TITLE_MAP[meta["file_path"]] = st
            rp = meta["relative_path"].replace("\\", "/")
            _PATH_TO_TITLE_MAP[rp] = st
            _PATH_TO_TITLE_MAP[meta["relative_path"]] = st

    if not file_path_str:
        return "《未知天文专著》"

    norm_str = file_path_str.replace("\\", "/")
    if norm_str in _PATH_TO_TITLE_MAP:
        return _PATH_TO_TITLE_MAP[norm_str]
    if file_path_str in _PATH_TO_TITLE_MAP:
        return _PATH_TO_TITLE_MAP[file_path_str]

    # Search for folder match in path string
    for folder_key, title in _PATH_TO_TITLE_MAP.items():
        if f"/{folder_key}/" in norm_str or f"\\{folder_key}\\" in file_path_str:
            return title

    return f"《{Path(file_path_str).stem}》"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Building full 155-book astronomy registry...")
    reg = build_book_registry()
    save_registry_to_json(reg)
    total_size_mb = sum(b["file_size_bytes"] for b in reg.values()) / (1024 * 1024)
    total_est_chunks = sum(b["estimated_chunks"] for b in reg.values())
    print(f"\nSuccessfully registered {len(reg)} books!")
    print(f"Total corpus size: {total_size_mb:.2f} MB")
    print(f"Total estimated chunks: {total_est_chunks:,}")
