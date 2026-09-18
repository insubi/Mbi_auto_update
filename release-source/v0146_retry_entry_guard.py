#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0146_retry_entry_guard.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
detector_path = app / "dungeon" / "TargetDetector.cs"
targets_path = app / "dungeon" / "config" / "targets.json"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

# 1) Add a strict retry OCR target for the entry verifier.
targets = json.loads(read(targets_path))
if not any(t.get("Id") == "retry_ocr_strict" for t in targets):
    retry = next((t for t in targets if t.get("Id") == "retry"), None)
    if retry is None:
        raise RuntimeError("retry target missing")
    strict = {
        "Id": "retry_ocr_strict",
        "Kind": "ocr",
        "Roi": retry["Roi"],
        "Text": "다시 하기",
        "MaxEditDistance": 0,
        "OcrRetryAt2x": True
    }
    idx = targets.index(retry) + 1
    targets.insert(idx, strict)
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# 2) Make strict retry OCR return only the exact word bounds.
detector = read(detector_path)
old = '''            bool exactDungeonEntryState =
                id.Equals("selected_ocr_strict", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("challenge_confirm_strict", StringComparison.OrdinalIgnoreCase);

            if (exactDungeonSlot || exactClickableEntry || exactDungeonEntryState)
                return await _ocr.FindCompactLabelAsync(frame, roi, t.Text, ct);
'''
new = '''            bool exactDungeonEntryState =
                id.Equals("selected_ocr_strict", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("challenge_confirm_strict", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("retry_ocr_strict", StringComparison.OrdinalIgnoreCase);

            if (exactDungeonSlot || exactClickableEntry || exactDungeonEntryState)
                return await _ocr.FindCompactLabelAsync(frame, roi, t.Text, ct);
'''
detector = replace_once(detector, old, new, "strict retry OCR routing")
write(detector_path, detector)

engine = read(engine_path)

# 3) In VerifyChallengeBeforeEntryAsync, never use the loose hybrid retry target.
#    The old target overlaps the bottom party/entry buttons and can false-match there.
engine = replace_once(
    engine,
    'var normalRetry = await _detector.DetectAsync("retry", frame, ct);',
    'var normalRetry = await _detector.DetectAsync("retry_ocr_strict", frame, ct);',
    "entry verifier strict retry first check")
engine = replace_once(
    engine,
    'var retryConfirm = await _detector.DetectAsync("retry", retryConfirmFrame, ct);',
    'var retryConfirm = await _detector.DetectAsync("retry_ocr_strict", retryConfirmFrame, ct);',
    "entry verifier strict retry confirmation")
engine = replace_once(
    engine,
    'var stillRetry = await _detector.DetectAsync("retry", afterRetryFrame, ct);',
    'var stillRetry = await _detector.DetectAsync("retry_ocr_strict", afterRetryFrame, ct);',
    "entry verifier strict retry post-check")

# 4) Defense in depth for the normal scenario retry step:
#    if any exact entry-screen signal is visible, do not click a retry candidate.
click_anchor = '''                if (step.Type.Equals("wait_click", StringComparison.OrdinalIgnoreCase))
                {
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
'''
click_guard = '''                if (step.Type.Equals("wait_click", StringComparison.OrdinalIgnoreCase))
                {
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);

                    if (step.Target.Equals("retry", StringComparison.OrdinalIgnoreCase))
                    {
                        var retryGuardSelected = await _detector.DetectAsync("selected_ocr_strict", frame, ct);
                        var retryGuardChallenge = await _detector.DetectAsync("challenge_confirm_strict", frame, ct);
                        var retryGuardEnter = await _detector.DetectAsync("enter_bottom", frame, ct);

                        if (retryGuardSelected.Found || retryGuardChallenge.Found || retryGuardEnter.Found)
                        {
                            Log?.Invoke(
                                $"[retry guard] 입장 화면에서는 다시 하기 클릭 금지 " +
                                $"selected={(retryGuardSelected.Found ? 1 : 0)} " +
                                $"challenge={(retryGuardChallenge.Found ? 1 : 0)} " +
                                $"enter={(retryGuardEnter.Found ? 1 : 0)} " +
                                $"retryCandidate={found.Bounds}");
                            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                            continue;
                        }
                    }

                    if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
'''
engine = replace_once(engine, click_anchor, click_guard, "scenario retry entry guard")

