import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "data" / "samples" / "manual_runs"
CLI_CMD = ["python", "-m", "news_coverage.cli", "--mode", "agent"]


def run_sample(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"title", "source", "url", "content"}
    if not required.issubset(data.keys()) or not data.get("content"):
        print(
            f"[skip] {path.name}: url-only stub or missing required fields; "
            "use the extension to capture full payload."
        )
        return

    out_path = path.with_suffix(path.suffix + ".out.md")
    cmd = CLI_CMD + [str(path), "--out", str(out_path)]
    print(f"[run] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode == 0:
        print(f"[ok ] wrote {out_path}")
    else:
        print(f"[fail] {path.name} (exit {result.returncode})")


def main():
    if not SAMPLES_DIR.exists():
        print("manual_runs directory not found; nothing to do.")
        return
    for json_path in sorted(SAMPLES_DIR.glob("*.json")):
        run_sample(json_path)


if __name__ == "__main__":
    main()
