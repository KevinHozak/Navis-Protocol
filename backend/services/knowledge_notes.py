"""Reviewed notes from explicitly selected, bounded Markdown sources."""
import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path
from urllib.parse import quote

from services.vault_access import ApplicationNotePolicy, RESERVED, read_markdown_source
from services.vault_paths import resolve_relative_path

DESTINATIONS = ("Library/Notes", "Library/Knowledge Notes")
FIELDS = ("question", "findings", "uncertainty", "application")


def selected_sources(root, paths):
    if not isinstance(paths, list) or not 1 <= len(paths) <= 5 or any(not isinstance(p, str) for p in paths):
        raise ValueError("Select one to five Markdown source paths.")
    if len(set(paths)) != len(paths):
        raise ValueError("Select each source only once.")
    policy = ApplicationNotePolicy.from_root(root)
    sources = [read_markdown_source(policy, p) for p in paths]
    if sum(len(s["content"]) for s in sources) > 40000 or any(len(s["content"]) > 20000 for s in sources):
        raise ValueError("Selected sources exceed the preview budget; choose smaller notes.")
    if len({s["path"].casefold() for s in sources}) != len(sources):
        raise ValueError("Select each source only once.")
    return {"sources": sources, "destinations": list(DESTINATIONS)}


def save(root, body):
    if not isinstance(body, dict):
        raise ValueError("Invalid note request.")
    fields = {k: body.get(k) for k in FIELDS}
    if any(not isinstance(v, str) or not v.strip() or len(v) > 10000 for v in fields.values()):
        raise ValueError("Complete all four note fields (maximum 10,000 characters each).")
    references = body.get("sources")
    if not isinstance(references, list) or any(not isinstance(s, dict) for s in references):
        raise ValueError("Load the selected sources before saving.")
    sources = selected_sources(root, [s.get("path") for s in references])["sources"]
    if any(s["sha256"] != reference.get("sha256") for s, reference in zip(sources, references)):
        raise ValueError("A selected source changed. Reload the sources and review the note before saving.")
    destination, filename = body.get("destination"), body.get("filename")
    if destination not in DESTINATIONS or not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", filename) or RESERVED.match(filename):
        raise ValueError("Choose a listed destination and an alphanumeric filename with hyphens or underscores.")
    policy = ApplicationNotePolicy.from_root(root)
    target = Path(resolve_relative_path(policy.root, f"{destination}/{filename}.md"))
    for directory in (policy.root / "Library", target.parent):
        if directory.exists():
            info = directory.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("Linked destinations are unavailable.")
        directory.mkdir(exist_ok=True)
    policy.require_root()
    text = "# " + fields["question"].strip().replace("\n", " ") + "\n\n"
    for label, field in (("Findings (reviewed)", "findings"), ("Uncertainty and disagreements", "uncertainty"), ("Practical application", "application")):
        text += f"## {label}\n\n{fields[field].strip()}\n\n"
    text += "## Selected source references\n\n"
    for i, source in enumerate(sources, 1):
        link = quote(os.path.relpath(policy.root / source["path"], target.parent).replace("\\", "/"), safe="/.")
        text += f"- [{i}] [{source['path']}]({link}) — SHA-256: `{source['sha256']}`\n"
    data = text.encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            if os.name == "nt":
                os.rename(temporary, target)
            else:
                os.link(temporary, target)
        except FileExistsError:
            if target.is_symlink() or target.read_bytes() != data:
                raise ValueError("That destination already contains another note. Choose a new filename.") from None
        if target.read_bytes() != data:
            raise ValueError("Saved note could not be verified; retry the same request.")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"saved": True, "path": target.relative_to(policy.root).as_posix(), "sha256": hashlib.sha256(data).hexdigest()}
