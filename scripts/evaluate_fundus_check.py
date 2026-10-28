"""Count how often the fundus check accepts non-eye images and rejects real fundus photos.

Usage (repo root):
    .venv\\Scripts\\python scripts\\evaluate_fundus_check.py --fundus incoming\\dr_v2\\parity --other docs\\screenshots docs\\diagrams

--fundus: folders (or files) of real retinal fundus photos; --other: folders (or files) of non-eye images.
--documents N adds N generated text-on-white document images to the non-eye set.
Prints one line per misclassified image (file name and the measured values) and the totals.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.ml.quality import FundusCheck  # noqa: E402

IMAGE_TYPES = {".jpg", ".jpeg", ".png"}


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        files += sorted(p for p in path.rglob("*") if p.suffix.lower() in IMAGE_TYPES) if path.is_dir() else [path]
    return files


def documents(count: int) -> list[tuple[str, Image.Image]]:
    pages = []
    for i in range(count):
        page = Image.new("RGB", (800, 1000), (245, 245, 240) if i % 2 else (255, 255, 255))
        draw = ImageDraw.Draw(page)
        for y in range(60, 950, 28):
            draw.text((50, y), "Lorem ipsum dolor sit amet, consectetur adipiscing elit " * 2, fill=(20, 20, 20))
        pages.append((f"generated-document-{i}", page))
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fundus", nargs="+", required=True)
    parser.add_argument("--other", nargs="+", required=True)
    parser.add_argument("--documents", type=int, default=6)
    args = parser.parse_args()
    check = FundusCheck()

    fundus = [(p.name, Image.open(p)) for p in collect(args.fundus)]
    other = [(p.name, Image.open(p)) for p in collect(args.other)] + documents(args.documents)
    false_reject = [(n, check.measure(i)) for n, i in fundus if not check.looks_like_fundus(i)]
    false_accept = [(n, check.measure(i)) for n, i in other if check.looks_like_fundus(i)]

    for label, rows in (("REJECTED fundus photo", false_reject), ("ACCEPTED non-eye image", false_accept)):
        for name, m in rows:
            print(f"{label}: {name} " + " ".join(f"{k}={v:.2f}" for k, v in m.items()))
    print(f"fundus photos: {len(fundus)}, wrongly rejected: {len(false_reject)}")
    print(f"non-eye images: {len(other)}, wrongly accepted: {len(false_accept)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
