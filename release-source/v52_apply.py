#!/usr/bin/env python3
from pathlib import Path
import sys, io, tarfile, base64

root = Path(sys.argv[1]).resolve()
parts_dir = Path(__file__).resolve().parent / "v52_parts"
payload = "".join(p.read_text(encoding="ascii") for p in sorted(parts_dir.glob("part*.txt")))
data = base64.b85decode(payload.encode("ascii"))
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
    tf.extractall(root)

# GitHub's historical v51 source release did not contain ui/reference.png even
# though the local ReferenceUI package did. Make the resource optional so the
# Windows build remains reliable, and let the UI create a dark fallback canvas
# when the decorative artwork is absent.
proj = root / "FishingAutomation" / "FishingAutomation.csproj"
proj_text = proj.read_text(encoding="utf-8")
old_resource = '<EmbeddedResource Include="ui\\reference.png" LogicalName="FishingAutomation.ReferenceArtwork.png" />'
new_resource = '<EmbeddedResource Include="ui\\reference.png" LogicalName="FishingAutomation.ReferenceArtwork.png" Condition="Exists(\'ui\\reference.png\')" />'
if old_resource in proj_text:
    proj_text = proj_text.replace(old_resource, new_resource)
proj.write_text(proj_text, encoding="utf-8")

refui = root / "FishingAutomation" / "MainForm.ReferenceUI.cs"
ref_text = refui.read_text(encoding="utf-8")
old_art = '''            using var stream = typeof(MainForm).Assembly.GetManifestResourceStream("FishingAutomation.ReferenceArtwork.png")
                ?? throw new InvalidOperationException("UI artwork resource is missing.");
            using var original = Image.FromStream(stream);
            _art = new Bitmap(original);'''
new_art = '''            using var stream = typeof(MainForm).Assembly.GetManifestResourceStream("FishingAutomation.ReferenceArtwork.png");
            if (stream is null)
            {
                _art = new Bitmap(1448, 1086);
                using var artGraphics = Graphics.FromImage(_art);
                artGraphics.Clear(Color.FromArgb(0, 18, 35));
            }
            else
            {
                using var original = Image.FromStream(stream);
                _art = new Bitmap(original);
            }'''
if old_art not in ref_text:
    raise SystemExit("ReferenceUI artwork initialization block was not found")
ref_text = ref_text.replace(old_art, new_art)
refui.write_text(ref_text, encoding="utf-8")

(root / "CHANGES_v52_AUTUPDATE.txt").write_text(
    "Mabi_Auto v52\n"
    "- UI click crash protection\n"
    "- Abyss current-step text layout fix\n"
    "- Dungeon selection menu shown only in Abyss mode\n"
    "- Left footer slogan removed\n"
    "- Abyss ready state shows selected dungeon name on the next line\n"
    "- Startup automatic update enabled for future releases\n"
    "- Missing decorative ReferenceUI artwork no longer breaks Windows builds\n",
    encoding="utf-8",
)
print("v52 files applied successfully")
