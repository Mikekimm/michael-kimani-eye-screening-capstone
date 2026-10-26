"""Score System Usability Scale (SUS) responses and summarise task results.

Input CSV columns: tester_id, role, device, q1..q10 (1-5), task1_success, task2_success, task3_success
(yes/no), task1_seconds, task2_seconds, task3_seconds, comments.

SUS (Brooke, 1996): odd items contribute (answer - 1), even items contribute (5 - answer); the sum
(0-40) is multiplied by 2.5 to give 0-100.

Usage:  .venv\\Scripts\\python scripts\\sus_score.py docs\\usability\\results.csv
"""
import csv
import statistics
import sys
from pathlib import Path


def sus_score(answers: list[int]) -> float:
    if len(answers) != 10 or any(a not in (1, 2, 3, 4, 5) for a in answers):
        raise ValueError("SUS needs exactly 10 answers, each between 1 and 5.")
    total = sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers))
    return total * 2.5


def summarise(rows: list[dict]) -> dict:
    scores = {row["tester_id"]: sus_score([int(row[f"q{i}"]) for i in range(1, 11)]) for row in rows}
    tasks = {}
    for t in (1, 2, 3):
        done = [row[f"task{t}_success"].strip().lower() == "yes" for row in rows]
        times = [float(row[f"task{t}_seconds"]) for row in rows if row.get(f"task{t}_seconds", "").strip()]
        tasks[f"task{t}"] = {"success_rate": sum(done) / len(done) if done else None,
                             "median_seconds": statistics.median(times) if times else None}
    values = list(scores.values())
    return {"testers": len(rows), "scores": scores,
            "mean": statistics.mean(values) if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None, "tasks": tasks}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    with open(Path(sys.argv[1]), newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("tester_id", "").strip()]
    if not rows:
        print("No tester rows yet.")
        return 1
    result = summarise(rows)
    print(f"Testers: {result['testers']}")
    for tester, score in result["scores"].items():
        print(f"  {tester}: SUS {score:.1f}")
    print(f"SUS mean {result['mean']:.1f} (range {result['min']:.1f}-{result['max']:.1f})")
    for task, info in result["tasks"].items():
        rate = "-" if info["success_rate"] is None else f"{info['success_rate']:.0%}"
        secs = "-" if info["median_seconds"] is None else f"{info['median_seconds']:.0f} s"
        print(f"  {task}: success {rate}, median time {secs}")
    if result["testers"] < 5:
        print("Fewer than 5 testers: report these results as indicative only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
