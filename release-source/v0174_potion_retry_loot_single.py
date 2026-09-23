#!/usr/bin/env python3
from pathlib import Path
import re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
retry_path = app / "dungeon" / "ScenarioEngine.AbyssRetry.cs"
project_path = app / "FishingAutomation.csproj"
update_path = app / "UpdateManager.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} anchor mismatch: count={count}")
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 1) Potion popup: do not hard-stop after a single missed ESC.
#    Retry ESC only while the exact same popup is still confirmed.
# ---------------------------------------------------------------------------
engine = read(engine_path)

escape_start = '''                case "escape":
                {
'''
escape_end = '''                case "click":
'''
start = engine.find(escape_start)
end = engine.find(escape_end, start)
if start < 0 or end < 0:
    raise SystemExit("CheckMonitors escape block not found")

new_escape = r'''                case "escape":
                {
                    // V0174_POTION_ESC_RETRY
                    // A real potion-shortage popup occasionally ignores a single ESC.
                    // Never click the purchase button. Confirm the same popup again and
                    // retry ESC up to three times, verifying disappearance after each try.
                    Log?.Invoke($"[monitor] {m.Target} 1/2 확인 -> ESC 닫기 재확인");
                    await Task.Delay(180, ct);
                    using (var confirmFrame = await CaptureGameWindowAsync(ct))
                    {
                        var confirm = await _detector.DetectAsync(m.Target, confirmFrame, ct);
                        if (!confirm.Found)
                        {
                            Log?.Invoke($"[monitor] {m.Target} 2차 확인에서 사라짐 -> 입력 없이 진행");
                            return true;
                        }
                    }

                    const int maxEscAttempts = 3;
                    for (int escAttempt = 1; escAttempt <= maxEscAttempts; escAttempt++)
                    {
                        _hwnd = await ResolveRequiredGameWindowAsync(ct);
                        NativeMethods.SetForegroundWindow(_hwnd);
                        await Task.Delay(120, ct);

                        Log?.Invoke(
                            $"[monitor] {m.Target} 2/2 확인 -> ESC {escAttempt}/{maxEscAttempts} " +
                            "(구매 버튼 클릭 금지)");
                        _input.TapScanCode(0x01);

                        var closeTimer = Stopwatch.StartNew();
                        int goneFrames = 0;
                        bool stillConfirmed = false;

                        while (closeTimer.Elapsed < TimeSpan.FromSeconds(2.5))
                        {
                            ct.ThrowIfCancellationRequested();
                            await Task.Delay(220, ct);

                            using var afterEsc = await CaptureGameWindowAsync(ct);
                            var stillOpen = await _detector.DetectAsync(m.Target, afterEsc, ct);
                            if (stillOpen.Found)
                            {
                                stillConfirmed = true;
                                goneFrames = 0;
                                continue;
                            }

                            if (++goneFrames >= 2)
                            {
                                Log?.Invoke(
                                    $"[monitor] {m.Target} ESC {escAttempt}/{maxEscAttempts} 후 " +
                                    "닫힘 2프레임 확인 -> 원래 진행 계속");
                                return true;
                            }
                        }

                        if (!stillConfirmed)
                        {
                            // Detection became unstable but never produced the two clean
                            // gone frames required above. Let the next monitor scan decide
                            // instead of turning this into a fatal macro error.
                            Log?.Invoke(
                                $"[monitor] {m.Target} ESC {escAttempt}/{maxEscAttempts} 후 " +
                                "팝업 판정 불안정 -> 추가 구매/클릭 없이 다음 감시에서 재확인");
                            return true;
                        }

                        if (escAttempt < maxEscAttempts)
                        {
                            Log?.Invoke(
                                $"[monitor] {m.Target} ESC {escAttempt}/{maxEscAttempts} 후에도 " +
                                "동일 팝업 유지 -> ESC 재시도");
                            await Task.Delay(350, ct);
                        }
                    }

                    // Keep the run alive. The monitor cooldown will expire and the same
                    // confirmed popup will be retried again. This is safer than stopping
                    // the whole Abyss loop or clicking a purchase coordinate.
                    Log?.Invoke(
                        $"[monitor] {m.Target} ESC {maxEscAttempts}회 후에도 팝업 유지 -> " +
                        "매크로 정지하지 않고 다음 감시 주기에 다시 시도");
                    return true;
                }
'''
engine = engine[:start] + new_escape + engine[end:]
write(engine_path, engine)

