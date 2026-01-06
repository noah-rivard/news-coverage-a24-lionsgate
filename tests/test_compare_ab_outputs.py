import subprocess
import sys
from pathlib import Path


def test_compare_ab_outputs_generates_side_by_side_report(tmp_path: Path) -> None:
    a_dir = tmp_path / "out-prefixed"
    b_dir = tmp_path / "out-unprefixed"
    a_dir.mkdir()
    b_dir.mkdir()

    a_text = "\n".join(
        [
            "Title: Warner Bros. Discovery Sets US Networks Leadership Team",
            "Category: Org -> Exec Changes",
            (
                "Content: New Role: Brett Paul, COO, U.S. Networks at WBD "
                "([12/18](https://example.com/a))"
            ),
            "Category: Strategy & Miscellaneous News -> General News & Strategy -> Strategy",
            (
                "Content: WBD will restructure into two divisions by mid-2025. "
                "([12/18](https://example.com/a))"
            ),
            "",
        ]
    )
    b_text = "\n".join(
        [
            "Title: Warner Bros. Discovery Sets US Networks Leadership Team",
            "Category: Org -> Exec Changes",
            (
                "Content: New Role: Brett Paul, COO, U.S. Networks at WBD "
                "([12/18](https://example.com/b))"
            ),
            "Content: He will report to Channing Dungey. ([12/18](https://example.com/b))",
            "",
        ]
    )
    (a_dir / "sample.out.md").write_text(a_text, encoding="utf-8")
    (b_dir / "sample.out.md").write_text(b_text, encoding="utf-8")

    report_path = tmp_path / "report.md"
    cmd = [
        sys.executable,
        str(Path("tools/compare_ab_outputs.py")),
        "--a",
        str(a_dir),
        "--b",
        str(b_dir),
        "--output",
        str(report_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

    report = report_path.read_text(encoding="utf-8")
    assert "A/B output comparison" in report
    assert "Exec Changes (paired)" in report
    assert "Brett Paul" in report
    assert "He will report to Channing Dungey." in report
    assert "Categories only in A" in report
    assert "([12/18](" not in report
