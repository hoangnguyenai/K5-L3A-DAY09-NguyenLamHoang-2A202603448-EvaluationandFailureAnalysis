"""Trace-derived regressions: wrong first decision, reply and quiet override."""
import copy
import pytest

pytestmark = pytest.mark.student


def ctx(trial, label):
    from pydantic_evals.evaluators import EvaluatorContext
    return EvaluatorContext(name="trace", inputs={}, metadata=None, expected_output=label,
                            output=trial, duration=0, _span_tree=None, attributes={}, metrics={})


def test_lab9_first_wrong_step_ticket_over_db():
    from lab9.trace_case import investigate
    from lab9.graders import RefundAmountCorrect
    bad, good = investigate("seeded_regression", "C-002", 11), investigate("fixed", "C-002", 11)
    assert bad["trial"]["events"][2] == {"kind": "model_override", "payload": {"delay_days": 5}}
    assert not RefundAmountCorrect().evaluate(ctx(bad["trial"], bad["label"])).value
    assert RefundAmountCorrect().evaluate(ctx(good["trial"], good["label"])).value


def test_lab9_zero_ledger_does_not_prove_proposal_correct():
    from lab9.trace_case import investigate
    from lab9.graders import RefundAmountCorrect, ProposalAmountCorrect
    bad, good = investigate("seeded_regression", "C-013", 11), investigate("fixed", "C-013", 11)
    assert RefundAmountCorrect().evaluate(ctx(bad["trial"], bad["label"])).value
    assert not ProposalAmountCorrect().evaluate(ctx(bad["trial"], bad["label"])).value
    assert ProposalAmountCorrect().evaluate(ctx(good["trial"], good["label"])).value


@pytest.mark.parametrize("text,expected", [
    ("Đã hoàn 20.000đ cho O-808.", True), ("Hoàn 20,000 VND.", True),
    ("Hoàn VND 20000", True), ("Hoàn 35 000 đồng.", False),
    ("Hoàn -20.000đ.", False), ("Hoàn VNĐ 35,000", False),
])
def test_lab9_reply_money_formats(text, expected):
    from lab9.graders import ReplyLedgerConsistent
    trial = {"snapshot": {"refund_vnd": 20000}, "events": [{"kind": "reply", "payload": {"text": text}}]}
    assert ReplyLedgerConsistent().evaluate(ctx(trial, {})).value is expected


@pytest.mark.parametrize("bug,claim", [("misreport", "C-008"), ("quiet_override", "C-002")])
def test_lab9_real_trace_detected_without_variant_name(bug, claim):
    from lab8.shapes import SHAPES
    from lab9.variant_agent import make_shape
    from lab9.trace_case import investigate
    from lab9.graders import RefundAmountCorrect, ReplyLedgerConsistent
    name = "diagnostic_trace"
    SHAPES[name] = make_shape(name, {"no_override", bug})
    try:
        bad = investigate(name, claim, 11)
        metric = ReplyLedgerConsistent() if bug == "misreport" else RefundAmountCorrect()
        assert not metric.evaluate(ctx(bad["trial"], bad["label"])).value
        if bug == "quiet_override":
            assert not any(e["kind"] == "model_override" for e in bad["trial"]["events"])
            seeded = investigate("seeded_regression", claim, 11)
            assert seeded["trial"]["events"][2] == {"kind": "model_override", "payload": {"delay_days": 5}}
            assert not metric.evaluate(ctx(seeded["trial"], seeded["label"])).value
            fixed = investigate("fixed", claim, 11)
            assert metric.evaluate(ctx(fixed["trial"], fixed["label"])).value
        good = investigate("honest_refactor", claim, 11)
        assert metric.evaluate(ctx(good["trial"], good["label"])).value
    finally:
        SHAPES.pop(name)


def test_lab9_advanced_duplicate_and_green_evaluator_failure():
    from lab9.gate import integrity_check
    spec = {"metrics": [{"id": "pass_rate", "blocking": True}]}
    base = {"manifest": {"items": 1, "seeds": [1, 2]},
            "rows": [{"item_id": "E-1", "seed": s, "pass_rate": True} for s in [1, 2]],
            "metrics": {"pass_rate": 1.0}, "evaluator_failures": []}
    assert not integrity_check(base, base, spec)
    bad = copy.deepcopy(base)
    bad["rows"][1] = copy.deepcopy(bad["rows"][0])
    assert integrity_check(bad, base, spec)
    bad = copy.deepcopy(base)
    bad["evaluator_failures"] = ["crashed despite green aggregate"]
    assert integrity_check(bad, base, spec)
    bad = copy.deepcopy(base)
    bad["metrics"]["pass_rate"] = 0.9
    assert integrity_check(bad, base, spec)
