"""Différences entre deux versions : par section puis par phrase (difflib)."""

import difflib

from app.domain.generation import DeliverableContent, SectionDraft


def _texts(section: SectionDraft | None) -> list[str]:
    return [s.text for s in section.sentences] if section else []


def diff_section(key: str, old: SectionDraft | None, new: SectionDraft | None) -> dict:
    a, b = _texts(old), _texts(new)
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        ops.append({"op": tag, "old": a[i1:i2], "new": b[j1:j2]})
    if old is None:
        status = "added"
    elif new is None:
        status = "removed"
    else:
        status = "unchanged" if a == b and old.status == new.status else "changed"
    return {"section_key": key, "status": status, "sentences": ops}


def diff_contents(old: DeliverableContent, new: DeliverableContent) -> list[dict]:
    """Une entrée par section (ordre : sections de `new`, puis supprimées)."""
    old_by = {s.section_key: s for s in old.sections}
    new_by = {s.section_key: s for s in new.sections}
    keys = [s.section_key for s in new.sections] + [k for k in old_by if k not in new_by]
    return [diff_section(k, old_by.get(k), new_by.get(k)) for k in keys]
