#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0143_selected_entry_click_guards.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
detector_path = app / "dungeon" / "TargetDetector.cs"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
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

# 1) Physical separation of the two bottom buttons.
# Only the right-bottom region can ever be recognized/clicked as '입장하기'.
targets = json.loads(read(targets_path))
by_id = {t.get("Id"): t for t in targets}

for tid in ("enter_bottom", "enter_confirm"):
    if tid not in by_id:
        raise RuntimeError(f"missing target: {tid}")
    t = by_id[tid]
    t["Roi"] = {"X": 360, "Y": 900, "Width": 440, "Height": 100}
    t["Text"] = "입장하기"
    t["MaxEditDistance"] = 0
    t["OcrRetryAt2x"] = True

for tid, text_value in (("selected_ocr_strict", "선택됨"), ("challenge_confirm_strict", "도전")):
    if tid not in by_id:
        raise RuntimeError(f"missing target: {tid}")
    t = by_id[tid]
    t["Text"] = text_value
    t["MaxEditDistance"] = 0
    t["OcrRetryAt2x"] = True

write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# 2) Strict state words must return the exact word bounds, not a whole OCR line.
detector = read(detector_path)
old = '''            bool exactClickableEntry =
                id.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("enter_confirm", StringComparison.OrdinalIgnoreCase);

            if (exactDungeonSlot || exactClickableEntry)
                return await _ocr.FindCompactLabelAsync(frame, roi, t.Text, ct);
'''
new = '''            bool exactClickableEntry =
                id.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("enter_confirm", StringComparison.OrdinalIgnoreCase);

            bool exactDungeonEntryState =
                id.Equals("selected_ocr_strict", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("challenge_confirm_strict", StringComparison.OrdinalIgnoreCase);

            if (exactDungeonSlot || exactClickableEntry || exactDungeonEntryState)
                return await _ocr.FindCompactLabelAsync(frame, roi, t.Text, ct);
'''
detector = replace_once(detector, old, new, "exact selected/challenge OCR")
write(detector_path, detector)

# 3) Preserve the intended state machine:
#    selected -> click selected button only -> challenge -> click entry only.
engine = read(engine_path)

anchor = '''        const double VisualLeadMargin = 0.07;

        int challengeConsecutive = 0;
'''
replacement = '''        const double VisualLeadMargin = 0.07;

        // 800x1000 client coordinates.
        // Selected-state transition is allowed only inside the dungeon card.
        // Entry is allowed only in the right-bottom button region; the left-bottom
        // party-search button is therefore physically excluded from all entry clicks.
        var selectedClickSafe = new Rectangle(430, 640, 330, 230);
        var entryClickSafe = new Rectangle(360, 900, 440, 100);

        int challengeConsecutive = 0;
'''
engine = replace_once(engine, anchor, replacement, "safe click regions")

old_selected_click = '''                if (now - lastSelectedClick >= 1200)
                {
                    Log?.Invoke($"[도전 안전확인] 선택됨 확정 S={state.SelectedScore:0.000} C={state.ChallengeScore:0.000} -> 1회 클릭");
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _input.ClickClientPoint(_hwnd, state.ClickPoint);
                    lastSelectedClick = now;
                    await Task.Delay(Math.Max(650, _settings.ClickSettleMs), ct);
                }
'''
new_selected_click = '''                if (now - lastSelectedClick >= 1200)
                {
                    if (!selectedClickSafe.Contains(state.ClickPoint))
                    {
                        Log?.Invoke($"[도전 안전확인] 선택됨 검출 좌표가 카드 안전영역 밖 -> 클릭 안 함 @ {state.ClickPoint} safe={selectedClickSafe}");
                        await Task.Delay(ConfirmIntervalMs, ct);
                        continue;
                    }

                    Log?.Invoke($"[도전 안전확인] 선택됨 확정 -> 카드 안 선택됨 버튼만 1회 클릭 @ {state.ClickPoint} S={state.SelectedScore:0.000} C={state.ChallengeScore:0.000}");
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _input.ClickClientPoint(_hwnd, state.ClickPoint);
                    lastSelectedClick = now;
                    await Task.Delay(Math.Max(650, _settings.ClickSettleMs), ct);
                }
'''
engine = replace_once(engine, old_selected_click, new_selected_click, "selected safe click")

old_final = '''            if (finalState.State == 2 && enter.Found)
            {
                Log?.Invoke($"[도전 안전확인] 최종 도전 확인 성공 + 입장하기 확인 -> 입장 허용 (S={finalState.SelectedScore:0.000} C={finalState.ChallengeScore:0.000})");
                return;
            }
'''
new_final = '''            if (finalState.State == 2 && enter.Found)
            {
                if (!entryClickSafe.Contains(enter.Center))
                {
                    Log?.Invoke($"[도전 안전확인] 입장하기 검출 좌표가 오른쪽 하단 안전영역 밖 -> 입장 금지 @ {enter.Center} safe={entryClickSafe}");
                    challengeConsecutive = 0;
                    await Task.Delay(ConfirmIntervalMs, ct);
                    continue;
                }

                Log?.Invoke($"[도전 안전확인] 최종 도전 확인 성공 + 오른쪽 입장하기 확인 -> 입장 허용 @ {enter.Center} (S={finalState.SelectedScore:0.000} C={finalState.ChallengeScore:0.000})");
                return;
            }
'''
engine = replace_once(engine, old_final, new_final, "entry authorization safe region")

