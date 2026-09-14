#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"v67 expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


# Require the published v66 source as the base.
v66_audit_path = root / "V66_ABYSS_CLEAR_AUTOSTOP_AUDIT.json"
if not v66_audit_path.is_file():
    raise RuntimeError("v66 audit missing; v67 must be applied on v66 source")
v66_audit = json.loads(v66_audit_path.read_text(encoding="utf-8-sig"))
if v66_audit.get("version") != "v66":
    raise RuntimeError("unexpected base audit version")

# Version bump only; keep v66 auto-stop UI and all unrelated runtime logic intact.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v66";',
                 'public const string CurrentVersion = "v67";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "67.0.0"), ("AssemblyVersion", "67.0.0.0"), ("FileVersion", "67.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v67 project version tag missing: {name}")
write(project, s)

ui_path = app / "MainForm.ReferenceUI.cs"
s = read(ui_path)
s = replace_once(s, 'TextAt(g, "v66.0.0 · UI", new(252, 22, 150, 35), 15);',
                 'TextAt(g, "v67.0.0 · UI", new(252, 22, 150, 35), 15);', 'reference UI version')
write(ui_path, s)

# Verify v66 clear targets remain image-only. No target/template thresholds are changed here.
targets_path = app / "abyss" / "config" / "targets.json"
targets = json.loads(targets_path.read_text(encoding="utf-8-sig"))
by_id = {t.get("Id"): t for t in targets}
for target_id in ("abyss_touch_screen", "abyss_dungeon_clear_visual"):
    t = by_id.get(target_id)
    if not t or str(t.get("Kind", "")).lower() != "template" or not t.get("TemplatePath"):
        raise RuntimeError(f"v67 requires image-only target: {target_id}")
if by_id["abyss_touch_screen"].get("Text"):
    raise RuntimeError("v67 refuses OCR fallback on abyss_touch_screen")

engine_path = app / "dungeon" / "ScenarioEngine.cs"
s = read(engine_path)
# Keep the two-image OR + two-consecutive clear recognition from v66. Only the transition/click
# logic is replaced: never click the clear-title match; click only the touch prompt, then require
# the clear screen to be absent for three consecutive captures before step 6 may start.
s = s.replace("// v66: image-only multi-scale confirmation. Rank S and OCR are not used.",
              "// v67: image-only multi-scale confirmation. Rank S/OCR are not used; transition is separately verified.", 1)

old_methods = '''    private async Task<DetectionResult> DetectAbyssClearVisualAsync(Bitmap frame, CancellationToken ct)\n    {\n        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);\n        if (clearTitle.Found) return clearTitle;\n        return await _detector.DetectAsync("abyss_touch_screen", frame, ct);\n    }\n\n    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)\n    {\n        Log?.Invoke("[어비스] 클리어 화면 이미지 2회 확인 완료 -> 1차 클릭");\n        _input.ClickClientPoint(_hwnd, firstDetection.Center);\n        await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);\n\n        using (var afterFirst = await CaptureGameWindowAsync(ct))\n        {\n            var clearStillVisible = await DetectAbyssClearVisualAsync(afterFirst, ct);\n            if (!clearStillVisible.Found)\n            {\n                Log?.Invoke("[어비스] 1차 클릭 후 클리어 화면 전환 확인");\n                return;\n            }\n\n            Log?.Invoke("[어비스] 클리어 화면 유지 -> 2차 클릭");\n            _input.ClickClientPoint(_hwnd, clearStillVisible.Center);\n        }\n\n        await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);\n\n        using var afterSecond = await CaptureGameWindowAsync(ct);\n        var clearAfterSecond = await DetectAbyssClearVisualAsync(afterSecond, ct);\n        if (clearAfterSecond.Found)\n        {\n            Log?.Invoke("[어비스] 경고: 2회 클릭 후에도 클리어 화면 이미지가 남아 있음");\n            throw new TimeoutException("어비스 클리어 화면이 2회 클릭 후에도 넘어가지 않았습니다.");\n        }\n\n        Log?.Invoke("[어비스] 2차 클릭 후 클리어 화면 전환 확인");\n    }'''

