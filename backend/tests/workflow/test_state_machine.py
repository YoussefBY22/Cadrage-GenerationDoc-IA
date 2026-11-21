"""Table complète des transitions et des conditions (fonctions pures)."""

import itertools

import pytest

from app.workflow.state_machine import ALLOWED, TransitionContext, WorkflowError, check_transition

STATES = ["draft", "in_review", "approved", "rejected"]


def ctx(current, to, **kw):
    base = {"current": current, "to": to, "reason": "motif", "actor_id": "rev",
            "actor_can_review": True, "version_author_id": "aut",
            "deliverable_author_id": "aut"}
    base.update(kw)
    return TransitionContext(**base)


@pytest.mark.parametrize("current,to", list(itertools.product(STATES, STATES)))
def test_full_transition_table(current, to):
    actor = "aut" if (current, to) == ("in_review", "draft") else "rev"
    c = ctx(current, to, actor_id=actor)
    if (current, to) in ALLOWED:
        check_transition(c)
    else:
        with pytest.raises(WorkflowError) as e:
            check_transition(c)
        assert e.value.code == "INVALID_TRANSITION" and e.value.status == 409


def test_reject_needs_reason():
    for reason in (None, "", "   "):
        with pytest.raises(WorkflowError) as e:
            check_transition(ctx("in_review", "rejected", reason=reason))
        assert e.value.code == "REASON_REQUIRED"


def test_four_eyes_and_override():
    with pytest.raises(WorkflowError) as e:
        check_transition(ctx("in_review", "approved", actor_id="aut"))
    assert e.value.code == "FOUR_EYES"
    check_transition(ctx("in_review", "approved", actor_id="aut", allow_self_approval=True))


def test_approval_requires_reviewer_role():
    with pytest.raises(WorkflowError) as e:
        check_transition(ctx("in_review", "approved", actor_can_review=False))
    assert e.value.status == 403


def test_approval_blocked_by_failures_and_missing_sections():
    with pytest.raises(WorkflowError) as e:
        check_transition(ctx("in_review", "approved", unacknowledged_failures=2))
    assert e.value.code == "UNACKNOWLEDGED_FAILURES"
    with pytest.raises(WorkflowError) as e:
        check_transition(ctx("in_review", "approved", sections_complete=False))
    assert e.value.code == "INCOMPLETE_SECTIONS"


def test_only_author_withdraws():
    with pytest.raises(WorkflowError) as e:
        check_transition(ctx("in_review", "draft", actor_id="rev"))
    assert e.value.code == "AUTHOR_ONLY"
