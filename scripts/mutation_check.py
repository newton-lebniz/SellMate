"""Do the regression tests actually fail when the bugs come back?

A test that can't fail proves nothing. This script puts each known bug back into a scratch
COPY of the project (your files are never touched), runs the test suite, and reports
whether the tests noticed.

    python scripts/mutation_check.py

Every line should say CAUGHT. A MISSED line means a bug could return without any test failing.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LOOKS_UNSURE_HEAD = (
    'def looks_unsure(answer: str) -> bool:\n'
    '    """True if the answer says it doesn\'t know, or opens by handing the question to the seller."""\n'
)
PRICE_RETURN = "    return bool(PRICE_QUESTION.search(text)) and not NOT_A_PLAIN_PRICE_ASK.search(text)"

# (what we break, file, original text, broken text)
BUGS = [
    ("inbox never fills: looks_unsure always False", "backend/app/handoff.py",
     LOOKS_UNSURE_HEAD, "def looks_unsure(answer: str) -> bool:\n    return False\n"),
    ("every answer logged (the Day 2 bug): looks_unsure always True", "backend/app/handoff.py",
     LOOKS_UNSURE_HEAD, "def looks_unsure(answer: str) -> bool:\n    return True\n"),
    ("'contact the seller' after an answer counts as a hand-off", "backend/app/handoff.py",
     "    opening = _SENTENCE_END.split(text.strip(), maxsplit=1)[0]\n", "    opening = text\n"),
    ("price questions go to the model again", "backend/app/handoff.py",
     PRICE_RETURN, "    return False"),
    ("price shortcut answers 'is it negotiable?' with the price", "backend/app/handoff.py",
     PRICE_RETURN, "    return bool(PRICE_QUESTION.search(text))"),
    ("claim guard switched off", "backend/app/claims.py",
     "    text = _listing_text(listing)\n    hard = _unsupported(HARD, text, supplied)",
     "    return listing\n    text = _listing_text(listing)\n    hard = _unsupported(HARD, text, supplied)"),
    ("claim guard trusts the photo notes as confirmation", "backend/app/claims.py",
     '    return " ".join(part for part in (keywords, category or "", seller_notes) if part)',
     '    return " ".join(part for part in (keywords, category or "", seller_notes, "silver gold hand-tied") if part)'),
    ("repeat questions add rows instead of counting", "backend/app/storage.py",
     "                if question_key(existing.question, existing.product_id) == key:",
     "                if False:"),
    ("photo EXIF/GPS kept when resizing", "backend/app/llm.py",
     '    img.save(buf, format="JPEG", quality=85)',
     '    img.save(buf, format="JPEG", quality=85, exif=Image.open(io.BytesIO(raw)).info.get("exif", b""))'),
]


def run_tests(project: Path) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
        cwd=project, capture_output=True, text=True,
    )
    lines = result.stdout.strip().splitlines()
    return result.returncode == 0, (lines[-1] if lines else result.stderr.strip()[-200:])


def main() -> int:
    ok, summary = run_tests(ROOT)
    print(f"Baseline: {summary}")
    if not ok:
        print("Fix the failing tests first; the check only means something from a green baseline.")
        return 2

    problems = []
    for name, rel, original, broken in BUGS:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(
                "__pycache__", ".pytest_cache", ".git", ".venv", "venv", "data"))
            target = project / rel
            text = target.read_text(encoding="utf-8")
            if original not in text:
                print(f"SKIPPED  {name}: the code changed, update this script")
                problems.append(name)
                continue
            target.write_text(text.replace(original, broken, 1), encoding="utf-8")
            passed, summary = run_tests(project)
        print(f"{'MISSED ' if passed else 'CAUGHT '}  {name}  ({summary})")
        if passed:
            problems.append(name)

    print("\nAll known bugs are caught by the tests." if not problems else f"\nNeeds attention: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
