"""Copy a finished factory run into runs/<name>/ so it can be committed and judged.

    uv run python scripts/export-run.py --name run3 --workspace ~/onsen-runs/capyfinder-... \
        --transcript ~/.onsen/transcripts/capyfinder-....json [--revealed ~/.onsen/revealed/exam-<run>.json]

Writes:
  runs/<name>/room.json        the room transcript, cleaned (no display names, no local paths)
  runs/<name>/RUN.md           receipt, timeline of tagged messages, exam curve, links
  runs/<name>/exam.json        the revealed sealed exam (its sha256 matches the [seal] message)
  runs/<name>/capyfinder/      the software the factory built (+ git-log.txt)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import make_replay  # noqa: E402

SKIP = {".git", "__pycache__", "node_modules", ".venv", "app.log", ".band-workspaces"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--revealed")
    ap.add_argument("--note", help="a paragraph to put under the title")
    args = ap.parse_args()
    out = ROOT / "runs" / args.name
    out.mkdir(parents=True, exist_ok=True)

    raw = json.loads(Path(args.transcript).read_text())
    raw.sort(key=lambda m: m.get("inserted_at") or "")
    clean = make_replay.clean_copy(raw)
    (out / "room.json").write_text(json.dumps(clean, indent=1, ensure_ascii=False))

    ws = Path(args.workspace)
    app = out / "capyfinder"
    shutil.rmtree(app, ignore_errors=True)
    shutil.copytree(ws, app, ignore=lambda d, names: [n for n in names if n in SKIP])
    log = subprocess.run(["git", "-C", str(ws), "log", "--format=%h %ad %s", "--date=format:%H:%M"],
                         capture_output=True, text=True).stdout
    (app / "git-log.txt").write_text(log)

    seal_hash = None
    for m in clean:
        hit = re.search(r"\[seal\].*?sha256=([0-9a-f]{64})", m["content"])
        if hit:
            seal_hash = hit.group(1)
    exam_note = ""
    if args.revealed and Path(args.revealed).exists():
        data = Path(args.revealed).read_bytes()
        (out / "exam.json").write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        exam_note = (f"- Revealed exam: [exam.json](exam.json) · sha256 `{digest}` · "
                     f"{'matches' if digest == seal_hash else 'does NOT match'} the last `[seal]`")

    texts = [m for m in clean if m["type"] == "text"]
    receipt = next((m["content"] for m in reversed(texts) if "[receipt]" in m["content"]), "(no receipt)")
    start = texts[0]["at"][11:19] if texts else "?"
    end = texts[-1]["at"][11:19] if texts else "?"
    tagged = []
    for m in texts:
        body = re.sub(r"^(?:@(?:Nap Guard|You \(the capybara\)|[\w-]+)\s+)+", "", m["content"])
        tag = re.match(r"\[([a-z-]+)\][^\n]*", body)
        if tag or m["from"].startswith("You"):
            line = (tag.group(0) if tag else body.splitlines()[0])[:160]
            tagged.append(f"| {m['at'][11:19]} | {m['from']} | {line.replace('|', '/')} |")
    tools = sum(1 for m in clean if m["type"] == "tool_call")
    md = [f"# Run `{args.name}`", "",
          f"One BAND room, six agents, {start}–{end} UTC. {len(texts)} messages, {tools} tool calls.", "",
          *([args.note, ""] if args.note else []),
          "## Receipt", "", "```", re.sub(r"^(?:@(?:Nap Guard|You \(the capybara\)|[\w-]+)\s+)+", "", receipt).strip(), "```", "",
          "## Evidence", "",
          "- Room transcript: [room.json](room.json) (display names and local paths removed)",
          "- What it built: [capyfinder/](capyfinder/) · commit history in [git-log.txt](capyfinder/git-log.txt)",
          exam_note, "",
          "## Timeline (tagged messages)", "", "| UTC | From | Message |", "|---|---|---|", *tagged, ""]
    (out / "RUN.md").write_text("\n".join(x for x in md if x is not None))
    print(f"exported {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
