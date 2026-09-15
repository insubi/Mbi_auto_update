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
        raise RuntimeError(f"V0.1 expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


# V0.1 is the first public/stable version and is built directly from published v72.
v72_audit_path = root / "V72_SCENIC_PREVIEW_AUDIT.json"
if not v72_audit_path.is_file():
    raise RuntimeError("v72 audit missing; V0.1 must be applied on published v72 source")
v72_audit = json.loads(v72_audit_path.read_text(encoding="utf-8-sig"))
if v72_audit.get("version") != "v72":
    raise RuntimeError("unexpected base audit version")

preview_rels = [
    "FishingAutomation/abyss/previews/hallucination_anchorage.jpg",
    "FishingAutomation/abyss/previews/madness_cave.jpg",
    "FishingAutomation/abyss/previews/scattered_waterway.jpg",
]
preview_hashes = {}
for rel in preview_rels:
    p = root / rel
    if not p.is_file():
        raise RuntimeError(f"v72 scenic preview missing: {rel}")
    preview_hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

# Public version resets to V0.1. Legacy v73 is used only as an updater bridge so v72
# installations can discover this build; after installation the app ignores old integer
# release tags and follows semantic public versions (V0.1, V0.1.1, V0.2, V1.0...).
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v72";',
                 'public const string CurrentVersion = "V0.1";', 'UpdateManager public version')
old_method = '''    private static bool IsMainReleaseTag(string tag)
    {
        if (string.IsNullOrWhiteSpace(tag) || tag.Length < 2) return false;
        if (tag[0] is not ('v' or 'V')) return false;
        bool hasDigit = false;
        for (int i = 1; i < tag.Length; i++)
        {
            char c = tag[i];
            if (char.IsDigit(c)) { hasDigit = true; continue; }
            if (c == '.') continue;
            return false;
        }
        return hasDigit;
    }
'''
new_method = '''    private static bool IsMainReleaseTag(string tag)
    {
        if (string.IsNullOrWhiteSpace(tag) || tag.Length < 2) return false;
        if (tag[0] is not ('v' or 'V')) return false;
        bool hasDigit = false;
        bool hasDot = false;
        for (int i = 1; i < tag.Length; i++)
        {
            char c = tag[i];
            if (char.IsDigit(c)) { hasDigit = true; continue; }
            if (c == '.') { hasDot = true; continue; }
            return false;
        }

        // Once the installed build is on the public semantic-version line, legacy
        // integer bridge tags (v72/v73/...) are no longer update candidates.
        bool currentUsesSemanticVersion = CurrentVersion.Contains('.', StringComparison.Ordinal);
        if (currentUsesSemanticVersion && !hasDot) return false;
        return hasDigit;
    }
'''
s = replace_once(s, old_method, new_method, 'semantic release filter')
write(update, s)