# ---------------------------------------------------------------------------
# 2) Loot: one tracked loot item maximum per result screen.
#    When related templates cross-match, choose the strongest 2-frame minimum score.
# ---------------------------------------------------------------------------
retry = read(retry_path)

method_sig = "    private async Task<HashSet<string>> DetectAbyssLootAsync(Bitmap frame, CancellationToken ct)"
start = retry.find(method_sig)
if start < 0:
    raise SystemExit("DetectAbyssLootAsync missing")
brace = retry.find("{", start)
depth = 0
end = None
for i in range(brace, len(retry)):
    if retry[i] == "{":
        depth += 1
    elif retry[i] == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break
if end is None:
    raise SystemExit("DetectAbyssLootAsync end missing")

new_loot_method = r'''    private async Task<HashSet<string>> DetectAbyssLootAsync(Bitmap frame, CancellationToken ct)
    {
        // V0174_ABYSS_LOOT_SINGLE_WINNER
        // The tracked special loot is awarded one item at a time. Require the same
        // template in two consecutive frames, then count only the strongest candidate.
        var first = await DetectAbyssLootTemplateFrameAsync(frame, ct);
        await Task.Delay(180, ct);
        using var secondFrame = await CaptureGameWindowAsync(ct);
        var second = await DetectAbyssLootTemplateFrameAsync(secondFrame, ct);

        var stable = new List<(string Key, double Score, double First, double Second)>();
        foreach (var item in AbyssLootTemplateTargets)
        {
            if (first.TryGetValue(item.LootKey, out var a) &&
                second.TryGetValue(item.LootKey, out var b) &&
                a.Found && b.Found)
            {
                stable.Add((
                    item.LootKey,
                    Math.Min(a.Score, b.Score),
                    a.Score,
                    b.Score));
            }
        }

        if (stable.Count > 0)
        {
            var winner = stable
                .OrderByDescending(x => x.Score)
                .ThenBy(x => x.Key, StringComparer.Ordinal)
                .First();

            Log?.Invoke(
                $"[어비스 전리품 이미지] 최종 1개 확정: " +
                $"{FishingAutomation.LootStats.GetDisplayName(winner.Key)} " +
                $"score={winner.First:0.000}/{winner.Second:0.000}");

            if (stable.Count > 1)
            {
                string suppressed = string.Join(
                    ", ",
                    stable
                        .Where(x => !string.Equals(x.Key, winner.Key, StringComparison.Ordinal))
                        .OrderByDescending(x => x.Score)
                        .Select(x =>
                            $"{FishingAutomation.LootStats.GetDisplayName(x.Key)}={x.Score:0.000}"));
                Log?.Invoke(
                    $"[어비스 전리품 이미지] 동시 교차매칭 {stable.Count - 1}개 제외: {suppressed}");
            }

            return new HashSet<string>(StringComparer.Ordinal) { winner.Key };
        }

        // Image matching stays primary. OCR is only a fallback.
        var best = second
            .OrderByDescending(kv => kv.Value.Score)
            .Take(3)
            .Select(kv =>
                $"{FishingAutomation.LootStats.GetDisplayName(kv.Key)}={kv.Value.Score:0.000}");
        Log?.Invoke(
            $"[어비스 전리품 이미지] 2프레임 확정 없음 · 상위 점수: " +
            $"{string.Join(", ", best)} -> OCR 보조 확인");

        _abyssLootOcr ??= new OcrRecognizer();
        var roi = ScaleAbyssResultRoi(AbyssLootCanonicalRoi, secondFrame.Size);
        var found = new HashSet<string>(StringComparer.Ordinal);

        foreach (int scale in new[] { 1, 2 })
        {
            var lines = await _abyssLootOcr.ReadLinesAsync(secondFrame, roi, scale, ct);
            foreach (var line in lines)
                ClassifyAbyssLootLine(secondFrame, line, found);
        }

        if (found.Count == 0)
            return found;

        // OCR can also produce several fuzzy hits from the same visual row.
        // Honor the one-loot-per-round rule and use template similarity only as a
        // tie-breaker among OCR-recognized keys.
        string ocrWinner = found
            .OrderByDescending(key =>
                second.TryGetValue(key, out var hit) ? hit.Score : 0.0)
            .ThenBy(key => key, StringComparer.Ordinal)
            .First();

        if (found.Count > 1)
        {
            Log?.Invoke(
                $"[어비스 전리품 OCR 보조] 복수 후보 {found.Count}개 -> " +
                $"가장 강한 1개만 인정: {FishingAutomation.LootStats.GetDisplayName(ocrWinner)}");
        }
        else
        {
            Log?.Invoke(
                $"[어비스 전리품 OCR 보조] " +
                $"{FishingAutomation.LootStats.GetDisplayName(ocrWinner)}");
        }

        return new HashSet<string>(StringComparer.Ordinal) { ocrWinner };
    }'''

