# ruff: noqa: F811
"""Parcours HTTP : transitions, quatre yeux, acquittement, versions, isolement, audit."""

from app.domain.generation import Sentence
from tests.workflow.world import make_content, world  # noqa: F401

API = "/api/v1"


def tr(w, headers, to, reason=None, d=None):
    return w.client.post(f"{API}/deliverables/{d or w.deliverable}/transitions",
                         json={"to": to, "reason": reason}, headers=headers)


def test_happy_path_and_audit(world):
    w = world
    assert tr(w, w.h_alice, "in_review").json()["state"] == "in_review"
    assert tr(w, w.h_bob, "approved").json()["state"] == "approved"
    rows = w.client.get(f"{API}/audit", params={"object_id": w.deliverable}, headers=w.h_bob).json()
    assert [r["action"] for r in rows] == ["transition", "transition"]
    assert rows[1]["details"]["to"] == "approved" and rows[1]["user_id"] == w.bob


def test_four_eyes_and_role(world):
    w = world
    tr(w, w.h_alice, "in_review")
    r = tr(w, w.h_alice, "approved")           # l'auteur n'est pas relecteur
    assert r.status_code == 403
    w.repo.add_member(w.dossier, w.alice, "reviewer")  # relecteur ET auteur
    r = tr(w, w.h_alice, "approved")
    assert r.status_code == 409 and r.json()["error"]["code"] == "FOUR_EYES"


def test_reject_needs_reason_then_resume(world):
    w = world
    tr(w, w.h_alice, "in_review")
    assert tr(w, w.h_bob, "rejected").json()["error"]["code"] == "REASON_REQUIRED"
    assert tr(w, w.h_bob, "rejected", "trop vague").status_code == 200
    assert tr(w, w.h_alice, "draft").json()["state"] == "draft"
    assert tr(w, w.h_alice, "approved").status_code == 409


def test_failed_sentence_blocks_until_acknowledged(world):
    w = world
    bad = make_content(w.chunk.id, sentences=[Sentence(
        text="Le budget atteint 9 999 euros.", kind="fact", source_labels=["P1"],
        source_ids=[w.chunk.id])])
    r = w.client.put(f"{API}/deliverables/{w.deliverable}/content",
                     json=bad.model_dump(mode="json"), headers=w.h_alice)
    assert r.status_code == 200 and r.json()["version"] == 2
    assert any(x["report"]["issues"] for x in r.json()["reports"])
    tr(w, w.h_alice, "in_review")
    r = tr(w, w.h_bob, "approved")
    assert r.json()["error"]["code"] == "UNACKNOWLEDGED_FAILURES"
    ack = w.client.post(f"{API}/deliverables/{w.deliverable}/acknowledgements",
                        json={"section_key": "constats", "sentence_index": 0}, headers=w.h_bob)
    assert ack.status_code == 201
    assert tr(w, w.h_bob, "approved").status_code == 200
    log = w.client.get(f"{API}/audit", params={"object_id": w.deliverable}, headers=w.h_bob).json()
    assert "sentence.acknowledge" in [a["action"] for a in log]


def test_refusal_needs_acknowledgement_and_missing_section(world):
    w = world
    refus = make_content(w.chunk.id, status="insufficient_evidence", sentences=[])
    w.client.put(f"{API}/deliverables/{w.deliverable}/content",
                 json=refus.model_dump(mode="json"), headers=w.h_alice)
    tr(w, w.h_alice, "in_review")
    assert tr(w, w.h_bob, "approved").json()["error"]["code"] == "INCOMPLETE_SECTIONS"
    w.client.post(f"{API}/deliverables/{w.deliverable}/acknowledgements",
                  json={"section_key": "constats"}, headers=w.h_bob)
    assert tr(w, w.h_bob, "approved").status_code == 200


def test_edit_approved_goes_back_to_draft_and_in_review_locked(world):
    w = world
    tr(w, w.h_alice, "in_review")
    body = make_content(w.chunk.id).model_dump(mode="json")
    r = w.client.put(f"{API}/deliverables/{w.deliverable}/content", json=body, headers=w.h_alice)
    assert r.status_code == 409 and r.json()["error"]["code"] == "NOT_EDITABLE"
    tr(w, w.h_bob, "approved")
    r = w.client.put(f"{API}/deliverables/{w.deliverable}/content", json=body, headers=w.h_alice)
    assert r.status_code == 200
    d = w.client.get(f"{API}/deliverables/{w.deliverable}", headers=w.h_alice).json()
    assert d["state"] == "draft" and d["version"] == 2


