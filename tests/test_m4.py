"""Tests for Module 4: Evaluation."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.m4_eval import load_test_set, evaluate_ragas, failure_analysis, EvalResult

def test_load_test_set():
    ts = load_test_set()
    assert len(ts) > 0 and "question" in ts[0] and "ground_truth" in ts[0]

def test_evaluate_returns_metrics():
    r = evaluate_ragas(["q"], ["a"], [["c"]], ["gt"])
    for k in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        assert k in r and isinstance(r[k], (int, float))

def test_failure_analysis_returns():
    results = [EvalResult("Q1", "A1", ["C1"], "GT1", 0.5, 0.6, 0.4, 0.3)]
    f = failure_analysis(results, bottom_n=1)
    assert len(f) == 1

def test_failure_has_diagnosis():
    results = [EvalResult("Q1", "A1", ["C1"], "GT1", 0.5, 0.6, 0.4, 0.3)]
    f = failure_analysis(results, bottom_n=1)
    if f:
        assert "diagnosis" in f[0] and "suggested_fix" in f[0]


def test_save_report_preserves_evidence(tmp_path):
    import json
    from src.m4_eval import save_report

    sample = EvalResult("Q", "A", ["C"], "GT", 0.8, 0.7, 0.9, 0.6)
    results = {
        "faithfulness": 0.8,
        "answer_relevancy": 0.7,
        "context_precision": 0.9,
        "context_recall": 0.6,
        "per_question": [sample],
        "evaluation_status": "complete",
        "failed_metric_count": 0,
    }
    target = tmp_path / "report.json"
    save_report(results, failure_analysis([sample]), str(target))
    report = json.loads(target.read_text(encoding="utf-8"))
    assert report["per_question"][0]["answer"] == "A"
    assert report["per_question"][0]["contexts"] == ["C"]
    assert report["evaluation_status"] == "complete"
    assert "evaluation_status" not in report["aggregate"]


def test_failed_evaluation_preserves_previous_report(tmp_path):
    from src.m4_eval import save_report

    target = tmp_path / "report.json"
    target.write_text('{"previous": true}', encoding="utf-8")
    save_report({"evaluation_status": "failed", "per_question": []}, [], str(target))
    assert target.read_text(encoding="utf-8") == '{"previous": true}'
    assert (tmp_path / "report_incomplete.json").exists()
