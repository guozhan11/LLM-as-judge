"""Portable comment identifiers shared by evaluation and analysis.

CSV identifiers are logical record IDs, not paths. JSON comments use paths
relative to the project root; legacy absolute paths remain readable.
"""
from pathlib import PurePosixPath


def normalize_comment_id(value):
    """Canonicalize a JSON comment path without changing CSV or unknown IDs."""
    if not isinstance(value, str) or value.startswith("csv:"):
        return value
    portable = value.replace("\\", "/")
    parts = PurePosixPath(portable).parts
    if "comments" not in parts or not portable.lower().endswith(".json"):
        return value
    index = len(parts) - 1 - parts[::-1].index("comments")
    relative = parts[index:]
    if ".." in relative:
        raise ValueError(f"Comment identifier contains parent traversal: {value!r}")
    return PurePosixPath(*relative).as_posix()
