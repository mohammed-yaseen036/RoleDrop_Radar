import json
from pathlib import Path

from .models import JobPosting, Profile
from .services.intelligence import deterministic_match


def main() -> int:
    dataset_path = Path(__file__).parents[2] / "evaluation" / "labeled_jobs.json"
    records = json.loads(dataset_path.read_text(encoding="utf-8"))
    profile = Profile(
        user_id="evaluation",
        skills=["Python", "FastAPI", "React", "Docker", "LLM", "RAG"],
        target_role_families=["Backend Engineering", "Full-Stack Engineering", "AI/ML Engineering"],
        preferred_locations=["India", "Remote"],
        remote_preference=True,
    )
    predicted: list[tuple[bool, bool]] = []
    for index, record in enumerate(records):
        job = JobPosting(
            source_id="evaluation",
            external_id=str(index),
            identity_hash=str(index),
            content_hash=str(index),
            company=record["company"],
            title=record["title"],
            location=record["location"],
            description=record["description"],
            canonical_url=f"https://example.test/{index}",
            apply_url=f"https://example.test/{index}/apply",
        )
        result = deterministic_match(profile, job)
        predicted.append((result.eligible and result.score >= 75, record["expected_urgent"]))
    true_positive = sum(prediction and expected for prediction, expected in predicted)
    false_positive = sum(prediction and not expected for prediction, expected in predicted)
    false_negative = sum(not prediction and expected for prediction, expected in predicted)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0
    print(
        json.dumps(
            {
                "labeled_jobs": len(records),
                "true_positive": true_positive,
                "false_positive": false_positive,
                "false_negative": false_negative,
                "urgent_precision": round(precision, 3),
                "urgent_recall": round(recall, 3),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