retry = retry[:start] + new_loot_method + retry[end:]
write(retry_path, retry)

# ---------------------------------------------------------------------------
# 3) Version metadata.
# ---------------------------------------------------------------------------
project = read(project_path)
for old, new in (
    ("<Version>0.1.73</Version>", "<Version>0.1.74</Version>"),
    ("<AssemblyVersion>0.1.73.0</AssemblyVersion>", "<AssemblyVersion>0.1.74.0</AssemblyVersion>"),
    ("<FileVersion>0.1.73.0</FileVersion>", "<FileVersion>0.1.74.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.73"' not in update:
    raise SystemExit("UpdateManager V0.1.73 marker missing")
update = update.replace('CurrentVersion = "V0.1.73"', 'CurrentVersion = "V0.1.74"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 4) Static verification.
# ---------------------------------------------------------------------------
engine_check = read(engine_path)
retry_check = read(retry_path)
all_runtime = "\n".join(read(p) for p in (app / "dungeon").glob("ScenarioEngine*.cs"))

for marker in (
    "V0174_POTION_ESC_RETRY",
    "ESC {escAttempt}/{maxEscAttempts}",
    "매크로 정지하지 않고 다음 감시 주기에 다시 시도",
):
    if marker not in engine_check:
        raise SystemExit(f"potion retry marker missing: {marker}")

if "회복 물약 팝업 ESC 1회 후 닫힘을 확인하지 못했습니다" in engine_check:
    raise SystemExit("old one-ESC fatal stop remains")

for marker in (
    "V0174_ABYSS_LOOT_SINGLE_WINNER",
    "최종 1개 확정",
    "동시 교차매칭",
    "return new HashSet<string>(StringComparer.Ordinal) { winner.Key };",
):
    if marker not in retry_check:
        raise SystemExit(f"loot single-winner marker missing: {marker}")

# Preserve V0.1.73/V0.1.72 behavior.
for marker in (
    "V0172_ABYSS_CLEAR_TITLE_FALLBACK",
    "V0173_NETWORK_RECONNECT",
    "V0173_ABYSS_LOOT_IMAGE_MATCH",
    "LootStats.RecordRound",
    "실제 결과 화면 2/2 확인",
):
    if marker not in all_runtime:
        raise SystemExit(f"preserved behavior marker missing: {marker}")

for p in app.rglob("*"):
    if p.suffix.lower() in (".cs", ".json"):
        text = read(p)
        if re.search(r"abyss_death|AbyssDeath|DeathTimeout|사망", text):
            raise SystemExit(f"death logic returned: {p}")

scenario = __import__("json").loads(read(app / "abyss" / "config" / "scenario.json"))
combat = next(s for s in scenario["Steps"] if s["Target"] == "abyss_touch_screen")
if combat["TimeoutSeconds"] != 600:
    raise SystemExit("Abyss combat timeout is not 600 seconds")

print("PASS V0.1.74: potion ESC retry + one-loot winner; V0.1.73 network/templates preserved")
