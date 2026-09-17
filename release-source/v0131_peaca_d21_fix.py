#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0131_peaca_d21_fix.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_required(path: Path, pairs: list[tuple[str, str]]) -> None:
    text = read_text(path)
    for old, new in pairs:
        if old not in text:
            raise RuntimeError(f"D2-1 correction anchor missing in {path.name}: {old}")
        text = text.replace(old, new)
    write_text(path, text)

# The intended second Peaca destination is D2-1, not D2-2.
replace_required(
    app / "MainForm.cs",
    [
        ("페카 심층 2-2", "페카 심층 2-1"),
        ("peaca_d2_2", "peaca_d2_1"),
    ],
)

replace_required(
    app / "MainForm.ReferenceUI.cs",
    [("페카 심층 2-2", "페카 심층 2-1")],
)

replace_required(
    app / "dungeon" / "ScenarioEngine.cs",
    [
        ("peaca_d2_2", "peaca_d2_1"),
        ("페카 심층 2-2", "페카 심층 2-1"),
        ("route_d2_2", "route_d2_1"),
        ("route_enter_d2_2", "route_enter_d2_1"),
        ("심층 2층 2구역", "심층 2층 1구역"),
    ],
)

targets_path = app / "dungeon" / "config" / "targets.json"
targets = json.loads(read_text(targets_path))
id_map = {
    "route_d2_2": "route_d2_1",
    "route_enter_d2_2": "route_enter_d2_1",
}
seen = set()
for target in targets:
    target_id = target.get("Id", "")
    if target_id in id_map:
        target["Id"] = id_map[target_id]
    if isinstance(target.get("Text"), str):
        target["Text"] = target["Text"].replace("심층 2층 2구역", "심층 2층 1구역")
    if target.get("Id") in seen:
        raise RuntimeError(f"duplicate target after D2-1 correction: {target.get('Id')}")
    seen.add(target.get("Id"))

for required in ("route_d2_1", "route_enter_d2_1"):
    if required not in seen:
        raise RuntimeError(f"corrected target missing: {required}")

write_text(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

for path in (
    app / "MainForm.cs",
    app / "MainForm.ReferenceUI.cs",
    app / "dungeon" / "ScenarioEngine.cs",
    targets_path,
):
    text = read_text(path)
    for forbidden in ("페카 심층 2-2", "peaca_d2_2", "route_d2_2", "route_enter_d2_2", "심층 2층 2구역"):
        if forbidden in text:
            raise RuntimeError(f"D2-2 residue remains in {path.name}: {forbidden}")

print("V0.1.31 D2-1 correction applied")
