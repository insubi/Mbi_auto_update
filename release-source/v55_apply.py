#!/usr/bin/env python3
from pathlib import Path
import base64, json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path): return path.read_text(encoding="utf-8-sig")
def write(path, text): path.write_text(text, encoding="utf-8-sig")

# Version bump v54 -> v55.
p = app / "UpdateManager.cs"
s = read(p)
old = 'public const string CurrentVersion = "v54";'
if old not in s: raise RuntimeError("v54 UpdateManager version not found")
write(p, s.replace(old, 'public const string CurrentVersion = "v55";', 1))

p = app / "MainForm.Dashboard.cs"
s = read(p).replace('Text = "v54.0.0"', 'Text = "v55.0.0"')
s = s.replace('Dashboard v54', 'Dashboard v55').replace('v54  |  Mabi Auto', 'v55  |  Mabi Auto')
write(p, s)

p = app / "MainForm.ReferenceUI.cs"
write(p, read(p).replace('v54.0.0 · UI', 'v55.0.0 · UI'))

p = app / "FishingAutomation.csproj"
s = read(p)
for key, value in {"Version":"55.0.0", "AssemblyVersion":"55.0.0.0", "FileVersion":"55.0.0.0"}.items():
    pat = rf'<{key}>[^<]+</{key}>'
    if not re.search(pat, s): raise RuntimeError(f"v55 version tag missing: {key}")
    s = re.sub(pat, f'<{key}>{value}</{key}>', s, count=1)
write(p, s)

# Save the supplied purple challenge button as a grayscale visual template.
# TemplateMatcher also compares in grayscale, so this visual check is color-insensitive
# and covers both the older red challenge button and the current purple button.
td = app / "dungeon" / "templates"
td.mkdir(parents=True, exist_ok=True)
(td / "challenge_visual.png").write_bytes(base64.b64decode("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"))

