#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
retry_path = app / "dungeon" / "ScenarioEngine.AbyssRetry.cs"
network_path = app / "dungeon" / "ScenarioEngine.NetworkRecovery.cs"
targets_path = app / "abyss" / "config" / "targets.json"
scenario_path = app / "abyss" / "config" / "scenario.json"
project_path = app / "FishingAutomation.csproj"
update_path = app / "UpdateManager.cs"
payload_dir = Path(__file__).resolve().parent / "v0173-template-payload"
template_dir = app / "abyss" / "templates" / "loot_v173"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label} anchor mismatch: count={text.count(old)}")
    return text.replace(old, new, 1)

def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"method signature missing: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"method opening brace missing: {signature}")
    depth = 0
    end = None
    in_string = False
    verbatim = False
    escape = False
    i = brace
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if not in_string and ch == "/" and nxt == "/":
            nl = text.find("\n", i + 2)
            if nl < 0:
                i = len(text)
                break
            i = nl + 1
            continue
        if not in_string and ch == "/" and nxt == "*":
            close = text.find("*/", i + 2)
            if close < 0:
                raise SystemExit(f"unterminated comment while replacing {signature}")
            i = close + 2
            continue
        if not in_string and ch == "@" and nxt == '"':
            in_string = True
            verbatim = True
            i += 2
            continue
        if not in_string and ch == '"':
            in_string = True
            verbatim = False
            escape = False
            i += 1
            continue
        if in_string:
            if verbatim:
                if ch == '"' and nxt == '"':
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                    verbatim = False
            else:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    if end is None:
        raise SystemExit(f"method closing brace missing: {signature}")
    return text[:start] + replacement.rstrip() + text[end:]

# ---------------------------------------------------------------------------
# 1) Decode the 11 user-provided loot icon templates into the Abyss package.
# ---------------------------------------------------------------------------
template_files = [
    "loot_mor_corsair_coat.png",
    "loot_mor_corsair_gloves.png",
    "loot_mor_corsair_boots.png",
    "loot_mor_corsair_tricorne.png",
    "loot_hallucination_stone.png",
    "loot_devouring_stone.png",
    "loot_abyss_stone.png",
    "loot_rune_engraving_10.png",
    "loot_rune_engraving_10_plus.png",
    "loot_rune_binding_10.png",
    "loot_rune_binding_10_plus.png",
]
template_dir.mkdir(parents=True, exist_ok=True)
for name in template_files:
    src = payload_dir / f"{name}.b64"
    if not src.exists():
        raise SystemExit(f"template payload missing: {src}")
    raw = base64.b64decode(src.read_text(encoding="ascii").strip(), validate=True)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit(f"invalid PNG payload: {src}")
    (template_dir / name).write_bytes(raw)

# ---------------------------------------------------------------------------
# 2) Add image targets for loot and OCR targets for the network retry popup.
# ---------------------------------------------------------------------------
targets = json.loads(read(targets_path))
remove_ids = {
    "network_unstable_title",
    "network_retry_button",
}
targets = [
    t for t in targets
    if t.get("Id") not in remove_ids and not str(t.get("Id", "")).startswith("abyss_loot_")
]

loot_target_specs = [
    ("abyss_loot_mor_corsair_coat", "loot_mor_corsair_coat.png"),
    ("abyss_loot_mor_corsair_gloves", "loot_mor_corsair_gloves.png"),
    ("abyss_loot_mor_corsair_boots", "loot_mor_corsair_boots.png"),
    ("abyss_loot_mor_corsair_tricorne", "loot_mor_corsair_tricorne.png"),
    ("abyss_loot_hallucination_stone", "loot_hallucination_stone.png"),
    ("abyss_loot_devouring_stone", "loot_devouring_stone.png"),
    ("abyss_loot_abyss_stone", "loot_abyss_stone.png"),
    ("abyss_loot_rune_engraving_10", "loot_rune_engraving_10.png"),
    ("abyss_loot_rune_engraving_10_plus", "loot_rune_engraving_10_plus.png"),
    ("abyss_loot_rune_binding_10", "loot_rune_binding_10.png"),
    ("abyss_loot_rune_binding_10_plus", "loot_rune_binding_10_plus.png"),
]
for target_id, filename in loot_target_specs:
    targets.append({
        "Id": target_id,
        "Kind": "template",
        "Roi": {"X": 20, "Y": 80, "Width": 760, "Height": 800},
        "TemplatePath": f"templates/loot_v173/{filename}",
        "Threshold": 0.74,
        "TemplateScaleMin": 0.75,
        "TemplateScaleMax": 1.85,
        "TemplateScaleStep": 0.05,
    })

