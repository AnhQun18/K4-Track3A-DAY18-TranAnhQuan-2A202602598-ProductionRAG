from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import json, math, os, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from dataclasses import asdict, dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEST_SET_PATH, OPENAI_MODEL, RAGAS_MAX_WORKERS, EMBEDDING_MODEL


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def _safe_metric_score(value) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return score if math.isfinite(score) else 0.0


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    # 1. Wrap trong try/except — RAGAS cần OPENAI_API_KEY và Python 3.11+.
    # try:
    #     from ragas import evaluate
    #     from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    #     from datasets import Dataset
    #
    #     dataset = Dataset.from_dict({
    #         "question": questions, "answer": answers,
    #         "contexts": contexts, "ground_truth": ground_truths,
    #     })
    #     result = evaluate(dataset, metrics=[faithfulness, answer_relevancy,
    #                                         context_precision, context_recall])
    #     df = result.to_pandas()
    #     per_question = [EvalResult(question=row["question"], answer=row["answer"],
    #         contexts=row["contexts"], ground_truth=row["ground_truth"],
    #         faithfulness=float(row.get("faithfulness", 0.0)),
    #         answer_relevancy=float(row.get("answer_relevancy", 0.0)),
    #         context_precision=float(row.get("context_precision", 0.0)),
    #         context_recall=float(row.get("context_recall", 0.0)))
    #         for _, row in df.iterrows()]
    #     return {"faithfulness": ..., "answer_relevancy": ...,
    #             "context_precision": ..., "context_recall": ..., "per_question": [...]}
    # except Exception as e:
    #     print(f"  ⚠️  RAGAS evaluation failed: {e}")
    #     return zeros
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from ragas.run_config import RunConfig
        from src.llm_client import get_evaluation_llm
        from langchain_community.embeddings import HuggingFaceEmbeddings

        dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        })
        result = evaluate(
            dataset,
            llm=get_evaluation_llm(),
            embeddings=HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL),
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
            run_config=RunConfig(
                timeout=900,
                max_retries=5,
                max_wait=120,
                max_workers=RAGAS_MAX_WORKERS,
            ),
        )
        dataframe = result.to_pandas()
        metric_names = [
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
        ]
        invalid_scores = sum(
            int(dataframe[metric_name].isna().sum())
            if metric_name in dataframe
            else len(dataframe)
            for metric_name in metric_names
        )
        if invalid_scores:
            print(
                f"  ⚠️  RAGAS returned {invalid_scores} invalid scores; "
                "using 0.0 for failed metrics."
            )

        per_question = [
            EvalResult(
                question=row["question"],
                answer=row["answer"],
                contexts=list(row["contexts"]),
                ground_truth=row["ground_truth"],
                faithfulness=_safe_metric_score(row.get("faithfulness", 0.0)),
                answer_relevancy=_safe_metric_score(row.get("answer_relevancy", 0.0)),
                context_precision=_safe_metric_score(row.get("context_precision", 0.0)),
                context_recall=_safe_metric_score(row.get("context_recall", 0.0)),
            )
            for _, row in dataframe.iterrows()
        ]

        count = len(per_question)
        def metric_average(metric_name: str) -> float:
            if not count:
                return 0.0
            return sum(
                getattr(item, metric_name) for item in per_question
            ) / count

        return {
            "faithfulness": metric_average("faithfulness"),
            "answer_relevancy": metric_average("answer_relevancy"),
            "context_precision": metric_average("context_precision"),
            "context_recall": metric_average("context_recall"),
            "per_question": per_question,
            "evaluation_status": "partial" if invalid_scores else "complete",
            "failed_metric_count": invalid_scores,
        }
    except Exception as error:
        print(f"  ⚠️  RAGAS evaluation failed: {error}")
        return {
            "faithfulness": 0.0,
            "answer_relevancy": 0.0,
            "context_precision": 0.0,
            "context_recall": 0.0,
            "per_question": [],
            "evaluation_status": "failed",
            "evaluation_error": str(error),
        }


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    # 1. diagnostic_tree = {
    #        "faithfulness": ("LLM hallucinating", "Tighten prompt, lower temperature"),
    #        "context_recall": ("Missing relevant chunks", "Improve chunking or add BM25"),
    #        "context_precision": ("Too many irrelevant chunks", "Add reranking or metadata filter"),
    #        "answer_relevancy": ("Answer doesn't match question", "Improve prompt template"),
    #    }
    # 2. For each EvalResult: compute avg of 4 metrics, find worst_metric
    # 3. Sort by avg ascending → take bottom_n
    # 4. Return [{"question": ..., "worst_metric": ..., "score": ...,
    #             "diagnosis": ..., "suggested_fix": ...}]
    if bottom_n <= 0:
        return []

    diagnostic_tree = {
        "faithfulness": (
            "LLM hallucinating",
            "Tighten prompt, lower temperature",
        ),
        "context_recall": (
            "Missing relevant chunks",
            "Improve chunking or add BM25",
        ),
        "context_precision": (
            "Too many irrelevant chunks",
            "Add reranking or metadata filter",
        ),
        "answer_relevancy": (
            "Answer doesn't match question",
            "Improve prompt template",
        ),
    }
    failures = []

    for result in eval_results:
        metric_scores = {
            "faithfulness": _safe_metric_score(result.faithfulness),
            "answer_relevancy": _safe_metric_score(result.answer_relevancy),
            "context_precision": _safe_metric_score(result.context_precision),
            "context_recall": _safe_metric_score(result.context_recall),
        }
        average_score = sum(metric_scores.values()) / len(metric_scores)
        worst_metric = min(metric_scores, key=metric_scores.get)
        diagnosis, suggested_fix = diagnostic_tree[worst_metric]
        failures.append({
            "question": result.question,
            "worst_metric": worst_metric,
            "score": average_score,
            "diagnosis": diagnosis,
            "suggested_fix": suggested_fix,
        })

    failures.sort(key=lambda item: item["score"])
    return failures[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "reports/ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    if results.get("evaluation_status") in ("failed", "partial"):
        report_stem, report_extension = os.path.splitext(path)
        path = f"{report_stem}_incomplete{report_extension}"
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    report = {
        "aggregate": {
            key: results.get(key, 0.0)
            for key in ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
        },
        "evaluation_status": results.get("evaluation_status", "unknown"),
        "failed_metric_count": results.get("failed_metric_count", 0),
        "evaluation_error": results.get("evaluation_error"),
        "num_questions": len(results.get("per_question", [])),
        "per_question": [asdict(item) for item in results.get("per_question", [])],
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
