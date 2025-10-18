import pytest

from backend.app import validate_evaluation


def test_validate_evaluation_sanitises_lists():
    payload = {
        "mode": "TOEFL",
        "criterion_scores": {},
        "equivalent_scores": {},
        "question_breakdown": [{"question_number": 1, "score": 3}, "invalid"],
        "strengths": ["Clear pronunciation", 123],
        "improvements": ["Add more detail", None],
        "specific_examples": {
            "good": ["Used advanced vocabulary", 5],
            "needs_work": ["Limited organisation", {}],
        },
        "detailed_feedback": "Solid response overall.",
    }

    validated = validate_evaluation(payload)

    assert validated["mode"] == "toefl"
    assert validated["question_breakdown"] == [{"question_number": 1, "score": 3}]
    assert validated["strengths"] == ["Clear pronunciation"]
    assert validated["improvements"] == ["Add more detail"]
    assert validated["specific_examples"]["good"] == ["Used advanced vocabulary"]
    assert validated["specific_examples"]["needs_work"] == ["Limited organisation"]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"criterion_scores": []},
        {"criterion_scores": {}, "equivalent_scores": [], "question_breakdown": []},
    ],
)
def test_validate_evaluation_rejects_invalid_payloads(payload):
    with pytest.raises(ValueError):
        validate_evaluation(payload)