# Keep challenge recognition limited to the real button area.
# This prevents the lower explanatory sentence containing '도전' from authorizing entry.
targets = [
  {"Id":"challenge_confirm_strict","Kind":"ocr","Roi":{"X":455,"Y":700,"Width":210,"Height":115},"Text":"도전","MaxEditDistance":0,"OcrRetryAt2x":True},
  {"Id":"challenge","Kind":"ocr","Roi":{"X":455,"Y":700,"Width":210,"Height":115},"Text":"도전","MaxEditDistance":1,"OcrRetryAt2x":True},
  {"Id":"challenge_visual","Kind":"template","Roi":{"X":455,"Y":700,"Width":210,"Height":115},"TemplatePath":"templates/challenge_visual.png","Threshold":0.68,"TemplateScaleMin":0.75,"TemplateScaleMax":1.25,"TemplateScaleStep":0.05},
  {"Id":"selected","Kind":"ocr","Roi":{"X":455,"Y":700,"Width":210,"Height":115},"Text":"선택됨","MaxEditDistance":1,"OcrRetryAt2x":True},
  {"Id":"enter_bottom","Kind":"ocr","Roi":{"X":0,"Y":900,"Width":800,"Height":100},"Text":"입장하기","MaxEditDistance":1,"OcrRetryAt2x":True},
  {"Id":"enter_confirm","Kind":"ocr","Roi":{"X":140,"Y":880,"Width":560,"Height":120},"Text":"입장하기","MaxEditDistance":1,"OcrRetryAt2x":True},
  {"Id":"touch_result","Kind":"ocr","Roi":{"X":240,"Y":900,"Width":360,"Height":100},"Text":"터치해","MaxEditDistance":1,"OcrRetryAt2x":True},
  {"Id":"retry","Kind":"ocr","Roi":{"X":340,"Y":900,"Width":360,"Height":100},"Text":"다시하기","MaxEditDistance":1,"OcrRetryAt2x":True},
  {"Id":"scene_skip","Kind":"hybrid","Roi":{"X":0,"Y":0,"Width":800,"Height":1000},"Text":"장면 넘기기","MaxEditDistance":1,"OcrRetryAt2x":True,"TemplatePath":"templates/scene_skip_phone.jpg","Threshold":0.62,"TemplateScaleMin":0.50,"TemplateScaleMax":1.40,"TemplateScaleStep":0.08}
]
write(app / "dungeon" / "config" / "targets.json", json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# challenge = color-insensitive button image OR OCR '도전'.
(app / "dungeon" / "TargetDetector.cs").write_bytes(base64.b64decode("77u/bmFtZXNwYWNlIER1bmdlb25WaXNpb25Cb3Q7CgppbnRlcm5hbCBzZWFsZWQgY2xhc3MgVGFyZ2V0RGV0ZWN0b3IKewogICAgcHJpdmF0ZSByZWFkb25seSBEaWN0aW9uYXJ5PHN0cmluZywgVGFyZ2V0RGVmaW5pdGlvbj4gX3RhcmdldHM7CiAgICBwcml2YXRlIHJlYWRvbmx5IE9jclJlY29nbml6ZXIgX29jcjsKICAgIHByaXZhdGUgcmVhZG9ubHkgVGVtcGxhdGVNYXRjaGVyIF90ZW1wbGF0ZTsKCiAgICBwdWJsaWMgVGFyZ2V0RGV0ZWN0b3IoSUVudW1lcmFibGU8VGFyZ2V0RGVmaW5pdGlvbj4gdGFyZ2V0cywgc3RyaW5nIGJhc2VEaXIpCiAgICB7CiAgICAgICAgX3RhcmdldHMgPSB0YXJnZXRzLlRvRGljdGlvbmFyeSh0ID0+IHQuSWQsIFN0cmluZ0NvbXBhcmVyLk9yZGluYWxJZ25vcmVDYXNlKTsKICAgICAgICBfb2NyID0gbmV3IE9jclJlY29nbml6ZXIoKTsKICAgICAgICBfdGVtcGxhdGUgPSBuZXcgVGVtcGxhdGVNYXRjaGVyKGJhc2VEaXIpOwogICAgfQoKICAgIHB1YmxpYyBUYXJnZXREZWZpbml0aW9uIEdldChzdHJpbmcgaWQpID0+IF90YXJnZXRzLlRyeUdldFZhbHVlKGlkLCBvdXQgdmFyIHQpCiAgICAgICAgPyB0IDogdGhyb3cgbmV3IEtleU5vdEZvdW5kRXhjZXB0aW9uKCQidGFyZ2V0cy5qc29u7JeQICd7aWR9JyDtg4DquYPsnbQg7JeG7Iq164uI64ukLiIpOwoKICAgIHB1YmxpYyBhc3luYyBUYXNrPERldGVjdGlvblJlc3VsdD4gRGV0ZWN0QXN5bmMoc3RyaW5nIGlkLCBCaXRtYXAgZnJhbWUsIENhbmNlbGxhdGlvblRva2VuIGN0KQogICAgewogICAgICAgIGlmIChpZC5FcXVhbHMoImNoYWxsZW5nZSIsIFN0cmluZ0NvbXBhcmlzb24uT3JkaW5hbElnbm9yZUNhc2UpKQogICAgICAgICAgICByZXR1cm4gYXdhaXQgRGV0ZWN0Q2hhbGxlbmdlQXN5bmMoZnJhbWUsIGN0KTsKCiAgICAgICAgdmFyIHQgPSBHZXQoaWQpOwogICAgICAgIHJldHVybiBhd2FpdCBEZXRlY3REZWZpbml0aW9uQXN5bmModCwgZnJhbWUsIGN0KTsKICAgIH0KCiAgICBwcml2YXRlIGFzeW5jIFRhc2s8RGV0ZWN0aW9uUmVzdWx0PiBEZXRlY3RDaGFsbGVuZ2VBc3luYyhCaXRtYXAgZnJhbWUsIENhbmNlbGxhdGlvblRva2VuIGN0KQogICAgewogICAgICAgIC8vIFRoZSB2aXN1YWwgdGVtcGxhdGUgaXMgZ3JheXNjYWxlLCBzbyB0aGUgc2FtZSBidXR0b24gc2hhcGUgbWF0Y2hlcwogICAgICAgIC8vIGJvdGggdGhlIG9sZGVyIHJlZCBza2luIGFuZCB0aGUgY3VycmVudCBwdXJwbGUgc2tpbi4KICAgICAgICBpZiAoX3RhcmdldHMuVHJ5R2V0VmFsdWUoImNoYWxsZW5nZV92aXN1YWwiLCBvdXQgdmFyIHZpc3VhbFRhcmdldCkpCiAgICAgICAgewogICAgICAgICAgICB2YXIgdmlzdWFsID0gYXdhaXQgRGV0ZWN0RGVmaW5pdGlvbkFzeW5jKHZpc3VhbFRhcmdldCwgZnJhbWUsIGN0KTsKICAgICAgICAgICAgaWYgKHZpc3VhbC5Gb3VuZCkgcmV0dXJuIHZpc3VhbDsKICAgICAgICB9CgogICAgICAgIC8vIE9DUiBmYWxsYmFjayBpcyBpbnRlbnRpb25hbGx5IHJlc3RyaWN0ZWQgdG8gdGhlIGNoYWxsZW5nZS1idXR0b24gUk9JLgogICAgICAgIGlmIChfdGFyZ2V0cy5UcnlHZXRWYWx1ZSgiY2hhbGxlbmdlIiwgb3V0IHZhciBvY3JUYXJnZXQpKQogICAgICAgICAgICByZXR1cm4gYXdhaXQgRGV0ZWN0RGVmaW5pdGlvbkFzeW5jKG9jclRhcmdldCwgZnJhbWUsIGN0KTsKCiAgICAgICAgcmV0dXJuIERldGVjdGlvblJlc3VsdC5Ob3RGb3VuZDsKICAgIH0KCiAgICBwcml2YXRlIGFzeW5jIFRhc2s8RGV0ZWN0aW9uUmVzdWx0PiBEZXRlY3REZWZpbml0aW9uQXN5bmMoVGFyZ2V0RGVmaW5pdGlvbiB0LCBCaXRtYXAgZnJhbWUsIENhbmNlbGxhdGlvblRva2VuIGN0KQogICAgewogICAgICAgIHZhciByb2kgPSBXaW5kb3dDYXB0dXJlLkNsYW1wUm9pKHQuUm9pLlRvUmVjdGFuZ2xlKCksIGZyYW1lLlNpemUpOwogICAgICAgIGlmIChyb2kuV2lkdGggPCAyIHx8IHJvaS5IZWlnaHQgPCAyKSByZXR1cm4gRGV0ZWN0aW9uUmVzdWx0Lk5vdEZvdW5kOwoKICAgICAgICBpZiAodC5LaW5kLkVxdWFscygib2NyIiwgU3RyaW5nQ29tcGFyaXNvbi5PcmRpbmFsSWdub3JlQ2FzZSkpCiAgICAgICAgewogICAgICAgICAgICBpZiAoc3RyaW5nLklzTnVsbE9yV2hpdGVTcGFjZSh0LlRleHQpKSByZXR1cm4gRGV0ZWN0aW9uUmVzdWx0Lk5vdEZvdW5kOwogICAgICAgICAgICByZXR1cm4gYXdhaXQgX29jci5GaW5kVGV4dEFzeW5jKGZyYW1lLCByb2ksIHQuVGV4dCwgdC5NYXhFZGl0RGlzdGFuY2UsIHQuT2NyUmV0cnlBdDJ4LCBjdCk7CiAgICAgICAgfQoKICAgICAgICBpZiAodC5LaW5kLkVxdWFscygidGVtcGxhdGUiLCBTdHJpbmdDb21wYXJpc29uLk9yZGluYWxJZ25vcmVDYXNlKSkKICAgICAgICB7CiAgICAgICAgICAgIGlmIChzdHJpbmcuSXNOdWxsT3JXaGl0ZVNwYWNlKHQuVGVtcGxhdGVQYXRoKSkgcmV0dXJuIERldGVjdGlvblJlc3VsdC5Ob3RGb3VuZDsKICAgICAgICAgICAgcmV0dXJuIF90ZW1wbGF0ZS5GaW5kTXVsdGlTY2FsZSgKICAgICAgICAgICAgICAgIGZyYW1lLCByb2ksIHQuVGVtcGxhdGVQYXRoLCB0LlRocmVzaG9sZCwKICAgICAgICAgICAgICAgIHQuVGVtcGxhdGVTY2FsZU1pbiwgdC5UZW1wbGF0ZVNjYWxlTWF4LCB0LlRlbXBsYXRlU2NhbGVTdGVwKTsKICAgICAgICB9CgogICAgICAgIGlmICh0LktpbmQuRXF1YWxzKCJoeWJyaWQiLCBTdHJpbmdDb21wYXJpc29uLk9yZGluYWxJZ25vcmVDYXNlKSkKICAgICAgICB7CiAgICAgICAgICAgIGlmICghc3RyaW5nLklzTnVsbE9yV2hpdGVTcGFjZSh0LlRlbXBsYXRlUGF0aCkpCiAgICAgICAgICAgIHsKICAgICAgICAgICAgICAgIHZhciB2aXN1YWwgPSBfdGVtcGxhdGUuRmluZE11bHRpU2NhbGUoCiAgICAgICAgICAgICAgICAgICAgZnJhbWUsIHJvaSwgdC5UZW1wbGF0ZVBhdGgsIHQuVGhyZXNob2xkLAogICAgICAgICAgICAgICAgICAgIHQuVGVtcGxhdGVTY2FsZU1pbiwgdC5UZW1wbGF0ZVNjYWxlTWF4LCB0LlRlbXBsYXRlU2NhbGVTdGVwKTsKICAgICAgICAgICAgICAgIGlmICh2aXN1YWwuRm91bmQpIHJldHVybiB2aXN1YWw7CiAgICAgICAgICAgIH0KCiAgICAgICAgICAgIGlmICghc3RyaW5nLklzTnVsbE9yV2hpdGVTcGFjZSh0LlRleHQpKQogICAgICAgICAgICAgICAgcmV0dXJuIGF3YWl0IF9vY3IuRmluZFRleHRBc3luYyhmcmFtZSwgcm9pLCB0LlRleHQsIHQuTWF4RWRpdERpc3RhbmNlLCB0Lk9jclJldHJ5QXQyeCwgY3QpOwoKICAgICAgICAgICAgcmV0dXJuIERldGVjdGlvblJlc3VsdC5Ob3RGb3VuZDsKICAgICAgICB9CgogICAgICAgIHRocm93IG5ldyBOb3RTdXBwb3J0ZWRFeGNlcHRpb24oJCLslYwg7IiYIOyXhuuKlCDtg4DquYMg7KKF66WYOiB7dC5LaW5kfSIpOwogICAgfQp9Cg=="))

(root / "CHANGES_v55_DUNGEON_CHALLENGE_DETECTION.txt").write_text(
  "Mabi_Auto v55\n"
  "- Dungeon entry accepts the challenge state only when the challenge-button image (red or purple, color-insensitive) or OCR '도전' is detected.\n"
  "- Purple challenge image was cropped from the supplied screenshot and stored as the visual template.\n"
  "- OCR is restricted to the actual challenge-button area.\n"
  "- Existing 3 consecutive confirmations plus the 2-second final confirmation remain enabled.\n"
  "- If '선택됨' is visible, entry remains blocked.\n"
  "- v54 Abyss behavior and all unrelated logic remain unchanged.\n",
  encoding="utf-8")

print("v55 challenge detection applied")