# Windows file metadata follows the public version.
project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "0.1.0"), ("AssemblyVersion", "0.1.0.0"), ("FileVersion", "0.1.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"V0.1 project version tag missing: {name}")
write(project, s)

# HOME-only visual polish requested from the approved mockup.
ui_path = app / "MainForm.ReferenceUI.cs"
s = read(ui_path)

# Compact top-left brand: smaller mark, cleaner title spacing, semantic version pill.
s = replace_once(
    s,
    '            Artwork(g, new(27, 21, 39, 37), new(27, 21, 39, 37));\n'
    '            TextAt(g, "Mabi_Auto", new(76, 15, 175, 44), 24, true, Color.White);\n'
    '            TextAt(g, "v72", new(257, 20, 64, 34), 14, true, _cyan);',
    '            Artwork(g, new(30, 22, 32, 30), new(27, 21, 39, 37));\n'
    '            TextAt(g, "Mabi_Auto", new(78, 14, 170, 43), 25, true, Color.White);\n'
    '            Card(g, new(252, 16, 78, 35));\n'
    '            TextAt(g, UpdateManager.CurrentVersion, new(252, 18, 78, 31), 14, true, _cyan, StringAlignment.Center);',
    'HOME brand/version banner')

# Make scheduled stop read as one compact component. The time field remains centered,
# but its height is reduced so native WinForms vertical text placement looks centered too.
s = replace_once(
    s,
    '                BackColor = Color.FromArgb(3, 27, 48),\n'
    '                ForeColor = _text,\n'
    '                Font = new Font(_baseFont.FontFamily, 9.5f, FontStyle.Regular, GraphicsUnit.Point),',
    '                BackColor = Color.FromArgb(2, 22, 42),\n'
    '                ForeColor = _text,\n'
    '                Font = new Font(_baseFont.FontFamily, 9.5f, FontStyle.Regular, GraphicsUnit.Point),',
    'auto-stop caption background')
s = replace_once(
    s,
    '                Padding = new Padding(0, 0, 0, 1)',
    '                Padding = new Padding(3, 0, 0, 1)',
    'auto-stop caption padding')
s = replace_once(
    s,
    '            var autoStopCheckBounds = new RectangleF(1063, 154, 166, 48);\n'
    '            var autoStopTimeBounds = new RectangleF(1242, 154, 128, 48);',
    '            var autoStopCheckBounds = new RectangleF(1065, 158, 154, 38);\n'
    '            var autoStopTimeBounds = new RectangleF(1235, 160, 110, 34);',
    'compact auto-stop bounds')
s = replace_once(
    s,
    '            Card(g, new(1048, 145, 342, 66));',
    '            Card(g, new(1054, 151, 312, 54));',
    'compact auto-stop group card')
write(ui_path, s)

# Scenic dungeon previews remain exactly the approved v72 artwork.
for rel, before in preview_hashes.items():
    after = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    if after != before:
        raise RuntimeError(f"V0.1 must preserve approved Abyss preview artwork: {rel}")

versioning_path = root / "VERSIONING_V0.1.txt"
versioning_path.write_text(
    "MABI AUTO PUBLIC VERSION RULES\n"
    "- V0.1: first stable/public baseline.\n"
    "- V0.1.1, V0.1.2 ...: small UI fixes, bug fixes, and stability-only corrections.\n"
    "- V0.2, V0.3 ...: user-visible feature additions or meaningful behavior changes.\n"
    "- V1.0: major stable milestone / large structural release.\n"
    "- Legacy integer tag v73 is only the one-time updater bridge from v72 and earlier.\n"
    "- The application and user-facing version from this build onward is V0.1.\n",
    encoding="utf-8",
)

changes_path = root / "CHANGES_V0.1_UI_POLISH.txt"
changes_path.write_text(
    "MABI AUTO V0.1\n"
    "- Public versioning starts at V0.1.\n"
    "- Top-left Mabi_Auto brand spacing/size cleaned up and version moved into a compact pill.\n"
    "- Scheduled-stop group/card reduced to match its contents.\n"
    "- HH:mm field is narrower/shorter and remains horizontally centered for a visually centered 02:30.\n"
    "- Approved v72 Abyss scenic card artwork is preserved byte-for-byte.\n"
    "- Auto-stop behavior, Telegram, Abyss clear/recovery, recognition templates and all other runtime logic remain unchanged.\n",
    encoding="utf-8",
)

modified = [update, project, ui_path, versioning_path, changes_path]
audit = {
    "base": "v72",
    "technical_bridge_tag": "v73",
    "version": "V0.1",
    "purpose": "First stable public version; HOME brand and scheduled-stop visual polish only",
    "version_rules": {
        "patch": "V0.1.1 for UI/bug/stability-only fixes",
        "minor": "V0.2 for feature or meaningful behavior additions",
        "major": "V1.0 for major stable milestone",
    },
    "home_brand": {
        "title": "Mabi_Auto",
        "public_version": "V0.1",
        "version_pill": [252, 16, 78, 35],
    },
    "auto_stop_ui": {
        "group_card": [1054, 151, 312, 54],
        "caption_bounds": [1065, 158, 154, 38],
        "time_bounds": [1235, 160, 110, 34],
        "time_alignment": "center",
        "time_format": "HH:mm",
        "safe_stop_behavior_preserved": True,
        "settings_persistence_preserved": True,
    },
    "preserved_preview_hashes": preview_hashes,
    "preserved": [
        "v72 approved Abyss scenic artwork",
        "Abyss recognition templates",
        "Telegram settings and alerts",
        "Abyss clear transition and in-dungeon recovery",
        "F10 manual safe stop",
        "other windows and layouts",
        "administrator elevation",
        "exact 800x1000 game-window sizing and monitor placement"
    ],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V0_1_RELEASE_AUDIT.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("V0.1 applied on v72: brand polish + compact centered auto-stop + semantic public versioning")
