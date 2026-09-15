#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"v71 expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


# v71 must be a narrow UI-only polish on the published v70 source.
v70_audit_path = root / "V70_AUTOSTOP_UI_AUDIT.json"
if not v70_audit_path.is_file():
    raise RuntimeError("v70 audit missing; v71 must be applied on v70 source")
v70_audit = json.loads(v70_audit_path.read_text(encoding="utf-8-sig"))
if v70_audit.get("version") != "v70":
    raise RuntimeError("unexpected base audit version")

preview_rels = [
    "FishingAutomation/abyss/templates/hallucination_anchorage.png",
    "FishingAutomation/abyss/templates/madness_cave.png",
    "FishingAutomation/abyss/templates/scattered_waterway.png",
]
preview_hashes = {}
for rel in preview_rels:
    p = root / rel
    if not p.is_file():
        raise RuntimeError(f"v70 Abyss preview missing: {rel}")
    preview_hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

# Version bump.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v70";',
                 'public const string CurrentVersion = "v71";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "71.0.0"), ("AssemblyVersion", "71.0.0.0"), ("FileVersion", "71.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v71 project version tag missing: {name}")
write(project, s)

ui_path = app / "MainForm.ReferenceUI.cs"
s = read(ui_path)

# Refine only the HOME brand typography: slightly smaller, more breathing room,
# and a cleaner separation between product name and version.
s = replace_once(
    s,
    'TextAt(g, "Mabi_Auto", new(76, 14, 166, 48), 27, true, Color.White);',
    'TextAt(g, "Mabi_Auto", new(76, 15, 175, 44), 24, true, Color.White);',
    'HOME brand title')
s = replace_once(
    s,
    'TextAt(g, "v70", new(244, 20, 70, 37), 15, true, _cyan);',
    'TextAt(g, "v71", new(257, 20, 64, 34), 14, true, _cyan);',
    'HOME version label')

# Polish the existing v70 scheduled-stop controls without changing behavior.
s = replace_once(
    s,
    'BackColor = Color.FromArgb(2, 22, 42),\n                ForeColor = _text,\n                Font = new Font(_baseFont.FontFamily, 9.5f, FontStyle.Bold, GraphicsUnit.Point),',
    'BackColor = Color.FromArgb(3, 27, 48),\n                ForeColor = _text,\n                Font = new Font(_baseFont.FontFamily, 9.5f, FontStyle.Regular, GraphicsUnit.Point),',
    'auto-stop caption styling')
s = replace_once(
    s,
    'BackColor = Color.FromArgb(3, 29, 51),\n                ForeColor = Color.White,',
    'BackColor = Color.FromArgb(2, 24, 45),\n                ForeColor = Color.White,',
    'auto-stop time styling')
s = replace_once(
    s,
    'var autoStopCheckBounds = new RectangleF(1068, 154, 160, 48);\n            var autoStopTimeBounds = new RectangleF(1240, 154, 132, 48);',
    'var autoStopCheckBounds = new RectangleF(1063, 154, 166, 48);\n            var autoStopTimeBounds = new RectangleF(1242, 154, 128, 48);',
    'auto-stop bounds')

# Add a subtle shared container behind checkbox/caption/time so the control reads as
# one dashboard component rather than two unrelated native widgets.
anchor = '            TextAt(g, "모든 시스템 상태를 확인하고 자동 진행을 준비합니다.", new(319, 169, 440, 31), 18);\n'
container_draw = (
    anchor +
    '            Card(g, new(1048, 145, 342, 66));\n'
)
s = replace_once(s, anchor, container_draw, 'auto-stop visual container')
write(ui_path, s)

# Confirm the three Abyss dungeon artwork files are untouched byte-for-byte.
for rel, before in preview_hashes.items():
    after = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    if after != before:
        raise RuntimeError(f"v71 must not change Abyss dungeon preview artwork: {rel}")

changes_path = root / "CHANGES_v71_UI_POLISH.txt"
changes_path.write_text(
    "MABI AUTO v71\n"
    "- HOME Mabi_Auto title/version spacing and size refined for a cleaner header.\n"
    "- Scheduled-stop checkbox/caption/time are visually grouped in a subtle dark card.\n"
    "- Scheduled-stop caption uses the same Malgun Gothic family with a lighter dashboard-matching weight.\n"
    "- HH:mm field stays dark and compact; existing validation, persistence and F10-safe stop behavior are unchanged.\n"
    "- Abyss dungeon preview image files are preserved byte-for-byte from v70.\n"
    "- Telegram, Abyss clear/recovery logic, all other windows and layouts are unchanged.\n",
    encoding="utf-8",
)

modified = [update, project, ui_path, changes_path]
audit = {
    "base": "v70",
    "version": "v71",
    "purpose": "Polish HOME title and scheduled-stop visual grouping only",
    "home_title": {
        "text": "Mabi_Auto",
        "version": "v71",
        "title_size_pixels": 24,
        "version_size_pixels": 14,
    },
    "auto_stop_ui": {
        "caption": "자동 정지",
        "font_family": "맑은 고딕",
        "font_size_points": 9.5,
        "caption_weight": "Regular",
        "time_control": "MaskedTextBox",
        "time_format": "HH:mm",
        "group_card": [1048, 145, 342, 66],
        "safe_stop_path_preserved": "StopSelected",
        "settings_persistence_preserved": True,
    },
    "preserved_preview_hashes": preview_hashes,
    "preserved": [
        "v70 Abyss dungeon preview artwork",
        "v70 Telegram menu/dialog",
        "v70 Abyss clear transition and in-dungeon recovery",
        "F10 manual safe stop",
        "all other windows and layouts",
        "administrator elevation",
        "exact 800x1000 game-window sizing and monitor placement"
    ],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V71_UI_POLISH_AUDIT.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("v71 applied: HOME brand + grouped auto-stop polish; Abyss artwork preserved")
