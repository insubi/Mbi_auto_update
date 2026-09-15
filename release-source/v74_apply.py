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
        raise RuntimeError(f"V0.1.1 expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


# V0.1.1 is a bug-fix patch applied directly on the V0.1/v73 bridge source.
base_audit_path = root / "V0_1_RELEASE_AUDIT.json"
if not base_audit_path.is_file():
    raise RuntimeError("V0.1 audit missing; v74/V0.1.1 must be applied on published V0.1 source")
base_audit = json.loads(base_audit_path.read_text(encoding="utf-8-sig"))
if base_audit.get("version") != "V0.1" or base_audit.get("technical_bridge_tag") != "v73":
    raise RuntimeError("unexpected V0.1 base audit")

# Preserve recognition configuration/template bytes. This patch changes only the
# completion decision and recovery mechanics, not image assets, ROIs or thresholds.
targets_path = app / "abyss" / "config" / "targets.json"
targets_sha_before = hashlib.sha256(targets_path.read_bytes()).hexdigest()
targets = json.loads(targets_path.read_text(encoding="utf-8-sig"))
by_id = {t.get("Id"): t for t in targets}
clear_template_hashes = {}
for target_id in ("abyss_dungeon_clear_visual", "abyss_touch_screen"):
    target = by_id.get(target_id)
    if not target or str(target.get("Kind", "")).lower() != "template" or not target.get("TemplatePath"):
        raise RuntimeError(f"V0.1.1 requires image-only target: {target_id}")
    template_path = app / "abyss" / target["TemplatePath"]
    if not template_path.is_file():
        raise RuntimeError(f"clear template missing: {template_path}")
    clear_template_hashes[template_path.relative_to(root).as_posix()] = hashlib.sha256(template_path.read_bytes()).hexdigest()

# Public semantic patch version.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "V0.1";',
                 'public const string CurrentVersion = "V0.1.1";', 'UpdateManager public version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "0.1.1"), ("AssemblyVersion", "0.1.1.0"), ("FileVersion", "0.1.1.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"V0.1.1 project version tag missing: {name}")
write(project, s)

engine_path = app / "dungeon" / "ScenarioEngine.cs"
s = read(engine_path)

# Old initial clear decision was OR: clear title OR touch prompt. A single loose match
# during live combat could therefore move to step 6. Keep the OR helper only for
# post-click transition tracking, but require BOTH result-screen visuals for the initial
# completion decision.
anchor = '''    private async Task<DetectionResult> DetectAbyssClearVisualAsync(Bitmap frame, CancellationToken ct)\n    {\n        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);\n        if (clearTitle.Found) return clearTitle;\n        return await _detector.DetectAsync("abyss_touch_screen", frame, ct);\n    }'''
strict_plus_anchor = '''    private async Task<DetectionResult> DetectAbyssConfirmedClearAsync(Bitmap frame, CancellationToken ct)\n    {\n        // V0.1.1 false-positive guard: live combat is never considered complete from\n        // one loose match. The real result screen contains BOTH independent visuals.\n        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);\n        if (!clearTitle.Found) return DetectionResult.NotFound;\n\n        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);\n        if (!touch.Found) return DetectionResult.NotFound;\n\n        return touch;\n    }\n\n    private async Task<DetectionResult> DetectAbyssClearVisualAsync(Bitmap frame, CancellationToken ct)\n    {\n        // After a confirmed result screen, one visual can disappear before the other\n        // during transition. OR detection is therefore retained only for transition tracking.\n        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);\n        if (clearTitle.Found) return clearTitle;\n        return await _detector.DetectAsync("abyss_touch_screen", frame, ct);\n    }'''
s = replace_once(s, anchor, strict_plus_anchor, "strict Abyss clear helper")

# Initial completion detection: BOTH images in the same frame, 3 consecutive frames.
s = replace_once(s,
                 '                found = await DetectAbyssClearVisualAsync(frame, ct);',
                 '                found = await DetectAbyssConfirmedClearAsync(frame, ct);',
                 'initial Abyss completion detector')
s = replace_once(s,
                 '                    Log?.Invoke($"[어비스] 클리어 이미지 연속 확인 {abyssClearConsecutive}/2");',
                 '                    Log?.Invoke($"[어비스] 클리어 화면 동시 이미지 연속 확인 {abyssClearConsecutive}/3");',
                 'Abyss completion confirmation log')
s = replace_once(s,
                 '                    if (abyssClearConsecutive < 2)',
                 '                    if (abyssClearConsecutive < 3)',
                 'Abyss completion consecutive threshold')

# Smart Recovery bug fix #1: it must use the same strict clear-state decision so a
# combat false-positive cannot trap recovery in the clear-screen branch.
s = replace_once(s,
                 '            var clearVisual = await DetectAbyssClearVisualAsync(frame, ct);',
                 '            var clearVisual = await DetectAbyssConfirmedClearAsync(frame, ct);',
                 'Abyss recovery clear-state detector')

# Smart Recovery bug fix #2: cooldown timestamps were initialized to long.MinValue.
# Environment.TickCount64 - long.MinValue overflows signed Int64, making the first
# cooldown test false and preventing the first touch/exit/popup click. Start at zero.
s = replace_once(s,
                 '        long lastTouchClick = long.MinValue;\n        long lastExitClick = long.MinValue;\n        long lastPopupClick = long.MinValue;',
                 '        long lastTouchClick = 0;\n        long lastExitClick = 0;\n        long lastPopupClick = 0;',
                 'Smart Recovery cooldown timestamp initialization')

# Make recovery state visible in logs while combat is still in progress. No input is
# sent on an unknown/live-combat frame; recovery simply waits for a real clear screen.
s = replace_once(s,
                 '        bool treasureSeen = false;\n\n        Log?.Invoke("[어비스 자동복구] 던전 내부 복구 시작: 화면 터치 -> 보물상자 확인 -> 나가기 -> 던전 밖 확인");',
                 '        bool treasureSeen = false;\n        long lastWaitingLog = 0;\n\n        Log?.Invoke("[어비스 자동복구] 던전 내부 복구 시작: 전투 중이면 실제 클리어 화면까지 대기 -> 화면 터치 -> 보물상자 확인 -> 나가기 -> 던전 밖 확인");',
                 'Smart Recovery waiting-state log initialization')
old_tail = '''            await Task.Delay(Math.Max(300, _settings.PollIntervalMs), ct);\n        }\n\n        Log?.Invoke($"[어비스 자동복구] {RecoveryTimeoutSeconds}초 동안 던전 밖 복귀를 완료하지 못함");'''
new_tail = '''            if (now - lastWaitingLog >= 15000)\n            {\n                Log?.Invoke("[어비스 자동복구] 종료 화면 미확인 -> 전투/진행 화면으로 보고 실제 클리어까지 대기 중");\n                lastWaitingLog = now;\n            }\n\n            await Task.Delay(Math.Max(300, _settings.PollIntervalMs), ct);\n        }\n\n        Log?.Invoke($"[어비스 자동복구] {RecoveryTimeoutSeconds}초 동안 던전 밖 복귀를 완료하지 못함");'''
s = replace_once(s, old_tail, new_tail, "Smart Recovery waiting heartbeat")
write(engine_path, s)

# Recognition configuration/templates must remain byte-for-byte unchanged.
if hashlib.sha256(targets_path.read_bytes()).hexdigest() != targets_sha_before:
    raise RuntimeError("V0.1.1 unexpectedly changed abyss targets.json")
for rel, expected in clear_template_hashes.items():
    if hashlib.sha256((root / rel).read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"V0.1.1 unexpectedly changed clear template: {rel}")

preserved_preview_hashes = dict(base_audit.get("preserved_preview_hashes", {}))
for rel, expected in preserved_preview_hashes.items():
    p = root / rel
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"V0.1.1 must preserve approved Abyss preview: {rel}")