targets.extend([
    {
        "Id": "network_unstable_title",
        "Kind": "ocr",
        "Roi": {"X": 150, "Y": 600, "Width": 520, "Height": 180},
        "Text": "네트워크 상태가 불안정합니다",
        "MaxEditDistance": 3,
        "OcrRetryAt2x": True,
    },
    {
        "Id": "network_retry_button",
        "Kind": "ocr",
        "Roi": {"X": 370, "Y": 835, "Width": 270, "Height": 145},
        "Text": "다시 시도하기",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True,
    },
])
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# ---------------------------------------------------------------------------
# 3) Replace OCR-only loot recognition with image-template-first 2-frame logic.
#    Existing OCR remains as fallback only.
# ---------------------------------------------------------------------------
retry = read(retry_path)

mapping_anchor = '''    private static readonly Rectangle AbyssLootCanonicalRoi = new(20, 80, 760, 800);
'''
mapping_insert = '''    private static readonly Rectangle AbyssLootCanonicalRoi = new(20, 80, 760, 800);

    // V0173_ABYSS_LOOT_IMAGE_MATCH
    // User-provided item icons are the primary authority. OCR remains only as fallback.
    private static readonly (string TargetId, string LootKey)[] AbyssLootTemplateTargets =
    {
        ("abyss_loot_hallucination_stone", FishingAutomation.LootStats.HallucinationStone),
        ("abyss_loot_devouring_stone", FishingAutomation.LootStats.DevouringStone),
        ("abyss_loot_abyss_stone", FishingAutomation.LootStats.AbyssStone),
        ("abyss_loot_rune_engraving_10", FishingAutomation.LootStats.RuneEngraving10),
        ("abyss_loot_rune_engraving_10_plus", FishingAutomation.LootStats.RuneEngraving10Plus),
        ("abyss_loot_rune_binding_10", FishingAutomation.LootStats.RuneBinding10),
        ("abyss_loot_rune_binding_10_plus", FishingAutomation.LootStats.RuneBinding10Plus),
        ("abyss_loot_mor_corsair_coat", FishingAutomation.LootStats.MorCorsairCoat),
        ("abyss_loot_mor_corsair_gloves", FishingAutomation.LootStats.MorCorsairGloves),
        ("abyss_loot_mor_corsair_boots", FishingAutomation.LootStats.MorCorsairBoots),
        ("abyss_loot_mor_corsair_tricorne", FishingAutomation.LootStats.MorCorsairTricorne),
    };
'''
retry = replace_once(retry, mapping_anchor, mapping_insert, "loot mapping")

detect_signature = "    private async Task<HashSet<string>> DetectAbyssLootAsync(Bitmap frame, CancellationToken ct)"
new_detect = r'''    private async Task<Dictionary<string, DetectionResult>> DetectAbyssLootTemplateFrameAsync(
        Bitmap frame,
        CancellationToken ct)
    {
        var hits = new Dictionary<string, DetectionResult>(StringComparer.Ordinal);
        foreach (var item in AbyssLootTemplateTargets)
        {
            ct.ThrowIfCancellationRequested();
            var hit = await _detector.DetectAsync(item.TargetId, frame, ct);
            hits[item.LootKey] = hit;
        }
        return hits;
    }

    private async Task<HashSet<string>> DetectAbyssLootAsync(Bitmap frame, CancellationToken ct)
    {
        // Require the same item image in two fresh consecutive result frames.
        // This avoids accidental counting from a single noisy template match.
        var first = await DetectAbyssLootTemplateFrameAsync(frame, ct);
        await Task.Delay(180, ct);
        using var secondFrame = await CaptureGameWindowAsync(ct);
        var second = await DetectAbyssLootTemplateFrameAsync(secondFrame, ct);

        var stable = new HashSet<string>(StringComparer.Ordinal);
        foreach (var item in AbyssLootTemplateTargets)
        {
            if (first.TryGetValue(item.LootKey, out var a) &&
                second.TryGetValue(item.LootKey, out var b) &&
                a.Found && b.Found)
            {
                stable.Add(item.LootKey);
                Log?.Invoke(
                    $"[어비스 전리품 이미지] 2/2 확인: " +
                    $"{FishingAutomation.LootStats.GetDisplayName(item.LootKey)} " +
                    $"score={a.Score:0.000}/{b.Score:0.000}");
            }
        }

        if (stable.Count > 0)
            return stable;

        // Keep the old OCR recognizer only as a fallback. Template misses do not
        // block the existing result/retry flow.
        var best = second
            .OrderByDescending(kv => kv.Value.Score)
            .Take(3)
            .Select(kv =>
                $"{FishingAutomation.LootStats.GetDisplayName(kv.Key)}={kv.Value.Score:0.000}");
        Log?.Invoke($"[어비스 전리품 이미지] 2프레임 확정 없음 · 상위 점수: {string.Join(", ", best)} -> OCR 보조 확인");

        _abyssLootOcr ??= new OcrRecognizer();
        var roi = ScaleAbyssResultRoi(AbyssLootCanonicalRoi, secondFrame.Size);
        var found = new HashSet<string>(StringComparer.Ordinal);

        foreach (int scale in new[] { 1, 2 })
        {
            var lines = await _abyssLootOcr.ReadLinesAsync(secondFrame, roi, scale, ct);
            foreach (var line in lines)
                ClassifyAbyssLootLine(secondFrame, line, found);
        }

        if (found.Count > 0)
        {
            Log?.Invoke(
                $"[어비스 전리품 OCR 보조] " +
                $"{string.Join(", ", found.Select(FishingAutomation.LootStats.GetDisplayName))}");
        }

        return found;
    }'''
