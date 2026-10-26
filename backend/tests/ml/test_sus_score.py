"""SUS scoring (scripts/sus_score.py) against known reference values."""
import sys

import pytest

from app.core.config import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from sus_score import summarise, sus_score  # noqa: E402


@pytest.mark.parametrize("answers, expected", [
    ([3] * 10, 50.0),                     # neutral everywhere
    ([5, 1] * 5, 100.0),                  # best possible
    ([1, 5] * 5, 0.0),                    # worst possible
    ([4, 2, 4, 1, 4, 2, 5, 1, 4, 2], 82.5),
])
def test_known_scores(answers, expected):
    assert sus_score(answers) == expected


@pytest.mark.parametrize("bad", [[3] * 9, [0] + [3] * 9, [6] + [3] * 9])
def test_rejects_invalid_answers(bad):
    with pytest.raises(ValueError):
        sus_score(bad)


def test_summary_of_two_testers():
    row = {f"q{i}": "3" for i in range(1, 11)}
    rows = [{**row, "tester_id": "T1", "task1_success": "yes", "task2_success": "yes", "task3_success": "no",
             "task1_seconds": "60", "task2_seconds": "90", "task3_seconds": ""},
            {**{f"q{i}": ("5" if i % 2 else "1") for i in range(1, 11)}, "tester_id": "T2", "task1_success": "yes",
             "task2_success": "no", "task3_success": "no", "task1_seconds": "40", "task2_seconds": "", "task3_seconds": ""}]
    result = summarise(rows)
    assert result["scores"] == {"T1": 50.0, "T2": 100.0}
    assert result["mean"] == 75.0
    assert result["tasks"]["task1"] == {"success_rate": 1.0, "median_seconds": 50.0}
    assert result["tasks"]["task3"]["success_rate"] == 0.0
