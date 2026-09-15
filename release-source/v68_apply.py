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
        raise RuntimeError(f"v68 expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


# Require v67 as the exact base so the clear-screen transition fix stays intact.
v67_audit_path = root / "V67_ABYSS_CLEAR_TRANSITION_AUDIT.json"
if not v67_audit_path.is_file():
    raise RuntimeError("v67 audit missing; v68 must be applied on v67 source")
v67_audit = json.loads(v67_audit_path.read_text(encoding="utf-8-sig"))
if v67_audit.get("version") != "v67":
    raise RuntimeError("unexpected base audit version")

# Version bump only; no UI layout changes.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v67";',
                 'public const string CurrentVersion = "v68";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "68.0.0"), ("AssemblyVersion", "68.0.0.0"), ("FileVersion", "68.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v68 project version tag missing: {name}")
write(project, s)

ui_path = app / "MainForm.ReferenceUI.cs"
s = read(ui_path)
s = replace_once(s, 'TextAt(g, "v67.0.0 · UI", new(252, 22, 150, 35), 15);',
                 'TextAt(g, "v68.0.0 · UI", new(252, 22, 150, 35), 15);', 'reference UI version')
write(ui_path, s)

# Verify the exact targets used by the end-of-dungeon recovery flow.
targets_path = app / "abyss" / "config" / "targets.json"
targets = json.loads(targets_path.read_text(encoding="utf-8-sig"))
by_id = {t.get("Id"): t for t in targets}
for target_id in ("abyss_touch_screen", "abyss_dungeon_clear_visual", "abyss_treasure_chest", "abyss_exit", "abyss_menu", "abyss_popup_close"):
    if target_id not in by_id:
        raise RuntimeError(f"v68 required Abyss target missing: {target_id}")
for target_id in ("abyss_touch_screen", "abyss_dungeon_clear_visual"):
    t = by_id[target_id]
    if str(t.get("Kind", "")).lower() != "template" or not t.get("TemplatePath"):
        raise RuntimeError(f"v68 requires image-only clear target: {target_id}")

engine_path = app / "dungeon" / "ScenarioEngine.cs"
s = read(engine_path)

old_recovery = '''    private async Task<bool> TrySmartRecoveryAsync(CancellationToken ct)\n    {\n        bool abyss = string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);\n        if (!abyss)\n        {\n            try\n            {\n                Log?.Invoke("[자동복구] ESC 입력 후 현재 판 재시작");\n                _hwnd = await ResolveRequiredGameWindowAsync(ct);\n                NativeMethods.SetForegroundWindow(_hwnd);\n                _input.TapScanCode(0x01); // ESC scan code\n                await Task.Delay(900, ct);\n                return true;\n            }\n            catch { return false; }\n        }\n\n        for (int attempt = 1; attempt <= 3; attempt++)\n        {\n            ct.ThrowIfCancellationRequested();\n            try\n            {\n                using var frame = await CaptureGameWindowAsync(ct);\n                var menu = await _detector.DetectAsync("abyss_menu", frame, ct);\n                if (menu.Found)\n                {\n                    Log?.Invoke("[자동복구] 홈 화면 메뉴 아이콘 확인 완료");\n                    return true;\n                }\n            }\n            catch (Exception ex)\n            {\n                Log?.Invoke($"[자동복구] 홈 화면 확인 재시도: {ex.Message}");\n            }\n\n            try\n            {\n                _hwnd = await ResolveRequiredGameWindowAsync(ct);\n                NativeMethods.SetForegroundWindow(_hwnd);\n                _input.TapScanCode(0x01); // ESC\n                Log?.Invoke($"[자동복구] ESC 입력 {attempt}/3");\n            }\n            catch (Exception ex)\n            {\n                Log?.Invoke($"[자동복구] ESC 입력 실패: {ex.Message}");\n            }\n            await Task.Delay(900, ct);\n        }\n        return false;\n    }'''

new_recovery = '''    private async Task<bool> TrySmartRecoveryAsync(CancellationToken ct)\n    {\n        bool abyss = string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);\n        if (abyss)\n            return await TryAbyssInternalRecoveryAsync(ct);\n\n        // Non-Abyss recovery remains unchanged.\n        try\n        {\n            Log?.Invoke("[자동복구] ESC 입력 후 현재 판 재시작");\n            _hwnd = await ResolveRequiredGameWindowAsync(ct);\n            NativeMethods.SetForegroundWindow(_hwnd);\n            _input.TapScanCode(0x01); // ESC scan code\n            await Task.Delay(900, ct);\n            return true;\n        }\n        catch { return false; }\n    }\n\n    private async Task<bool> TryAbyssInternalRecoveryAsync(CancellationToken ct)\n    {\n        // Finish the current Abyss result flow instead of trying ESC/home directly:\n        // result/touch screen -> treasure detection -> exit click -> outside menu confirmation.\n        var sw = Stopwatch.StartNew();\n        const int RecoveryTimeoutSeconds = 300;\n        long lastTouchClick = long.MinValue;\n        long lastExitClick = long.MinValue;\n        long lastPopupClick = long.MinValue;\n        int touchClicks = 0;\n        int exitClicks = 0;\n        bool treasureSeen = false;\n\n        Log?.Invoke("[어비스 자동복구] 던전 내부 복구 시작: 화면 터치 -> 보물상자 확인 -> 나가기 -> 던전 밖 확인");\n\n        while (sw.Elapsed < TimeSpan.FromSeconds(RecoveryTimeoutSeconds))\n        {\n            ct.ThrowIfCancellationRequested();\n            using var frame = await CaptureGameWindowAsync(ct);\n            long now = Environment.TickCount64;\n\n            // Recovery is complete only after the normal outside/home menu is visible.\n            var home = await _detector.DetectAsync("abyss_menu", frame, ct);\n            if (home.Found)\n            {\n                Log?.Invoke("[어비스 자동복구] 던전 밖 메뉴 확인 완료 -> 처음부터 재시작");\n                return true;\n            }\n\n            // Keep the v65 template-only popup guard available during recovery.\n            if (now - lastPopupClick >= 2500)\n            {\n                var popupClose = await _detector.DetectAsync("abyss_popup_close", frame, ct);\n                if (popupClose.Found)\n                {\n                    _hwnd = await ResolveRequiredGameWindowAsync(ct);\n                    NativeMethods.SetForegroundWindow(_hwnd);\n                    Log?.Invoke($"[어비스 자동복구] 팝업 닫기 이미지 확인 -> 클릭 @ {popupClose.Bounds}");\n                    _input.ClickClientPoint(_hwnd, popupClose.Center);\n                    lastPopupClick = now;\n                    await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);\n                    continue;\n                }\n            }\n\n            // On the result screen, click only the real touch prompt. Never click the clear-title match.\n            var clearVisual = await DetectAbyssClearVisualAsync(frame, ct);\n            if (clearVisual.Found)\n            {\n                var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);\n                if (touch.Found && now - lastTouchClick >= 1800)\n                {\n                    _hwnd = await ResolveRequiredGameWindowAsync(ct);\n                    NativeMethods.SetForegroundWindow(_hwnd);\n                    touchClicks++;\n                    Log?.Invoke($"[어비스 자동복구] 화면 터치 {touchClicks}회 -> 터치 문구 위치 클릭 @ {touch.Bounds}");\n                    _input.ClickClientPoint(_hwnd, touch.Center);\n                    lastTouchClick = now;\n                    await Task.Delay(Math.Max(900, _settings.ClickSettleMs), ct);\n                    continue;\n                }\n\n                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);\n                continue;\n            }\n\n            // Step 6 in the normal scenario is detection-only. Do not click the chest.\n            if (!treasureSeen)\n            {\n                var treasure = await _detector.DetectAsync("abyss_treasure_chest", frame, ct);\n                if (treasure.Found)\n                {\n                    treasureSeen = true;\n                    Log?.Invoke($"[어비스 자동복구] 보물상자 확인 완료 @ {treasure.Bounds} -> 나가기 탐색");\n                }\n            }\n\n            // If recovery starts after the normal flow already passed the chest step, the exit may\n            // already be visible. In that case it is safe to resume directly from the exit screen.\n            if (now - lastExitClick >= 2200)\n            {\n                var exit = await _detector.DetectAsync("abyss_exit", frame, ct);\n                if (exit.Found)\n                {\n                    _hwnd = await ResolveRequiredGameWindowAsync(ct);\n                    NativeMethods.SetForegroundWindow(_hwnd);\n                    exitClicks++;\n                    Log?.Invoke($"[어비스 자동복구] 나가기 확인 {exitClicks}회 -> 클릭 @ {exit.Bounds}");\n                    _input.ClickClientPoint(_hwnd, exit.Center);\n                    lastExitClick = now;\n                    await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);\n                    continue;\n                }\n            }\n\n            await Task.Delay(Math.Max(300, _settings.PollIntervalMs), ct);\n        }\n\n        Log?.Invoke($"[어비스 자동복구] {RecoveryTimeoutSeconds}초 동안 던전 밖 복귀를 완료하지 못함");\n        return false;\n    }'''

s = replace_once(s, old_recovery, new_recovery, "Abyss Smart Recovery method")
write(engine_path, s)

changes_path = root / "CHANGES_v68_ABYSS_INTERNAL_RECOVERY.txt"
changes_path.write_text(
    "MABI AUTO v68\n"
    "- Abyss Smart Recovery no longer uses ESC as its recovery strategy.\n"
    "- On an Abyss timeout/error, recovery resumes the visible end-of-dungeon state.\n"
    "- Recovery sequence: clear/touch screen -> treasure detection -> exit click -> outside menu confirmation.\n"
    "- Clear-title recognition is never clicked; only the actual touch-screen prompt image is clicked.\n"
    "- Treasure remains detection-only, matching the normal step-6 behavior; recovery never clicks the chest.\n"
    "- If the normal flow already passed treasure, recovery may continue directly from a visible exit button.\n"
    "- Recovery succeeds only when the outside/home abyss_menu image is detected, then the scenario restarts from the beginning.\n"
    "- Recovery timeout is 300 seconds; after failure the existing retry-count/safe-stop policy remains in force.\n"
    "- v67 clear transition verification, v65 popup-close guard, auto-stop UI, other UI/layouts and window sizing are unchanged.\n",
    encoding="utf-8",
)

modified = [update, project, ui_path, engine_path, changes_path]
audit = {
    "base": "v67",
    "version": "v68",
    "purpose": "Abyss in-dungeon recovery through touch, treasure detection and exit",
    "abyss_recovery": {
        "esc_used": False,
        "sequence": ["clear/touch screen", "abyss_treasure_chest detection", "abyss_exit click", "abyss_menu outside confirmation"],
        "clear_title_click_allowed": False,
        "touch_prompt_click_only": True,
        "treasure_clicked": False,
        "recovery_timeout_seconds": 300,
        "success_requires_outside_menu": True,
        "game_restart_added": False,
    },
    "preserved": [
        "v67 clear-screen transition verification",
        "v66 HOME auto-stop UI/settings",
        "other windows and layouts",
        "v65 abyss_popup_close template-only guard",
        "scene_skip", "treasure chest target/config", "normal exit", "retry-count/safe-stop policy",
        "administrator elevation", "exact 800x1000 sizing", "dual-monitor handling"
    ],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V68_ABYSS_INTERNAL_RECOVERY_AUDIT.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("v68 applied: Abyss internal recovery = touch -> treasure detect -> exit -> outside confirmation")