changes_path = root / "CHANGES_V0.1.1_ABYSS_CLEAR_GUARD.txt"
changes_path.write_text(
    "MABI AUTO V0.1.1\n"
    "- Fix: live Abyss combat can no longer be declared complete from one template match.\n"
    "- Initial completion now requires BOTH dungeon-clear and touch-screen images in the SAME frame, 3 consecutive frames.\n"
    "- OCR and S-rank recognition remain unused for Abyss clear detection.\n"
    "- Existing clear templates, ROIs, thresholds and scales are unchanged.\n"
    "- Smart Recovery uses the same strict confirmed-clear state, so combat false positives do not trap recovery.\n"
    "- Smart Recovery first-click bug fixed: cooldown timestamps no longer start at long.MinValue (signed-overflow issue).\n"
    "- Recovery now logs every 15 seconds while it is safely waiting on a live combat/progress screen.\n"
    "- V0.1 HOME UI, auto-stop, Telegram, scenic dungeon previews and unrelated runtime behavior are unchanged.\n",
    encoding="utf-8",
)

modified = [update, project, engine_path, changes_path]
audit = {
    "base_public_version": "V0.1",
    "technical_bridge_base": "v73",
    "technical_bridge_tag": "v74",
    "version": "V0.1.1",
    "purpose": "Abyss false-completion guard and Smart Recovery first-action fix",
    "clear_detection": {
        "same_frame_required": ["abyss_dungeon_clear_visual", "abyss_touch_screen"],
        "consecutive_frames": 3,
        "ocr_used": False,
        "rank_s_used": False,
        "templates_or_thresholds_changed": False,
    },
    "smart_recovery": {
        "strict_clear_state": True,
        "cooldown_initialization": "0 instead of long.MinValue",
        "signed_overflow_first_click_bug_fixed": True,
        "waiting_heartbeat_seconds": 15,
        "recovery_sequence_preserved": ["confirmed clear/touch", "treasure detection", "exit click", "outside menu confirmation"],
    },
    "targets_json_sha256": targets_sha_before,
    "clear_template_hashes": clear_template_hashes,
    "preserved_preview_hashes": preserved_preview_hashes,
    "preserved": [
        "V0.1 HOME UI and version badge layout",
        "scheduled safe stop",
        "Telegram settings/alerts",
        "approved Abyss scenic card artwork",
        "Abyss recognition templates/ROIs/thresholds/scales",
        "clear touch-only click and transition verification",
        "administrator elevation and window sizing"
    ],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V0_1_1_ABYSS_CLEAR_GUARD_AUDIT.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("V0.1.1 applied: strict BOTH+3 clear confirmation + Smart Recovery overflow/false-state fixes")