new_methods = '''    private async Task<DetectionResult> DetectAbyssClearVisualAsync(Bitmap frame, CancellationToken ct)\n    {\n        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);\n        if (clearTitle.Found) return clearTitle;\n        return await _detector.DetectAsync("abyss_touch_screen", frame, ct);\n    }\n\n    private async Task<DetectionResult> WaitForAbyssTouchPromptAsync(CancellationToken ct)\n    {\n        var sw = Stopwatch.StartNew();\n        int clearGoneConsecutive = 0;\n\n        while (sw.Elapsed < TimeSpan.FromSeconds(20))\n        {\n            ct.ThrowIfCancellationRequested();\n            using var frame = await CaptureGameWindowAsync(ct);\n\n            var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);\n            if (touch.Found)\n            {\n                Log?.Invoke($"[어비스] 화면 터치 문구 확인 -> 해당 위치 클릭 준비 @ {touch.Bounds}");\n                return touch;\n            }\n\n            var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);\n            if (!clearTitle.Found)\n            {\n                clearGoneConsecutive++;\n                if (clearGoneConsecutive >= 3)\n                {\n                    Log?.Invoke("[어비스] 터치 문구 대기 중 클리어 화면이 이미 3회 연속 사라짐 -> 전환 완료로 처리");\n                    return DetectionResult.NotFound;\n                }\n            }\n            else\n            {\n                clearGoneConsecutive = 0;\n            }\n\n            await Task.Delay(Math.Max(200, _settings.PollIntervalMs), ct);\n        }\n\n        throw new TimeoutException("어비스 클리어 화면은 감지했지만 '화면을 터치해 주세요' 이미지를 20초 안에 찾지 못했습니다.");\n    }\n\n    private async Task WaitForAbyssClearScreenGoneAsync(CancellationToken ct)\n    {\n        var sw = Stopwatch.StartNew();\n        int goneConsecutive = 0;\n        int retryClicks = 0;\n\n        while (sw.Elapsed < TimeSpan.FromSeconds(20))\n        {\n            ct.ThrowIfCancellationRequested();\n            using var frame = await CaptureGameWindowAsync(ct);\n            var clear = await DetectAbyssClearVisualAsync(frame, ct);\n\n            if (!clear.Found)\n            {\n                goneConsecutive++;\n                Log?.Invoke($"[어비스] 클리어 화면 사라짐 확인 {goneConsecutive}/3");\n                if (goneConsecutive >= 3)\n                {\n                    Log?.Invoke("[어비스] 클리어 화면 3회 연속 사라짐 확인 -> 보물상자 단계 진행");\n                    return;\n                }\n            }\n            else\n            {\n                goneConsecutive = 0;\n\n                // If the result screen stayed up, retry once, but still click only the\n                // actual touch-prompt image. Never click the clear-title match.\n                if (retryClicks < 1 && sw.Elapsed >= TimeSpan.FromSeconds(2))\n                {\n                    var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);\n                    if (touch.Found)\n                    {\n                        _hwnd = await ResolveRequiredGameWindowAsync(ct);\n                        NativeMethods.SetForegroundWindow(_hwnd);\n                        Log?.Invoke($"[어비스] 클리어 화면 유지 -> 터치 문구 위치 1회 재클릭 @ {touch.Bounds}");\n                        _input.ClickClientPoint(_hwnd, touch.Center);\n                        retryClicks++;\n                        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);\n                        continue;\n                    }\n                }\n            }\n\n            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);\n        }\n\n        throw new TimeoutException("어비스 클리어 화면 클릭 후 화면 전환을 20초 안에 확정하지 못했습니다. 보물상자 단계로 넘어가지 않습니다.");\n    }\n\n    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)\n    {\n        _ = firstDetection; // Recognition proves clear; it is never used as a click position in v67.\n        Log?.Invoke("[어비스] 클리어 이미지 2회 확인 완료 -> 터치 문구 이미지를 별도로 찾음");\n\n        var touch = await WaitForAbyssTouchPromptAsync(ct);\n        if (!touch.Found)\n            return; // The clear screen already disappeared stably while waiting.\n\n        _hwnd = await ResolveRequiredGameWindowAsync(ct);\n        NativeMethods.SetForegroundWindow(_hwnd);\n        Log?.Invoke($"[어비스] '화면을 터치해 주세요' 위치 클릭 @ {touch.Bounds}");\n        _input.ClickClientPoint(_hwnd, touch.Center);\n        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);\n\n        // Do not start the 120-second treasure timer after a single missed frame.\n        // The result screen must be absent in three consecutive captures first.\n        await WaitForAbyssClearScreenGoneAsync(ct);\n    }'''

s = replace_once(s, old_methods, new_methods, "Abyss clear transition methods")
write(engine_path, s)

changes_path = root / "CHANGES_v67_ABYSS_CLEAR_TRANSITION.txt"
changes_path.write_text(
    "MABI AUTO v67\n"
    "- Abyss clear recognition remains v66 image-only multi-scale: dungeon-clear OR touch-screen, 2 consecutive detections.\n"
    "- The detected dungeon-clear title is never used as a click coordinate.\n"
    "- After clear recognition, the bot separately finds and clicks only the '화면을 터치해 주세요' image.\n"
    "- The clear/result screen must be absent for 3 consecutive captures before the treasure-chest step starts.\n"
    "- If the result screen remains, one retry click is allowed only when the touch-prompt image itself is found.\n"
    "- If transition cannot be confirmed within 20 seconds, the bot raises recovery immediately instead of entering the 120-second treasure wait.\n"
    "- Auto-stop UI, other windows/layouts, popup-close guard, scene-skip, treasure detection, retry/recovery, admin and window sizing are unchanged.\n",
    encoding="utf-8",
)

modified = [update, project, ui_path, engine_path, changes_path]
audit = {
    "base": "v66",
    "version": "v67",
    "purpose": "Abyss clear-screen click/transition verification before treasure wait",
    "clear_recognition_preserved": {
        "alternatives": ["abyss_dungeon_clear_visual", "abyss_touch_screen"],
        "consecutive_required": 2,
        "image_only": True,
        "rank_s_used": False,
        "ocr_used": False,
    },
    "transition_fix": {
        "click_target": "abyss_touch_screen only",
        "clear_title_used_as_click_target": False,
        "gone_consecutive_required": 3,
        "transition_timeout_seconds": 20,
        "max_touch_retry_clicks": 1,
        "treasure_step_starts_only_after_transition_confirmed": True,
    },
    "preserved": [
        "v66 HOME auto-stop UI/settings",
        "other windows and layouts",
        "v65 abyss_popup_close template-only guard",
        "scene_skip", "treasure chest target/config", "normal exit", "Smart Recovery", "retry",
        "administrator elevation", "exact 800x1000 sizing", "dual-monitor handling"
    ],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V67_ABYSS_CLEAR_TRANSITION_AUDIT.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("v67 applied: touch-prompt-only click + 3-frame clear transition confirmation")
