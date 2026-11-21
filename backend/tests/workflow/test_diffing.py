from app.domain.generation import DeliverableContent, SectionDraft, Sentence
from app.workflow.diffing import diff_contents


def content(*sections):
    return DeliverableContent(type="tor", language="fr", template_id="t", template_version="1",
                              sections=[SectionDraft(section_key=k, status="ok", sentences=[
                                  Sentence(text=t, kind="transition") for t in texts])
                                  for k, texts in sections])


def test_diff_per_section_and_sentence():
    old = content(("a", ["un", "deux"]), ("b", ["x"]), ("gone", ["y"]))
    new = content(("a", ["un", "trois"]), ("b", ["x"]), ("new", ["z"]))
    d = {x["section_key"]: x for x in diff_contents(old, new)}
    assert d["a"]["status"] == "changed"
    assert {"op": "replace", "old": ["deux"], "new": ["trois"]} in d["a"]["sentences"]
    assert d["b"]["status"] == "unchanged"
    assert d["new"]["status"] == "added" and d["gone"]["status"] == "removed"