# 5) Explicit logging so the next report tells us which retry path was used.
engine = engine.replace(
    'Log?.Invoke($"[던전 결과] 다시 하기 감지 1/2 score={normalRetry.Score:0.000}");',
    'Log?.Invoke($"[던전 결과] 정확 OCR 다시 하기 감지 1/2 OCR={normalRetry.ReadText} bounds={normalRetry.Bounds}");')
engine = engine.replace(
    'Log?.Invoke($"[던전 결과] 다시 하기 2/2 연속 확인 score={retryConfirm.Score:0.000}");',
    'Log?.Invoke($"[던전 결과] 정확 OCR 다시 하기 2/2 연속 확인 OCR={retryConfirm.ReadText} bounds={retryConfirm.Bounds}");')

write(engine_path, engine)

# 6) Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.45", "V0.1.46")
                   .replace("0.1.45.0", "0.1.46.0")
                   .replace("0.1.45", "0.1.46"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.46_RETRY_ENTRY_GUARD.txt").write_text(
    "MABI AUTO V0.1.46 - RETRY / ENTRY SCREEN GUARD\n\n"
    "Root cause hardening for the repeated party-search click on the selected dungeon screen.\n"
    "The normal-result retry fast path used a loose hybrid retry detector over X=180..619,Y=830..999, which overlaps the party-search/entry button area.\n"
    "Inside VerifyChallengeBeforeEntryAsync it now uses a new exact compact OCR target retry_ocr_strict (text: '다시 하기') with no template fallback and edit distance 0.\n"
    "The normal scenario retry click is also blocked whenever exact selected/challenge/entry screen evidence is visible.\n"
    "V0.1.45 exact selected/challenge OCR, scene_skip suppression during entry, selected-card safe click, and Space-only entry remain unchanged.\n",
    encoding="utf-8"
)

# Structural verification.
targets_check = {t.get("Id"): t for t in json.loads(read(targets_path))}
strict = targets_check.get("retry_ocr_strict")
if strict is None:
    raise RuntimeError("retry_ocr_strict missing")
if strict.get("Kind") != "ocr" or strict.get("Text") != "다시 하기" or int(strict.get("MaxEditDistance", -1)) != 0:
    raise RuntimeError("retry_ocr_strict config mismatch")

detector_check = read(detector_path)
engine_check = read(engine_path)

for marker in (
    'id.Equals("retry_ocr_strict"',
    'DetectAsync("retry_ocr_strict", frame, ct)',
    'DetectAsync("retry_ocr_strict", retryConfirmFrame, ct)',
    'DetectAsync("retry_ocr_strict", afterRetryFrame, ct)',
    "[retry guard] 입장 화면에서는 다시 하기 클릭 금지",
    "정확 OCR 다시 하기 감지 1/2",
):
    if marker not in detector_check and marker not in engine_check:
        raise RuntimeError("V0.1.46 marker missing: " + marker)

# The verifier must not use the loose hybrid retry target anymore.
verify_start = engine_check.index("private async Task VerifyChallengeBeforeEntryAsync")
verify_end = engine_check.index("private async Task<bool> VerifyAbyssSelectionScreenAsync", verify_start)
verify_block = engine_check[verify_start:verify_end]
if 'DetectAsync("retry", frame, ct)' in verify_block:
    raise RuntimeError("loose retry detector still present in entry verifier")

print("V0.1.46 patch applied: strict retry OCR + entry-screen retry click guard")
