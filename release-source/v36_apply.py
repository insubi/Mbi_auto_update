#!/usr/bin/env python3
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

root = Path(sys.argv[1]).resolve()
repo = os.environ.get("REPO", "insubi/Mbi_auto_update")


def read_text(path: Path):
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig"), ("utf-8-sig" if bom else "utf-8")


def write_text(path: Path, text: str, enc: str):
    path.write_text(text, encoding=enc)


def regex_required(path: Path, pattern: str, replacement: str, flags=0):
    text, enc = read_text(path)
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"rollback marker missing: {path} / {pattern}")
    write_text(path, new, enc)


# v33 introduced Life/cloth automation. Restore the complete v32 source tree first,
# then only bump version labels to v36 so the normal auto-updater will not replace
# the rollback with v33-v35 again.
with tempfile.TemporaryDirectory(prefix="mabi_v36_rollback_") as td:
    tmp = Path(td)
    source_zip = tmp / "CombinedFishingDungeon_v32_StabilityRemote.zip"

    subprocess.run([
        "gh", "release", "download", "v32",
        "--repo", repo,
        "--pattern", "CombinedFishingDungeon_v32_StabilityRemote.zip",
        "--dir", str(tmp),
        "--clobber",
    ], check=True)

    if not source_zip.is_file() or source_zip.stat().st_size < 1024:
        raise RuntimeError("v32 rollback source ZIP download failed")

    unpack = tmp / "unpack"
    unpack.mkdir()
    with zipfile.ZipFile(source_zip, "r") as zf:
        zf.extractall(unpack)

    candidates = []
    for p in unpack.rglob("FishingAutomation.csproj"):
        if p.parent.name == "FishingAutomation":
            candidates.append(p.parent.parent)
    if not candidates:
        raise RuntimeError("v32 source root was not found")
    v32_root = candidates[0]

    for child in list(root.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()

    for child in v32_root.iterdir():
        dest = root / child.name
        if child.is_dir():
            shutil.copytree(child, dest)
        else:
            shutil.copy2(child, dest)

app = root / "FishingAutomation"

# Keep v32 behavior, but publish it as a newer rollback release so automatic
# updates remain on the restored Abyss code instead of reinstalling v33-v35.
regex_required(
    app / "UpdateManager.cs",
    r'public const string CurrentVersion = "v\d+";',
    'public const string CurrentVersion = "v36";',
)

# Remove the game title words from the macro window title. This prevents the
# automation window itself from being mistaken for the game while leaving the
# v32 Abyss state machine unchanged.
main_form = app / "MainForm.cs"
text, enc = read_text(main_form)
new, count = re.subn(
    r'Text\s*=\s*"MABI AUTO[^\"]*";',
    'Text = "MABI AUTO · v36";',
    text,
    count=1,
)
if count == 1:
    write_text(main_form, new, enc)

# Dashboard labels are cosmetic only; update them when present.
dashboard = app / "MainForm.Dashboard.cs"
if dashboard.exists():
    text, enc = read_text(dashboard)
    text = re.sub(r'Dashboard v\d+', 'Dashboard v36', text)
    text = re.sub(r'v\d+\s*\|\s*Mabi Auto', 'v36  |  Mabi Auto', text)
    write_text(dashboard, text, enc)

# Give the Windows build a v36 file/product version without changing v32 logic.
proj = app / "FishingAutomation.csproj"
text, enc = read_text(proj)
replacements = {
    "Version": "36.0.0",
    "AssemblyVersion": "36.0.0.0",
    "FileVersion": "36.0.0.0",
}
for tag, value in replacements.items():
    pat = rf'<{tag}>[^<]+</{tag}>'
    repl = f'<{tag}>{value}</{tag}>'
    if re.search(pat, text):
        text = re.sub(pat, repl, text, count=1)
    else:
        marker = "<PropertyGroup>"
        if marker in text:
            text = text.replace(marker, marker + f"\n    {repl}", 1)
        else:
            raise RuntimeError(f"PropertyGroup missing while setting {tag}")
write_text(proj, text, enc)

(root / "CHANGES_v36_ABYSS_ROLLBACK.txt").write_text(
    "MABI AUTO v36 - Abyss rollback\n\n"
    "- v33에서 추가된 생활/옷감 자동 채집 기능 제거\n"
    "- 낚시/던전/어비스 코드를 v32 정식 릴리스 기준으로 전체 복원\n"
    "- 자동 업데이트가 v33~v35로 다시 덮어쓰지 않도록 버전만 v36으로 게시\n"
    "- 매크로 창 제목은 게임 창 오인 방지를 위해 'MABI AUTO · v36'으로 유지\n",
    encoding="utf-8",
)

print("v36 rollback applied: v32 behavior restored")
