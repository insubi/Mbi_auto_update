#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
payload_dir = Path(__file__).resolve().parent


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"v72 expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


# v72 is a narrow UI-asset change on the verified v71 source.
v71_audit_path = root / "V71_UI_POLISH_AUDIT.json"
if not v71_audit_path.is_file():
    raise RuntimeError("v71 audit missing; v72 must be applied on v71 source")
v71_audit = json.loads(v71_audit_path.read_text(encoding="utf-8-sig"))
if v71_audit.get("version") != "v71":
    raise RuntimeError("unexpected base audit version")

recognition_rels = [
    "FishingAutomation/abyss/templates/hallucination_anchorage.png",
    "FishingAutomation/abyss/templates/madness_cave.png",
    "FishingAutomation/abyss/templates/scattered_waterway.png",
]
recognition_hashes = {}
for rel in recognition_rels:
    p = root / rel
    if not p.is_file():
        raise RuntimeError(f"recognition template missing: {rel}")
    recognition_hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

# Version bump.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v71";',
                 'public const string CurrentVersion = "v72";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "72.0.0"), ("AssemblyVersion", "72.0.0.0"), ("FileVersion", "72.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v72 project version tag missing: {name}")
write(project, s)

# Decode the scenic images the user approved into a UI-only preview directory.
# Detection templates stay in abyss/templates and are never overwritten.
preview_dir = app / "abyss" / "previews"
preview_dir.mkdir(parents=True, exist_ok=True)
payloads = {
    "hallucination_anchorage.jpg": ("v72_preview_hallucination.b64", "0195c292d2b32cb369d2561ab01227e4b7120e9cade8178cc174d40bf8ceeb9d"),
    "madness_cave.jpg": ("v72_preview_madness.b64", "e6af39c665f1126dde46f17054589413b88690a0eaae56fc14e06a6434b4e50e"),
    "scattered_waterway.jpg": ("v72_preview_waterway.b64", "e554e07e40a3b07def8ef9f6ffe2f659c6a35097e02d14a9007a0a6fab8ccfdd"),
}
preview_paths = []
for out_name, (payload_name, expected_hash) in payloads.items():
    payload_path = payload_dir / payload_name
    if not payload_path.is_file():
        raise RuntimeError(f"v72 scenic preview payload missing: {payload_name}")
    data = base64.b64decode(payload_path.read_text(encoding="ascii").strip(), validate=True)
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_hash:
        raise RuntimeError(f"v72 scenic preview payload hash mismatch: {out_name}: {actual}")
    out = preview_dir / out_name
    out.write_bytes(data)
    preview_paths.append(out)

ui_path = app / "MainForm.ReferenceUI.cs"
s = read(ui_path)
s = replace_once(s,
    'TextAt(g, "v71", new(257, 20, 64, 34), 14, true, _cyan);',
    'TextAt(g, "v72", new(257, 20, 64, 34), 14, true, _cyan);',
    'HOME version label')
s = replace_once(s, 'LoadDungeonPreview("hallucination_anchorage.png")',
                 'LoadDungeonPreview("hallucination_anchorage.jpg")', 'harbor preview filename')
s = replace_once(s, 'LoadDungeonPreview("madness_cave.png")',
                 'LoadDungeonPreview("madness_cave.jpg")', 'cave preview filename')
s = replace_once(s, 'LoadDungeonPreview("scattered_waterway.png")',
                 'LoadDungeonPreview("scattered_waterway.jpg")', 'waterway preview filename')
s = replace_once(s,
    'string path = Path.Combine(AppContext.BaseDirectory, "abyss", "templates", fileName);',
    'string path = Path.Combine(AppContext.BaseDirectory, "abyss", "previews", fileName);',
    'HOME preview loader path')
write(ui_path, s)

# Hard guard: automation recognition images must not change while fixing the visual cards.
for rel, before in recognition_hashes.items():
    after = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    if after != before:
        raise RuntimeError(f"v72 must not alter recognition template: {rel}")

changes_path = root / "CHANGES_v72_SCENIC_PREVIEWS.txt"
changes_path.write_text(
    "MABI AUTO v72\n"
    "- Abyss dungeon cards now use separate scenic preview artwork matching the approved UI mockup.\n"
    "- 허상의 정박지: blue/night harbor and wooden wharf preview.\n"
    "- 광기의 동굴: dark blue-purple glowing cave preview.\n"
    "- 흩어진 물길: blue ruined arches and waterway preview.\n"
    "- Recognition templates remain byte-for-byte unchanged under abyss/templates.\n"
    "- v71 Mabi_Auto header and grouped auto-stop UI are preserved.\n"
    "- Telegram, Abyss clear/recovery logic and every other window/layout are unchanged.\n",
    encoding="utf-8",
)

modified = [update, project, ui_path, changes_path] + preview_paths
audit = {
    "base": "v71",
    "version": "v72",
    "purpose": "Separate scenic Abyss card previews from automation recognition templates",
    "home_ui_preserved": {
        "title": "Mabi_Auto",
        "version": "v72",
        "auto_stop_caption": "자동 정지",
        "auto_stop_safe_path": "StopSelected",
    },
    "scenic_previews": {
        "hallucination_anchorage": "FishingAutomation/abyss/previews/hallucination_anchorage.jpg",
        "madness_cave": "FishingAutomation/abyss/previews/madness_cave.jpg",
        "scattered_waterway": "FishingAutomation/abyss/previews/scattered_waterway.jpg",
    },
    "preserved_recognition_template_hashes": recognition_hashes,
    "preserved": [
        "v71 HOME title and scheduled-stop grouping",
        "v71 Telegram menu/dialog",
        "Abyss recognition templates and detection behavior",
        "Abyss clear transition and in-dungeon recovery",
        "F10 manual safe stop",
        "all other windows and layouts",
        "administrator elevation",
        "exact 800x1000 game-window sizing and monitor placement"
    ],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V72_SCENIC_PREVIEW_AUDIT.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("v72 applied: scenic Abyss card previews added separately; recognition templates untouched")