old_click_guard = '''                        if (step.Target.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase))
                        {
                            string exactEntry = FuzzyText.Normalize(found.ReadText ?? "");
                            if (!exactEntry.Equals(FuzzyText.Normalize("입장하기"), StringComparison.OrdinalIgnoreCase))
                            {
                                Log?.Invoke($"[던전 입장] 입장하기 정확 단어 확인 실패 -> 클릭 안 함 · OCR={found.ReadText} @ {found.Bounds}");
                                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                                continue;
                            }

                            Log?.Invoke($"[던전 입장] 입장하기 단어 자체 중앙 클릭 @ {found.Bounds} center={found.Center}");
                        }
'''
new_click_guard = '''                        if (step.Target.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase))
                        {
                            string exactEntry = FuzzyText.Normalize(found.ReadText ?? "");
                            var entryClickSafe = new Rectangle(360, 900, 440, 100);

                            if (!exactEntry.Equals(FuzzyText.Normalize("입장하기"), StringComparison.OrdinalIgnoreCase))
                            {
                                Log?.Invoke($"[던전 입장] 입장하기 정확 단어 확인 실패 -> 클릭 안 함 · OCR={found.ReadText} @ {found.Bounds}");
                                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                                continue;
                            }

                            if (!entryClickSafe.Contains(found.Center))
                            {
                                Log?.Invoke($"[던전 입장] 입장하기가 오른쪽 하단 안전영역 밖 -> 클릭 안 함 @ {found.Center} safe={entryClickSafe}");
                                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                                continue;
                            }

                            Log?.Invoke($"[던전 입장] 오른쪽 입장하기 단어 자체 중앙만 클릭 @ {found.Bounds} center={found.Center}");
                        }
'''
engine = replace_once(engine, old_click_guard, new_click_guard, "final entry no-party guard")
write(engine_path, engine)

# 4) Version bump only from V0.1.42 -> V0.1.43.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.42", "V0.1.43")
                   .replace("0.1.42.0", "0.1.43.0")
                   .replace("0.1.42", "0.1.43"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.43_SELECTED_ENTRY_GUARDS.txt").write_text(
    "MABI AUTO V0.1.43 - SELECTED / CHALLENGE / ENTRY CLICK GUARDS\n\n"
    "Keeps the intended dungeon flow: selected -> click the selected card button once -> challenge -> enter.\n"
    "Selected/challenge strict OCR now returns exact word bounds.\n"
    "A selected-state transition click is permitted only inside the dungeon-card safe rectangle.\n"
    "The bottom entry OCR ROI is restricted to the right side (X=360..799, Y=900..999), physically excluding the left party-search button.\n"
    "Entry authorization and the actual entry click both require the exact '입장하기' word center to be inside that right-bottom safe rectangle.\n"
    "No fallback coordinate is used. Any out-of-region detection is logged and ignored.\n"
    "V0.1.42 recognition navigation UI ('인식' + image icon) is preserved.\n",
    encoding="utf-8"
)

# 5) Structural verification.
targets_check = {t.get("Id"): t for t in json.loads(read(targets_path))}
for tid in ("enter_bottom", "enter_confirm"):
    t = targets_check[tid]
    expected = {"X": 360, "Y": 900, "Width": 440, "Height": 100}
    if t.get("Roi") != expected:
        raise RuntimeError(f"{tid} right-bottom ROI mismatch: {t.get('Roi')}")
    if t.get("Text") != "입장하기" or int(t.get("MaxEditDistance", -1)) != 0:
        raise RuntimeError(f"{tid} exact entry config mismatch")

for tid, expected_text in (("selected_ocr_strict", "선택됨"), ("challenge_confirm_strict", "도전")):
    t = targets_check[tid]
    if t.get("Text") != expected_text or int(t.get("MaxEditDistance", -1)) != 0:
        raise RuntimeError(f"{tid} exact-state config mismatch")

detector_check = read(detector_path)
engine_check = read(engine_path)
for marker in (
    "bool exactDungeonEntryState",
    'id.Equals("selected_ocr_strict"',
    'id.Equals("challenge_confirm_strict"',
):
    if marker not in detector_check:
        raise RuntimeError("strict state OCR marker missing: " + marker)

for marker in (
    "var selectedClickSafe = new Rectangle(430, 640, 330, 230);",
    "var entryClickSafe = new Rectangle(360, 900, 440, 100);",
    "선택됨 검출 좌표가 카드 안전영역 밖 -> 클릭 안 함",
    "선택됨 확정 -> 카드 안 선택됨 버튼만 1회 클릭",
    "입장하기 검출 좌표가 오른쪽 하단 안전영역 밖 -> 입장 금지",
    "오른쪽 입장하기 단어 자체 중앙만 클릭",
):
    if marker not in engine_check:
        raise RuntimeError("click guard marker missing: " + marker)

print("V0.1.43 patch applied: selected-card-only transition + right-entry-only click guard")
