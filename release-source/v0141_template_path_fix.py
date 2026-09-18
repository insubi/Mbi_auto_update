#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0141_template_path_fix.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
targets_path = app / "dungeon" / "config" / "targets.json"
detector_path = app / "dungeon" / "TargetDetector.cs"
matcher_path = app / "dungeon" / "TemplateMatcher.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

# 1) Fix every bad slot template path. ScenarioEngine's baseDir is already
#    <release>/dungeon, so all dungeon templates must be relative to that folder.
targets = json.loads(read(targets_path))
slot_ids = {
    "route_d1_1",
    "route_d2_1",
    "route_regular_1_1",
    "route_regular_2_1",
}
fixed = []
for t in targets:
    tid = t.get("Id")
    if tid not in slot_ids:
        continue
    p = t.get("TemplatePath") or ""
    if p.startswith("dungeon/templates/"):
        t["TemplatePath"] = p[len("dungeon/"):]
        fixed.append(tid)
    elif p.startswith("templates/"):
        fixed.append(tid)
    else:
        raise RuntimeError(f"{tid}: unexpected template path: {p}")

if set(fixed) != slot_ids:
    raise RuntimeError("not all slot paths were fixed: " + ",".join(sorted(fixed)))

write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# 2) Fail fast at TargetDetector construction for ALL configured template paths.
#    This protects every dungeon template target, not only 1-1/2-1.
detector = read(detector_path)
old_ctor = '''    public TargetDetector(IEnumerable<TargetDefinition> targets, string baseDir)
    {
        _targets = targets.ToDictionary(t => t.Id, StringComparer.OrdinalIgnoreCase);
        _ocr = new OcrRecognizer();
        _template = new TemplateMatcher(baseDir);
    }
'''
new_ctor = '''    public TargetDetector(IEnumerable<TargetDefinition> targets, string baseDir)
    {
        _targets = targets.ToDictionary(t => t.Id, StringComparer.OrdinalIgnoreCase);

        foreach (var t in _targets.Values)
        {
            if (string.IsNullOrWhiteSpace(t.TemplatePath)) continue;

            string resolved = Path.IsPathRooted(t.TemplatePath)
                ? t.TemplatePath
                : Path.Combine(baseDir, t.TemplatePath.Replace('/', Path.DirectorySeparatorChar));

            if (!File.Exists(resolved))
                throw new FileNotFoundException(
                    $"던전 템플릿 파일을 찾을 수 없습니다. target={t.Id}, path={resolved}",
                    resolved);
        }

        _ocr = new OcrRecognizer();
        _template = new TemplateMatcher(baseDir);
    }
'''
detector = replace_once(detector, old_ctor, new_ctor, "TargetDetector template preflight")
write(detector_path, detector)

# 3) Make both template matchers explicit if a future caller bypasses constructor preflight.
matcher = read(matcher_path)
old_missing = '        if (!File.Exists(fullPath)) return DetectionResult.NotFound;'
count = matcher.count(old_missing)
if count != 2:
    raise RuntimeError(f"TemplateMatcher missing-path anchors: expected 2, found {count}")
new_missing = '''        if (!File.Exists(fullPath))
            throw new FileNotFoundException($"템플릿 파일을 찾을 수 없습니다: {fullPath}", fullPath);'''
matcher = matcher.replace(old_missing, new_missing)
write(matcher_path, matcher)

# 4) Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.40", "V0.1.41")
                   .replace("0.1.40.0", "0.1.41.0")
                   .replace("0.1.40", "0.1.41"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.41_TEMPLATE_PATH_FIX.txt").write_text(
    "MABI AUTO V0.1.41 - ALL DUNGEON TEMPLATE PATH FIX\n\n"
    "Audited all 10 dungeon targets that use template files.\n"
    "The six legacy template paths were already correct.\n"
    "Fixes all four V0.1.39 slot template paths: Peaca D1-1/D2-1 and shared Runda/Fiod 1-1/2-1.\n"
    "ScenarioEngine already uses <release>/dungeon as its base directory, so slot paths are now templates/... rather than dungeon/templates/....\n"
    "TargetDetector now preflights every configured TemplatePath at dungeon start and reports target ID plus the resolved missing path immediately.\n"
    "TemplateMatcher also throws an explicit missing-file error instead of silently returning score 0.000.\n"
    "V0.1.40 binary-glyph multi-scale + OCR backup, five-minute arrival wait, 30-second slot wait, purple icon click, and no-fallback safety remain unchanged.\n"
    "Automatic recovery is not added in this version.\n",
    encoding="utf-8"
)

# 5) Structural + filesystem verification for ALL template targets.
targets_check = json.loads(read(targets_path))
template_targets = [t for t in targets_check if t.get("TemplatePath")]
if len(template_targets) != 10:
    raise RuntimeError(f"expected 10 template targets, found {len(template_targets)}")

for t in template_targets:
    rel = t["TemplatePath"]
    resolved = app / "dungeon" / Path(rel.replace("/", str(Path('/'))))
    # Cross-platform-safe re-resolution:
    resolved = app / "dungeon"
    for part in rel.split("/"):
        resolved = resolved / part
    if not resolved.exists():
        raise RuntimeError(f"template target unresolved after fix: {t.get('Id')} -> {resolved}")
    if rel.startswith("dungeon/templates/"):
        raise RuntimeError(f"duplicate dungeon prefix remains: {t.get('Id')} -> {rel}")

expected_slot_paths = {
    "route_d1_1": "templates/slot_peaca_d1_1_v0139.jpg",
    "route_d2_1": "templates/slot_peaca_d2_1_v0139.jpg",
    "route_regular_1_1": "templates/slot_regular_1_1_v0139.jpg",
    "route_regular_2_1": "templates/slot_regular_2_1_v0139.jpg",
}
by_id = {t.get("Id"): t for t in targets_check}
for tid, expected in expected_slot_paths.items():
    if by_id[tid].get("TemplatePath") != expected:
        raise RuntimeError(f"{tid}: path mismatch: {by_id[tid].get('TemplatePath')}")

detector_check = read(detector_path)
matcher_check = read(matcher_path)
for marker in (
    "foreach (var t in _targets.Values)",
    "던전 템플릿 파일을 찾을 수 없습니다",
    "target={t.Id}, path={resolved}",
):
    if marker not in detector_check:
        raise RuntimeError("template preflight marker missing: " + marker)
if matcher_check.count("템플릿 파일을 찾을 수 없습니다: {fullPath}") != 2:
    raise RuntimeError("TemplateMatcher fail-fast guards missing")

print("V0.1.41 patch applied: all 10 dungeon template paths validated; 4 slot paths corrected")