retry = replace_method(retry, detect_signature, new_detect)
write(retry_path, retry)

# ---------------------------------------------------------------------------
# 4) Add global Abyss network reconnect watcher.
#    Confirm title + retry button twice, send Space, wait until popup is gone,
#    then restart the Abyss cycle from step 1.
# ---------------------------------------------------------------------------
network_code = r'''using System.Diagnostics;
using System.Drawing;

namespace DungeonVisionBot;

internal sealed partial class ScenarioEngine
{
    // V0173_NETWORK_RECONNECT
    private bool _networkReconnectHandling;
    private bool _networkRestartRequested;

    private async Task<Bitmap> CaptureGameWindowRawAsync(CancellationToken ct)
    {
        Exception? lastError = null;

        for (int attempt = 1; attempt <= 12; attempt++)
        {
            ct.ThrowIfCancellationRequested();
            _hwnd = await ResolveRequiredGameWindowAsync(ct);

            try
            {
                return _capture.CaptureClient(_hwnd);
            }
            catch (Exception ex) when (
                ex is InvalidOperationException ||
                ex is System.ComponentModel.Win32Exception ||
                ex is System.Runtime.InteropServices.ExternalException)
            {
                lastError = ex;
                await Task.Delay(150, ct);
            }
        }

        throw new InvalidOperationException(
            "네트워크 복구 중 마비노기 모바일 화면 캡처가 반복해서 실패했습니다.",
            lastError);
    }

    private async Task<bool> IsNetworkRetryPopupAsync(Bitmap frame, CancellationToken ct)
    {
        var title = await _detector.DetectAsync("network_unstable_title", frame, ct);
        if (!title.Found)
            return false;

        var retry = await _detector.DetectAsync("network_retry_button", frame, ct);
        return retry.Found;
    }

    private void CompleteNetworkRestartRequest(string context)
    {
        _networkRestartRequested = false;
        _networkReconnectHandling = false;
        _resumeStepIndex = 0;
        _abyssCombatStartedAt = null;
        _abyssExitInProgress = false;
        _abyssClearTitleFallbackConsecutive = 0;

        Log?.Invoke(
            $"[네트워크 복구] {context} -> 기존 판 상태 초기화, 어비스 처음부터 재시작");
    }

    private async Task HandleNetworkReconnectIfNeededAsync(Bitmap frame, CancellationToken ct)
    {
        if (!IsAbyss || _networkReconnectHandling || _networkRestartRequested)
            return;

        if (!await IsNetworkRetryPopupAsync(frame, ct))
            return;

        _networkReconnectHandling = true;
        try
        {
            // Two-frame confirmation prevents an OCR false positive from sending Space.
            await Task.Delay(180, ct);
            using (var confirm = await CaptureGameWindowRawAsync(ct))
            {
                if (!await IsNetworkRetryPopupAsync(confirm, ct))
                {
                    Log?.Invoke("[네트워크 복구] 후보 1/2 후 사라짐 -> 입력 없음");
                    return;
                }
            }

            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            NativeMethods.SetForegroundWindow(_hwnd);
            Log?.Invoke("[네트워크 복구] '네트워크 상태가 불안정합니다' + '다시 시도하기' 2/2 확인 -> Space 1회");
            _input.TapScanCode(0x39);

            var wait = Stopwatch.StartNew();
            int goneFrames = 0;
            int spacePresses = 1;

            while (wait.Elapsed < TimeSpan.FromSeconds(45))
            {
                ct.ThrowIfCancellationRequested();
                await Task.Delay(500, ct);

                using var check = await CaptureGameWindowRawAsync(ct);
                bool popup = await IsNetworkRetryPopupAsync(check, ct);

                if (!popup)
                {
                    goneFrames++;
                    if (goneFrames >= 3)
                    {
                        _networkRestartRequested = true;
                        Log?.Invoke("[네트워크 복구] 재접속 팝업 사라짐 3/3 확인 -> 어비스 처음부터 재시작 요청");
                        throw new RestartCycleException();
                    }
                    continue;
                }

                goneFrames = 0;

                // One guarded retry is allowed only if the exact same popup is still
                // confirmed after five seconds. Never click "시작 화면으로".
                if (spacePresses < 2 && wait.Elapsed >= TimeSpan.FromSeconds(5))
                {
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    Log?.Invoke("[네트워크 복구] 팝업 유지 -> '다시 시도하기' 재확인 후 Space 1회 추가");
                    _input.TapScanCode(0x39);
                    spacePresses++;
                }
            }

            throw new TimeoutException(
                "네트워크 '다시 시도하기' Space 입력 후 45초 안에 팝업 종료를 확인하지 못했습니다.");
        }
        finally
        {
            _networkReconnectHandling = false;
        }
    }
}
'''
write(network_path, network_code)