def test_versions_diff_restore(world):
    w = world
    new = make_content(w.chunk.id, sentences=[Sentence(
        text="Le comité de pilotage se réunit chaque mois.", kind="fact",
        source_labels=["P1"], source_ids=[w.chunk.id])])
    w.client.put(f"{API}/deliverables/{w.deliverable}/content",
                 json=new.model_dump(mode="json"), headers=w.h_alice)
    vs = w.client.get(f"{API}/deliverables/{w.deliverable}/versions", headers=w.h_alice).json()
    assert [(v["version"], v["origin"]) for v in vs] == [(1, "generated"), (2, "edited")]
    assert w.client.get(f"{API}/deliverables/{w.deliverable}/versions/1",
                        headers=w.h_alice).json()["version"] == 1
    d = w.client.get(f"{API}/deliverables/{w.deliverable}/diff", params={"from": 1, "to": 2},
                     headers=w.h_alice).json()
    assert d["sections"][0]["status"] == "changed"
    r = w.client.post(f"{API}/deliverables/{w.deliverable}/versions/1:restore", headers=w.h_alice)
    assert r.json()["version"] == 3
    vs = w.client.get(f"{API}/deliverables/{w.deliverable}/versions", headers=w.h_alice).json()
    assert vs[-1]["origin"] == "restored"
    assert w.client.post(f"{API}/deliverables/{w.deliverable}/versions/9:restore",
                         headers=w.h_alice).status_code == 404


def test_cross_dossier_is_404_everywhere(world):
    w = world
    h = w.h_carol
    d = w.deliverable
    calls = [
        ("get", f"/deliverables/{d}", None), ("get", f"/deliverables/{d}/versions", None),
        ("get", f"/deliverables/{d}/versions/1", None),
        ("get", f"/deliverables/{d}/diff?from=1&to=1", None),
        ("put", f"/deliverables/{d}/content", {}),
        ("post", f"/deliverables/{d}/versions/1:restore", None),
        ("post", f"/deliverables/{d}/transitions", {"to": "in_review"}),
        ("post", f"/deliverables/{d}/acknowledgements", {"section_key": "constats"}),
        ("post", f"/deliverables/{d}/sections/constats/comments", {"text": "x"}),
        ("get", f"/deliverables/{d}/comments", None),
        ("post", f"/dossiers/{w.dossier}/members", {"user_id": w.carol}),
    ]
    for method, path, body in calls:
        r = getattr(w.client, method)(API + path, headers=h, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, path, r.status_code)


def test_comments_members_and_audit_access(world):
    w = world
    r = w.client.post(f"{API}/deliverables/{w.deliverable}/sections/constats/comments",
                      json={"text": "À reformuler"}, headers=w.h_bob)
    assert r.status_code == 201
    cs = w.client.get(f"{API}/deliverables/{w.deliverable}/comments", headers=w.h_alice).json()
    assert cs[0]["text"] == "À reformuler" and cs[0]["user_id"] == w.bob
    # seul le propriétaire (alice) ou un admin ajoute des membres
    assert w.client.post(f"{API}/dossiers/{w.dossier}/members", json={"user_id": w.carol},
                         headers=w.h_bob).status_code == 403
    assert w.client.post(f"{API}/dossiers/{w.dossier}/members",
                         json={"user_id": w.carol, "role": "reviewer"},
                         headers=w.h_alice).status_code == 201
    assert w.repo.member_role(w.dossier, w.carol) == "reviewer"
    # audit : réservé aux rôles reviewer/admin
    assert w.client.get(f"{API}/audit", headers=w.h_alice).status_code == 403
    assert w.client.get(f"{API}/audit", headers=w.h_bob).status_code == 200


def test_every_action_writes_audit(world):
    w = world
    body = make_content(w.chunk.id).model_dump(mode="json")
    w.client.put(f"{API}/deliverables/{w.deliverable}/content", json=body, headers=w.h_alice)
    w.client.post(f"{API}/deliverables/{w.deliverable}/versions/1:restore", headers=w.h_alice)
    w.client.post(f"{API}/deliverables/{w.deliverable}/sections/constats/comments",
                  json={"text": "ok"}, headers=w.h_alice)
    tr(w, w.h_alice, "in_review")
    log = w.client.get(f"{API}/audit", params={"object_id": w.deliverable}, headers=w.h_bob).json()
    assert [a["action"] for a in log] == [
        "content.edit", "version.restore", "comment.add", "transition"]
    assert all(a["user_id"] == w.alice for a in log)
    allrows = w.client.get(f"{API}/audit", headers=w.h_bob).json()
    assert {"auth.login"} <= {a["action"] for a in allrows}
