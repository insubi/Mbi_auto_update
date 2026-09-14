"""Packaging-only overlay on the published v57 Windows build input."""
import hashlib
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

# v57's ZIP contains dungeon/ and Dungeon/. Windows tar uses the later
# Dungeon/*.cs entries. Keep those exact bytes while removing case collisions.
upper = app / "Dungeon"
lower = app / "dungeon"
if upper.exists() and lower.exists() and not upper.samefile(lower):
    for source in upper.rglob("*"):
        if source.is_file():
            target = lower / source.relative_to(upper)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    import shutil
    shutil.rmtree(upper)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

protected = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
             (".cs", ".ps1", ".cmd", ".bat", ".json", ".png", ".jpg", ".jpeg", ".dll")]
before = {p.relative_to(root).as_posix(): digest(p) for p in protected}
update = app / "UpdateManager.cs"
old = update.read_bytes()
assert old.count(b'CurrentVersion = "v57"') == 1, "Expected v57 updater"
update.write_bytes(old.replace(b'CurrentVersion = "v57"', b'CurrentVersion = "v58"'))

project = app / "FishingAutomation.csproj"
text = project.read_text(encoding="utf-8-sig")
for name, value in (("Version", "58.0.0"), ("AssemblyVersion", "58.0.0.0"),
                    ("FileVersion", "58.0.0.0")):
    text, count = re.subn(fr"<{name}>[^<]+</{name}>", f"<{name}>{value}</{name}>", text)
    assert count == 1, name
# Content selection only: default Compile items and dependencies stay unchanged.
text = text.replace('    <Content Include="drivers\\README.txt" CopyToOutputDirectory="PreserveNewest" />\n', '')
for folder in ("templates", "dungeon", "abyss"):
    original = f'    <Content Include="{folder}\\**\\*" CopyToOutputDirectory="PreserveNewest" />'
    patterns = ([f"{folder}\\*.png", f"{folder}\\*.jpg", f"{folder}\\*.jpeg", f"{folder}\\*.bmp"]
                if folder == "templates" else
                [f"{folder}\\config\\*.json", f"{folder}\\templates\\*.png",
                 f"{folder}\\templates\\*.jpg", f"{folder}\\templates\\*.jpeg", f"{folder}\\templates\\*.bmp"])
    assert original in text, folder
    text = text.replace(original, '    <Content Include="' + ';'.join(patterns) +
                        '" CopyToOutputDirectory="PreserveNewest" />')
project.write_text(text, encoding="utf-8", newline="\n")

for path, sha in before.items():
    current = root / path
    if current == update:
        assert current.read_bytes().replace(b'CurrentVersion = "v58"', b'CurrentVersion = "v57"') == old
    else:
        assert digest(current) == sha, f"Runtime logic/data changed: {path}"

asset_names = ["config.json", "notification.json", "interception.dll"]
asset_names += [f"templates/{name}.png" for name in ("compass", "gauge", "healthbar", "hook")]
for mode in ("dungeon", "abyss"):
    asset_names += [f"{mode}/config/{name}.json" for name in ("appsettings", "scenario", "targets")]
asset_names += ["dungeon/templates/challenge_visual.png", "dungeon/templates/scene_skip_phone.jpg"]
asset_names += [f"abyss/templates/{name}.png" for name in
                ("abyss", "enter", "exit", "hallucination_anchorage", "leave_dungeon", "madness_cave",
                 "menu", "popup_close", "scattered_waterway", "touch_screen", "treasure_chest")]
asset_names += ["abyss/templates/scene_skip_phone.jpg"]
assets = [app / name for name in asset_names]
assert all(p.is_file() for p in assets)
audit = {
    "base": "v57", "version": "v58",
    "logic_change": "UpdateManager.CurrentVersion only; all other effective v57 C# bytes unchanged",
    "case_collision_policy": "Keep v57 Windows tar winner Dungeon/*.cs as dungeon/*.cs",
    "protected_sha256": {p.relative_to(root).as_posix(): digest(p) for p in protected if p.exists()},
    "runtime_assets": {p.relative_to(app).as_posix(): digest(p) for p in assets},
}
(root / "V58_PACKAGING_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
print(f"v58 packaging overlay verified: {len(before)} protected files; {len(assets)} runtime assets")