# ---------------------------------------------------------------------------
# 5) Wire the network watcher into every Abyss capture and make restart safe
#    even while Smart Recovery is already running.
# ---------------------------------------------------------------------------
engine = read(engine_path)

old_restart = '''            catch (RestartCycleException)
            {
                recoveryFailures = 0;
                repeatedRecoveryStep = -1;
                repeatedRecoveryCount = 0;
                _resumeStepIndex = 0;
                Log?.Invoke("감시 항목에 의해 현재 판을 처음부터 다시 시작합니다.");
            }
'''
new_restart = '''            catch (RestartCycleException)
            {
                recoveryFailures = 0;
                repeatedRecoveryStep = -1;
                repeatedRecoveryCount = 0;

                if (_networkRestartRequested)
                    CompleteNetworkRestartRequest("재접속 완료");
                else
                    _resumeStepIndex = 0;

                Log?.Invoke("감시 항목에 의해 현재 판을 처음부터 다시 시작합니다.");
            }
'''
engine = replace_once(engine, old_restart, new_restart, "RestartCycle catch")

old_recovery_decl = '''                int max = Math.Max(1, _settings.AutoRecoveryMaxAttempts);
                bool recovered = false;

                while (!recovered)
'''
new_recovery_decl = '''                int max = Math.Max(1, _settings.AutoRecoveryMaxAttempts);
                bool recovered = false;
                bool networkCycleRestart = false;

                while (!recovered)
'''
engine = replace_once(engine, old_recovery_decl, new_recovery_decl, "recovery declarations")

old_recovery_call = '''                    recovered = await TrySmartRecoveryAsync(ct);
                    if (recovered)
'''
new_recovery_call = '''                    try
                    {
                        recovered = await TrySmartRecoveryAsync(ct);
                    }
                    catch (RestartCycleException) when (_networkRestartRequested)
                    {
                        networkCycleRestart = true;
                        break;
                    }

                    if (recovered)
'''
engine = replace_once(engine, old_recovery_call, new_recovery_call, "recovery restart catch")

old_post_recovery = '''                await Task.Delay(TimeSpan.FromSeconds(Math.Max(1, _settings.AutoRecoveryDelaySeconds)), ct);
            }
'''
new_post_recovery = '''                if (networkCycleRestart)
                {
                    CompleteNetworkRestartRequest("자동복구 중 재접속 완료");
                    continue;
                }

                await Task.Delay(TimeSpan.FromSeconds(Math.Max(1, _settings.AutoRecoveryDelaySeconds)), ct);
            }
'''
engine = replace_once(engine, old_post_recovery, new_post_recovery, "post recovery restart")

old_capture_start = '''    private async Task<Bitmap> CaptureGameWindowAsync(CancellationToken ct)
    {
        Exception? lastError = null;
'''
new_capture_start = '''    private async Task<Bitmap> CaptureGameWindowAsync(CancellationToken ct)
    {
        if (_networkRestartRequested)
            throw new RestartCycleException();

        Exception? lastError = null;
'''
engine = replace_once(engine, old_capture_start, new_capture_start, "capture pending restart")

