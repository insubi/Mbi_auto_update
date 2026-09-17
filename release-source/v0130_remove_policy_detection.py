#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0130_remove_policy_detection.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
dungeon_targets_path = app / "dungeon" / "config" / "targets.json"
abyss_targets_path = app / "abyss" / "config" / "targets.json"

REMOVE_TARGETS = {"policy_shutdown", "policy_error88"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def remove_policy_targets(path: Path) -> None:
    if not path.exists():
        return
    data = json.loads(read(path))
    kept = [x for x in data if str(x.get("Id", "")).lower() not in REMOVE_TARGETS]
    if len(kept) == len(data):
        raise RuntimeError(f"policy targets not found in {path}")
    write(path, json.dumps(kept, ensure_ascii=False, indent=2) + "\n")


# Remove both OCR targets from regular dungeon and Abyss configs.
remove_policy_targets(dungeon_targets_path)
remove_policy_targets(abyss_targets_path)

engine = read(engine_path)

# Remove the V0.1.28 recovery-classifier policy/ERROR88 check.
classifier_block = '''            // V0.1.28 safety gate: do not send recovery input on a policy shutdown screen.
            var policy = await _detector.DetectAsync("policy_shutdown", frame, ct);
            var error88 = await _detector.DetectAsync("policy_error88", frame, ct);
            if (policy.Found || error88.Found)
            {
                Log?.Invoke("[던전 자동복구] 운영 정책/ERROR 88 종료 화면 감지 -> 모든 복구 입력 중지");
                throw new InvalidOperationException("DUNGEON_POLICY_SHUTDOWN_DETECTED: 운영 정책/ERROR 88 화면 감지 -> 자동 입력 즉시 정지");
            }

'''
if classifier_block not in engine:
    raise RuntimeError("recovery classifier policy block not found")
engine = engine.replace(classifier_block, "", 1)

# Remove the special policy exception passthrough; ordinary recovery exceptions remain.
catch_block = '''        catch (InvalidOperationException ex) when (ex.Message.StartsWith("DUNGEON_POLICY_SHUTDOWN_DETECTED", StringComparison.Ordinal))
        {
            // Intentionally escape Smart Recovery. RunAsync does not swallow this exception,
            // so the dungeon automation stops instead of sending more game input.
            throw;
        }
'''
if catch_block not in engine:
    raise RuntimeError("policy passthrough catch block not found")
engine = engine.replace(catch_block, "", 1)

# Remove the V0.1.29 global policy guard helper, but keep CheckMonitorsAsync itself.
helper_marker = "    // DUNGEON_GLOBAL_POLICY_GUARD_V7\n"
check_sig = "    private async Task<bool> CheckMonitorsAsync(Bitmap frame, CancellationToken ct)\n    {\n"
helper_start = engine.find(helper_marker)
check_start = engine.find(check_sig, helper_start)
if helper_start < 0 or check_start < 0 or check_start <= helper_start:
    raise RuntimeError("global policy guard helper boundary not found")
engine = engine[:helper_start] + engine[check_start:]

leading_guard = check_sig + "        await ThrowIfDungeonPolicyShutdownAsync(frame, ct);\n"
if leading_guard not in engine:
    raise RuntimeError("monitor leading policy guard call not found")
engine = engine.replace(leading_guard, check_sig, 1)

# Keep two-frame scene-skip confirmation, but remove the policy OCR call from its confirm frame.
confirm_guard = "                await ThrowIfDungeonPolicyShutdownAsync(confirmFrame, ct);\n"
if confirm_guard not in engine:
    raise RuntimeError("scene-skip confirm policy guard call not found")
engine = engine.replace(confirm_guard, "", 1)

for forbidden in [
    'policy_shutdown',
    'policy_error88',
    'ThrowIfDungeonPolicyShutdownAsync',
    'DUNGEON_POLICY_SHUTDOWN_DETECTED',
    'DUNGEON_GLOBAL_POLICY_GUARD_V7',
    '운영 정책/ERROR 88',
]:
    if forbidden in engine:
        raise RuntimeError(f"policy detection residue remains in ScenarioEngine.cs: {forbidden}")

# Preserve all unrelated V0.1.29 hardening and previous dungeon/Abyss behavior.
for marker in [
    "DUNGEON_FULL_STABILITY_HARDENING_V7",
    "동일 단계 복구",
    "같은 복구 단계가",
    "scene_skip 1/2 확인",
    "scene_skip 2/2 연속 확인",
    "DUNGEON_SCREEN_FIRST_RECOVERY_V6",
    "DUNGEON_CHALLENGE_DISAMBIGUATION_V5",
    "던전 밖 HUD 3/4 이상 확인",
    "어비스 클릭 검증 실패",
]:
    if marker not in engine:
        raise RuntimeError(f"preserved marker missing: {marker}")

write(engine_path, engine)

# Runtime version bump only.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.29", "V0.1.30")
                   .replace("0.1.29.0", "0.1.30.0")
                   .replace("0.1.29", "0.1.30"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.30_REMOVE_POLICY_DETECTION.txt").write_text(
    "MABI AUTO V0.1.30 - REMOVE POLICY / ERROR88 OCR DETECTION\n\n"
    "Base: V0.1.29 full stability hardening.\n"
    "Removed policy_shutdown and policy_error88 OCR targets from regular dungeon and Abyss.\n"
    "Removed all global/recovery policy OCR checks and DUNGEON_POLICY_SHUTDOWN_DETECTED handling.\n"
    "The game itself may close on those conditions; the bot no longer tries to detect them.\n"
    "V0.1.29 retry OCR+image, same-stage recovery loop cap, two-frame scene-skip, V0.1.28 screen-first recovery, Abyss, fishing, F10, logs and Telegram are preserved.\n",
    encoding="utf-8"
)

print("V0.1.30 applied: policy and ERROR88 OCR detection fully removed")
