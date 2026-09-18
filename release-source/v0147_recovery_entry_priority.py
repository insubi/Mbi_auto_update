#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0147_recovery_entry_priority.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

engine = read(engine_path)

old = '''            // Most specific later-stage screens first.
            var retry = await _detector.DetectAsync("retry", frame, ct);
            if (retry.Found)
            {
                int step = FindDungeonStepIndex("retry");
                Log?.Invoke($"[던전 자동복구] 다시 하기 확인 -> {step + 1}단계 재개");
                return step;
            }

            var touch = await _detector.DetectAsync("touch_result", frame, ct);
            if (touch.Found)
            {
                int step = FindDungeonStepIndex("touch_result");
                Log?.Invoke($"[던전 자동복구] 전투 종료/터치 화면 확인 -> {step + 1}단계 재개");
                return step;
            }

            // selected/challenge are the same logical entry-state stage.
            var selected = await _detector.DetectAsync("selected", frame, ct);
            if (selected.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] 선택됨 확인 -> 도전 상태 확인 {step + 1}단계 재개");
                return step;
            }

            var challenge = await _detector.DetectAsync("challenge", frame, ct);
            if (challenge.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] 도전 확인 -> {step + 1}단계 재개");
                return step;
            }

            // Entry text alone never authorizes entry; return through challenge verification.
            var enter = await _detector.DetectAsync("enter_bottom", frame, ct);
            if (enter.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] 입장하기 확인 -> 안전하게 도전 상태 확인 {step + 1}단계 재개");
                return step;
            }
'''

new = '''            // V0.1.47 recovery priority:
            // If the current screen is an entry-state screen, it must win over retry/touch.
            // This prevents the loose bottom-area retry detector from sending recovery back
            // to step 4 while the game is actually showing selected/challenge/entry.
            var selected = await _detector.DetectAsync("selected_ocr_strict", frame, ct);
            var challenge = await _detector.DetectAsync("challenge_confirm_strict", frame, ct);
            var enter = await _detector.DetectAsync("enter_bottom", frame, ct);

            if (selected.Found || challenge.Found || enter.Found)
            {
                int step = FindDungeonStepIndex("enter_bottom");
                Log?.Invoke(
                    $"[던전 자동복구] 입장 화면 우선 판정 -> {step + 1}단계 재개 " +
                    $"selected={(selected.Found ? 1 : 0)} " +
                    $"challenge={(challenge.Found ? 1 : 0)} " +
                    $"enter={(enter.Found ? 1 : 0)}");
                return step;
            }

            var touch = await _detector.DetectAsync("touch_result", frame, ct);
            if (touch.Found)
            {
                int step = FindDungeonStepIndex("touch_result");
                Log?.Invoke($"[던전 자동복구] 전투 종료/터치 화면 확인 -> {step + 1}단계 재개");
                return step;
            }

            // Retry recovery is allowed only after exact entry-state checks failed.
            // Use the strict OCR-only target added in V0.1.46; never the loose hybrid retry here.
            var retry = await _detector.DetectAsync("retry_ocr_strict", frame, ct);
            if (retry.Found)
            {
                int step = FindDungeonStepIndex("retry");
                Log?.Invoke($"[던전 자동복구] 정확 OCR 다시 하기 확인 -> {step + 1}단계 재개 OCR={retry.ReadText} bounds={retry.Bounds}");
                return step;
            }
'''

engine = replace_once(engine, old, new, "recovery priority block")
write(engine_path, engine)

# Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.46", "V0.1.47")
                   .replace("0.1.46.0", "0.1.47.0")
                   .replace("0.1.46", "0.1.47"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.47_RECOVERY_ENTRY_PRIORITY.txt").write_text(
    "MABI AUTO V0.1.47 - RECOVERY ENTRY PRIORITY\n\n"
    "Fixes the V0.1.46 runtime failure where recovery repeatedly resumed step 4 (retry) while the game screen was actually in challenge state.\n"
    "Recovery now checks exact selected/challenge/right-entry state first and immediately resumes the first enter_bottom step.\n"
    "Only when no entry-state signal is visible does recovery consider touch_result, then strict OCR-only retry_ocr_strict.\n"
    "The loose hybrid retry target is no longer used by DetectKnownDungeonRecoveryStepAsync.\n"
    "V0.1.46 retry click guard, scene_skip entry suppression, exact state OCR, selected-card safe click, and Space-only entry remain unchanged.\n",
    encoding="utf-8"
)

check = read(engine_path)
required = (
    "[던전 자동복구] 입장 화면 우선 판정",
    'DetectAsync("selected_ocr_strict", frame, ct)',
    'DetectAsync("challenge_confirm_strict", frame, ct)',
    'FindDungeonStepIndex("enter_bottom")',
    'DetectAsync("retry_ocr_strict", frame, ct)',
    "정확 OCR 다시 하기 확인",
)
for marker in required:
    if marker not in check:
        raise RuntimeError("V0.1.47 marker missing: " + marker)

start = check.index("private async Task<int?> DetectKnownDungeonRecoveryStepAsync")
end = check.index("// DUNGEON_SCREEN_FIRST_RECOVERY_V6", start)
block = check[start:end]
if 'DetectAsync("retry", frame, ct)' in block:
    raise RuntimeError("loose retry still present in recovery detector")
if block.index('DetectAsync("selected_ocr_strict", frame, ct)') > block.index('DetectAsync("retry_ocr_strict", frame, ct)'):
    raise RuntimeError("entry state is not checked before retry")

print("V0.1.47 patch applied: recovery entry-state priority + strict retry only")