old_capture_return = '''                Bitmap frame = _capture.CaptureClient(_hwnd);
                DiagnosticObserveFrame(frame);
                return frame;
'''
new_capture_return = '''                Bitmap frame = _capture.CaptureClient(_hwnd);
                try
                {
                    DiagnosticObserveFrame(frame);
                    await HandleNetworkReconnectIfNeededAsync(frame, ct);
                    return frame;
                }
                catch
                {
                    frame.Dispose();
                    throw;
                }
'''
engine = replace_once(engine, old_capture_return, new_capture_return, "capture network hook")
write(engine_path, engine)

# ---------------------------------------------------------------------------
# 6) Version metadata.
# ---------------------------------------------------------------------------
project = read(project_path)
for old, new in (
    ("<Version>0.1.72</Version>", "<Version>0.1.73</Version>"),
    ("<AssemblyVersion>0.1.72.0</AssemblyVersion>", "<AssemblyVersion>0.1.73.0</AssemblyVersion>"),
    ("<FileVersion>0.1.72.0</FileVersion>", "<FileVersion>0.1.73.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)

# The existing project only publishes its known template set. Explicitly include
# the new V0.1.73 loot subdirectory so auto-update ZIPs contain all 11 icons.
loot_content_item = r'''  <ItemGroup>
    <Content Include="abyss\templates\loot_v173\**\*.png">
      <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
      <CopyToPublishDirectory>PreserveNewest</CopyToPublishDirectory>
    </Content>
  </ItemGroup>
'''
if 'abyss\\templates\\loot_v173\\**\\*.png' not in project:
    if "</Project>" not in project:
        raise SystemExit("csproj closing Project tag missing")
    project = project.replace("</Project>", loot_content_item + "</Project>", 1)

write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.72"' not in update:
    raise SystemExit("UpdateManager V0.1.72 marker missing")
update = update.replace('CurrentVersion = "V0.1.72"', 'CurrentVersion = "V0.1.73"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 7) Static invariants.
# ---------------------------------------------------------------------------
engine_check = read(engine_path)
retry_check = read(retry_path)
network_check = read(network_path)
targets_check = json.loads(read(targets_path))
ids = {t.get("Id") for t in targets_check}
project_check = read(project_path)
if 'abyss\\templates\\loot_v173\\**\\*.png' not in project_check:
    raise SystemExit("loot_v173 publish Content item missing")

for name in template_files:
    p = template_dir / name
    if not p.exists() or p.stat().st_size < 100:
        raise SystemExit(f"decoded loot template missing/empty: {p}")

for target_id, _ in loot_target_specs:
    if target_id not in ids:
        raise SystemExit(f"loot target missing: {target_id}")

for target_id in ("network_unstable_title", "network_retry_button"):
    if target_id not in ids:
        raise SystemExit(f"network target missing: {target_id}")

for marker in (
    "V0173_ABYSS_LOOT_IMAGE_MATCH",
    "DetectAbyssLootTemplateFrameAsync",
    "[어비스 전리품 이미지] 2/2 확인",
    "OCR 보조 확인",
    "LootStats.RecordRound",
):
    if marker not in retry_check:
        raise SystemExit(f"loot marker missing: {marker}")

for marker in (
    "V0173_NETWORK_RECONNECT",
    "network_unstable_title",
    "network_retry_button",
    "_input.TapScanCode(0x39)",
    "재접속 팝업 사라짐 3/3 확인",
    "RestartCycleException",
):
    if marker not in network_check:
        raise SystemExit(f"network marker missing: {marker}")

for marker in (
    "V0172_ABYSS_CLEAR_TITLE_FALLBACK",
    "AbyssClearTitleFallbackMinScore = 0.68",
    "AbyssClearTitleFallbackRequiredFrames = 2",
):
    if marker not in engine_check:
        raise SystemExit(f"V0.1.72 clear fallback lost: {marker}")

telegram = read(app / "MainForm.Telegram.cs")
if 'case "/item":' not in telegram or 'case "/itemreset":' not in telegram:
    raise SystemExit("Telegram /item or /itemreset missing")

for p in app.rglob("*"):
    if p.suffix.lower() in (".cs", ".json"):
        text = read(p)
        if re.search(r"abyss_death|AbyssDeath|DeathTimeout|사망", text):
            raise SystemExit(f"death logic returned: {p}")

scenario = json.loads(read(scenario_path))
combat = next(s for s in scenario["Steps"] if s["Target"] == "abyss_touch_screen")
if combat["TimeoutSeconds"] != 600:
    raise SystemExit("Abyss combat timeout is not 600 seconds")

print("PASS V0.1.73: image-first loot 2-frame counting + guarded network Space reconnect; V0.1.72 clear fallback preserved")
