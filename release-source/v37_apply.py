#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read_text(path: Path):
    raw = path.read_bytes()
    enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    return raw.decode("utf-8-sig"), enc


def write_text(path: Path, text: str, enc: str):
    path.write_text(text, encoding=enc)


def replace_once(path: Path, pattern: str, replacement: str, flags=0):
    text, enc = read_text(path)
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"required marker missing: {path}")
    write_text(path, new, enc)


# v36 is the v32-based rollback. Keep that behavior and only improve updating.
replace_once(
    app / "UpdateManager.cs",
    r'public const string CurrentVersion = "v36";',
    'public const string CurrentVersion = "v37";',
)

# Once the external updater helper has started successfully, terminate the
# current macro process. ApplyUpdate.ps1 already waits for this process to end,
# replaces the files, launches START.cmd, and verifies the new startup.
p = app / "UpdateManager.cs"
text, enc = read_text(p)
if "Environment.Exit(0);" not in text:
    pattern = (
        r'(if \(updaterProcess is null\)\s*\r?\n'
        r'\s*throw new InvalidOperationException\("업데이트 도우미를 실행하지 못했습니다\."\);\s*\r?\n)'
    )
    text, count = re.subn(pattern, r'\1        Environment.Exit(0);\n', text, count=1)
    if count != 1:
        raise RuntimeError("LaunchUpdater completion block not found")
    write_text(p, text, enc)

# Keep the macro title distinct from the game window title.
p = app / "MainForm.cs"
text, enc = read_text(p)
text = re.sub(
    r'Text\s*=\s*"MABI AUTO[^\"]*";',
    'Text = "MABI AUTO · v37";',
    text,
    count=1,
)
write_text(p, text, enc)

# Cosmetic dashboard labels when present.
p = app / "MainForm.Dashboard.cs"
if p.exists():
    text, enc = read_text(p)
    text = re.sub(r'Dashboard v\d+', 'Dashboard v37', text)
    text = re.sub(r'v\d+\s*\|\s*Mabi Auto', 'v37  |  Mabi Auto', text)
    write_text(p, text, enc)

# Windows file/product version.
p = app / "FishingAutomation.csproj"
text, enc = read_text(p)
for tag, value in {
    "Version": "37.0.0",
    "AssemblyVersion": "37.0.0.0",
    "FileVersion": "37.0.0.0",
}.items():
    pattern = rf'<{tag}>[^<]+</{tag}>'
    replacement = f'<{tag}>{value}</{tag}>'
    if re.search(pattern, text):
        text = re.sub(pattern, replacement, text, count=1)
    else:
        if "<PropertyGroup>" not in text:
            raise RuntimeError(f"PropertyGroup missing while setting {tag}")
        text = text.replace("<PropertyGroup>", "<PropertyGroup>\n    " + replacement, 1)
write_text(p, text, enc)

(root / "CHANGES_v37_AUTO_RESTART.txt").write_text(
    "MABI AUTO v37 - reliable automatic restart after update\n\n"
    "- v36/v32-based Abyss, Dungeon and Fishing behavior preserved\n"
    "- Macro title remains separate from the game title: MABI AUTO · v37\n"
    "- After the updater helper starts, the current macro process exits automatically\n"
    "- Existing ApplyUpdate.ps1 then replaces files, starts START.cmd, and performs the startup health check\n",
    encoding="utf-8",
)

print("v37 applied: current process exits after updater launch; existing updater starts the new version")
