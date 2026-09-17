#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0127_dungeon_update_20260917.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
targets_path = app / "dungeon" / "config" / "targets.json"
engine_path = app / "dungeon" / "ScenarioEngine.cs"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


targets = json.loads(read(targets_path))
by_id = {t.get("Id"): t for t in targets}
required_ids = [
    "challenge_confirm_strict", "challenge", "challenge_visual",
    "selected", "selected_ocr_strict", "selected_red_visual",
    "enter_bottom", "enter_confirm", "retry", "scene_skip"
]
for tid in required_ids:
    if tid not in by_id:
        raise RuntimeError(f"required target missing: {tid}")

# 2026-09-17 UI update: keep the same semantics, but make the entry-state OCR
# tolerant of the shifted/new purple UI. The visual templates remain as fallback.
state_roi = {"X": 390, "Y": 635, "Width": 370, "Height": 215}
for tid in [
    "challenge_confirm_strict", "challenge", "challenge_visual",
    "selected", "selected_ocr_strict", "selected_red_visual"
]:
    by_id[tid]["Roi"] = dict(state_roi)

by_id["challenge_confirm_strict"]["MaxEditDistance"] = 1
by_id["challenge_confirm_strict"]["OcrRetryAt2x"] = True
by_id["challenge"]["MaxEditDistance"] = 2
by_id["challenge"]["OcrRetryAt2x"] = True
by_id["selected"]["MaxEditDistance"] = 2
by_id["selected"]["OcrRetryAt2x"] = True
by_id["selected_ocr_strict"]["MaxEditDistance"] = 1
by_id["selected_ocr_strict"]["OcrRetryAt2x"] = True

# The bottom entry button moved slightly in the updated UI. Search a wider bottom band.
enter_roi = {"X": 60, "Y": 825, "Width": 680, "Height": 175}
for tid in ["enter_bottom", "enter_confirm"]:
    by_id[tid]["Roi"] = dict(enter_roi)
    by_id[tid]["MaxEditDistance"] = 1
    by_id[tid]["OcrRetryAt2x"] = True

# Updated clear screen shows '다시 하기' with a visible space. Keep edit distance 2
# so the previous compact '다시하기' rendering also remains compatible.
retry = by_id["retry"]
retry["Kind"] = "ocr"
retry["Roi"] = {"X": 180, "Y": 830, "Width": 440, "Height": 170}
retry["Text"] = "다시 하기"
retry["MaxEditDistance"] = 2
retry["OcrRetryAt2x"] = True

write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# When ESC opens the main menu instead of revealing a known dungeon screen, close it
# once and classify again before consuming another Smart Recovery attempt.
engine = read(engine_path)
old = '''            int? resumeStep = await DetectKnownDungeonRecoveryStepAsync(ct);
            if (!resumeStep.HasValue)
            {
                Log?.Invoke("[던전 자동복구] ESC 후 8초 동안 알고 있는 단계 화면을 찾지 못함");
                return false;
            }

            _resumeStepIndex = resumeStep.Value;
            return true;
'''
new = '''            int? resumeStep = await DetectKnownDungeonRecoveryStepAsync(ct);
            if (!resumeStep.HasValue)
            {
                // DUNGEON_UPDATE_20260917_MENU_FALLBACK
                // After the 2026-09-17 update ESC can open the main menu on some dungeon screens.
                // A second ESC closes that menu; then classify the restored dungeon screen again.
                Log?.Invoke("[던전 자동복구] 첫 ESC 후 알려진 단계 미확인 -> 메뉴 가능성, ESC 1회 더 입력 후 재판별");
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                _input.TapScanCode(0x01);
                await Task.Delay(700, ct);
                resumeStep = await DetectKnownDungeonRecoveryStepAsync(ct);
            }

            if (!resumeStep.HasValue)
            {
                Log?.Invoke("[던전 자동복구] ESC 재확인 후에도 알고 있는 단계 화면을 찾지 못함");
                return false;
            }

            _resumeStepIndex = resumeStep.Value;
            return true;
'''
if old not in engine:
    raise RuntimeError("V0.1.26 recovery block not found")
engine = engine.replace(old, new, 1)

required_markers = [
    "DUNGEON_CHALLENGE_DISAMBIGUATION_V5",
    "DetectKnownDungeonRecoveryStepAsync",
    "DUNGEON_UPDATE_20260917_MENU_FALLBACK",
    "다시하기 확인 ->",
    "던전 밖 HUD 3/4 이상 확인",
    "어비스 클릭 검증 실패",
]
for marker in required_markers:
    if marker not in engine:
        raise RuntimeError(f"required marker missing after patch: {marker}")
write(engine_path, engine)

# Runtime version bump only.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.26", "V0.1.27")
                   .replace("0.1.26.0", "0.1.27.0")
                   .replace("0.1.26", "0.1.27"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.27_DUNGEON_UPDATE_20260917.txt").write_text(
    "MABI AUTO V0.1.27 - DUNGEON UPDATE 2026-09-17\n\n"
    "Base: V0.1.26 with dungeon scene-skip restored.\n"
    "Widened selected/challenge OCR search area for the updated purple dungeon UI.\n"
    "Widened enter-bottom OCR search area while preserving selected -> challenge -> enter semantics.\n"
    "Updated retry OCR for both '다시 하기' and the previous compact '다시하기' rendering.\n"
    "Smart Recovery now retries classification after one extra ESC when the first ESC opens the main menu.\n"
    "Scene-skip monitor, Abyss recovery, fishing logic, and V0.1.24 selected/challenge disambiguation are preserved.\n",
    encoding="utf-8"
)

print("V0.1.27 applied: 2026-09-17 dungeon UI compatibility + recovery menu fallback")
