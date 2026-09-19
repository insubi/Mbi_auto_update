#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
payload_dir = Path(__file__).resolve().parent

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

# Restore the exact scenic Abyss preview artwork that was previously approved in v72.
payloads = {
    "hallucination_anchorage.jpg": ("v72_preview_hallucination.b64", "0195c292d2b32cb369d2561ab01227e4b7120e9cade8178cc174d40bf8ceeb9d"),
    "madness_cave.jpg": ("v72_preview_madness.b64", "e6af39c665f1126dde46f17054589413b88690a0eaae56fc14e06a6434b4e50e"),
    "scattered_waterway.jpg": ("v72_preview_waterway.b64", "d1d56c996e21aaf60c8ec6d09770b2b93ae918ea1c1c290f4e767b62490c1ff6"),
}
preview_dir = app / "abyss" / "previews"
preview_dir.mkdir(parents=True, exist_ok=True)
for out_name, (payload_name, expected_hash) in payloads.items():
    payload_path = payload_dir / payload_name
    if not payload_path.is_file():
        raise SystemExit(f"missing approved scenic payload: {payload_name}")
    data = base64.b64decode(payload_path.read_text(encoding="ascii").strip(), validate=True)
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_hash:
        raise SystemExit(f"approved scenic payload hash mismatch: {out_name}: {actual}")
    out = preview_dir / out_name
    out.write_bytes(data)

# UI must load scenic JPG previews, never the recognition templates.
refui = app / "MainForm.ReferenceUI.cs"
s = read(refui)
replacements = {
    'LoadDungeonPreview("hallucination_anchorage.png")': 'LoadDungeonPreview("hallucination_anchorage.jpg")',
    'LoadDungeonPreview("madness_cave.png")': 'LoadDungeonPreview("madness_cave.jpg")',
    'LoadDungeonPreview("scattered_waterway.png")': 'LoadDungeonPreview("scattered_waterway.jpg")',
    'Path.Combine(AppContext.BaseDirectory, "abyss", "templates", fileName)': 'Path.Combine(AppContext.BaseDirectory, "abyss", "previews", fileName)',
}
for old, new in replacements.items():
    if old not in s:
        raise SystemExit(f"expected V0.1.50 preview marker missing: {old}")
    s = s.replace(old, new, 1)
write(refui, s)

# Ensure preview assets are copied by future build/publish operations.
project = app / "FishingAutomation.csproj"
p = read(project)
if "abyss\\previews\\**\\*.*" not in p and "abyss/previews/**/*.*" not in p:
    item = '''
  <ItemGroup>
    <None Update="abyss\\previews\\**\\*.*">
      <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
      <CopyToPublishDirectory>PreserveNewest</CopyToPublishDirectory>
    </None>
  </ItemGroup>
'''
    if "</Project>" not in p:
        raise SystemExit("project closing tag missing")
    p = p.replace("</Project>", item + "\n</Project>", 1)

# Narrow version bump V0.1.50 -> V0.1.51.
p = p.replace("<Version>0.1.50</Version>", "<Version>0.1.51</Version>")
p = p.replace("<AssemblyVersion>0.1.50.0</AssemblyVersion>", "<AssemblyVersion>0.1.51.0</AssemblyVersion>")
p = p.replace("<FileVersion>0.1.50.0</FileVersion>", "<FileVersion>0.1.51.0</FileVersion>")
write(project, p)

update = app / "UpdateManager.cs"
u = read(update)
if 'CurrentVersion = "V0.1.50"' not in u:
    raise SystemExit("UpdateManager V0.1.50 marker missing")
u = u.replace('CurrentVersion = "V0.1.50"', 'CurrentVersion = "V0.1.51"', 1)
write(update, u)

# Some source files may carry the display version. Only replace the exact current tag.
for path in app.rglob("*.cs"):
    if path in (refui, update):
        continue
    try:
        t = read(path)
    except UnicodeDecodeError:
        continue
    if "V0.1.50" in t:
        write(path, t.replace("V0.1.50", "V0.1.51"))

# Final invariants.
ui = read(refui)
required = (
    'LoadDungeonPreview("hallucination_anchorage.jpg")',
    'LoadDungeonPreview("madness_cave.jpg")',
    'LoadDungeonPreview("scattered_waterway.jpg")',
    'Path.Combine(AppContext.BaseDirectory, "abyss", "previews", fileName)',
)
for marker in required:
    if marker not in ui:
        raise SystemExit(f"restored preview marker missing: {marker}")
for forbidden in (
    'LoadDungeonPreview("hallucination_anchorage.png")',
    'LoadDungeonPreview("madness_cave.png")',
    'LoadDungeonPreview("scattered_waterway.png")',
    'Path.Combine(AppContext.BaseDirectory, "abyss", "templates", fileName)',
):
    if forbidden in ui:
        raise SystemExit(f"recognition template still wired as UI preview: {forbidden}")

for out_name, (_, expected_hash) in payloads.items():
    actual = hashlib.sha256((preview_dir / out_name).read_bytes()).hexdigest()
    if actual != expected_hash:
        raise SystemExit(f"restored preview hash mismatch: {out_name}")

project_text = read(project)
if "<Version>0.1.51</Version>" not in project_text:
    raise SystemExit("project version not V0.1.51")
if 'CurrentVersion = "V0.1.51"' not in read(update):
    raise SystemExit("UpdateManager version not V0.1.51")

print("V0.1.51 applied: original approved scenic Abyss previews restored")
