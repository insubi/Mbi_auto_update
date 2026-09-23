#!/usr/bin/env python3
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
retry_path = app / "dungeon" / "ScenarioEngine.AbyssRetry.cs"
ocr_path = app / "dungeon" / "OcrRecognizer.cs"
telegram_path = app / "MainForm.Telegram.cs"
stats_path = app / "LootStats.cs"
project_path = app / "FishingAutomation.csproj"
update_path = app / "UpdateManager.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
           {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat"}]
before = {p.relative_to(root).as_posix(): digest(p) for p in tracked}

# ---------------------------------------------------------------------------
# 1) Persistent + session/today loot statistics shared by the Abyss engine
#    and Telegram commands.
# ---------------------------------------------------------------------------
stats_code = r'''using System.Text;
using System.Text.Json;

namespace FishingAutomation;

public static class LootStats
{
    public const string HallucinationStone = "hallucination_stone";
    public const string DevouringStone = "devouring_stone";
    public const string AbyssStone = "abyss_stone";
    public const string RuneEngraving10 = "rune_engraving_10";
    public const string RuneEngraving10Plus = "rune_engraving_10_plus";
    public const string RuneBinding10 = "rune_binding_10";
    public const string RuneBinding10Plus = "rune_binding_10_plus";
    public const string MorCorsairCoat = "mor_corsair_coat";
    public const string MorCorsairGloves = "mor_corsair_gloves";
    public const string MorCorsairBoots = "mor_corsair_boots";
    public const string MorCorsairTricorne = "mor_corsair_tricorne";

    private static readonly object Gate = new();

    private static readonly string[] OrderedKeys =
    {
        HallucinationStone,
        DevouringStone,
        AbyssStone,
        RuneEngraving10,
        RuneEngraving10Plus,
        RuneBinding10,
        RuneBinding10Plus,
        MorCorsairCoat,
        MorCorsairGloves,
        MorCorsairBoots,
        MorCorsairTricorne,
    };

    private static readonly Dictionary<string, string> DisplayNames = new(StringComparer.Ordinal)
    {
        [HallucinationStone] = "허상의 마력석",
        [DevouringStone] = "포식의 마력석",
        [AbyssStone] = "심해의 마력석",
        [RuneEngraving10] = "룬새김 장식(★10)",
        [RuneEngraving10Plus] = "룬새김 장식(★10)+",
        [RuneBinding10] = "룬결속 장식(★10)",
        [RuneBinding10Plus] = "룬결속 장식(★10)+",
        [MorCorsairCoat] = "모르 코르셰어 코트",
        [MorCorsairGloves] = "모르 코르셰어 글러브",
        [MorCorsairBoots] = "모르 코르셰어 부츠",
        [MorCorsairTricorne] = "모르 코르셰어 트리코른",
    };

    private static readonly string StatsDirectory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "MabiAuto");

    private static readonly string StatsPath = Path.Combine(StatsDirectory, "loot_stats.json");
    private static readonly Dictionary<string, int> Session = CreateZeroCounts();
    private static PersistedStats Data = Load();

    public static string GetDisplayName(string key)
        => DisplayNames.TryGetValue(key, out var name) ? name : key;

    public static void RecordRound(IEnumerable<string> foundKeys)
    {
        lock (Gate)
        {
            bool changed = EnsureToday();
            foreach (string key in foundKeys.Distinct(StringComparer.Ordinal))
            {
                if (!DisplayNames.ContainsKey(key))
                    continue;

                Session[key] = Session.GetValueOrDefault(key) + 1;
                Data.Today[key] = Data.Today.GetValueOrDefault(key) + 1;
                Data.Lifetime[key] = Data.Lifetime.GetValueOrDefault(key) + 1;
                changed = true;
            }

            if (changed)
                Save();
        }
    }

    public static string GetTelegramReport()
    {
        lock (Gate)
        {
            if (EnsureToday())
                Save();

            var sb = new StringBuilder();
            sb.AppendLine("전리품 획득 현황");
            sb.AppendLine("(이번 실행 / 오늘 / 누적)");
            sb.AppendLine();

            AppendSection(sb, "마력석", new[]
            {
                HallucinationStone, DevouringStone, AbyssStone
            });

            AppendSection(sb, "장식", new[]
            {
                RuneEngraving10, RuneEngraving10Plus,
                RuneBinding10, RuneBinding10Plus
            });

            AppendSection(sb, "모르 코르셰어", new[]
            {
                MorCorsairCoat, MorCorsairGloves, MorCorsairBoots, MorCorsairTricorne
            });

            int sessionTotal = OrderedKeys.Sum(k => Session.GetValueOrDefault(k));
            int todayTotal = OrderedKeys.Sum(k => Data.Today.GetValueOrDefault(k));
            int lifetimeTotal = OrderedKeys.Sum(k => Data.Lifetime.GetValueOrDefault(k));

            sb.AppendLine($"총합: {sessionTotal} / {todayTotal} / {lifetimeTotal}");
            return sb.ToString().TrimEnd();
        }
    }

    public static string ResetLifetime()
    {
        lock (Gate)
        {
            EnsureToday();
            foreach (string key in OrderedKeys)
                Data.Lifetime[key] = 0;
            Save();

            return "전리품 누적 기록을 초기화했습니다.\n이번 실행/오늘 기록은 유지됩니다.\n누적 합계: 0개";
        }
    }

    private static void AppendSection(StringBuilder sb, string title, IEnumerable<string> keys)
    {
        sb.AppendLine($"[{title}]");
        foreach (string key in keys)
        {
            sb.AppendLine(
                $"{DisplayNames[key]}: " +
                $"{Session.GetValueOrDefault(key)} / " +
                $"{Data.Today.GetValueOrDefault(key)} / " +
                $"{Data.Lifetime.GetValueOrDefault(key)}");
        }
        sb.AppendLine();
    }

    private static Dictionary<string, int> CreateZeroCounts()
        => OrderedKeys.ToDictionary(k => k, _ => 0, StringComparer.Ordinal);

    private static void FillMissing(Dictionary<string, int> counts)
    {
        foreach (string key in OrderedKeys)
            counts.TryAdd(key, 0);
    }

    private static bool EnsureToday()
    {
        string today = DateTime.Now.ToString("yyyy-MM-dd");
        if (string.Equals(Data.Day, today, StringComparison.Ordinal))
            return false;

        Data.Day = today;
        Data.Today = CreateZeroCounts();
        return true;
    }

    private static PersistedStats Load()
    {
        try
        {
            Directory.CreateDirectory(StatsDirectory);
            if (!File.Exists(StatsPath))
                return NewPersisted();

            var loaded = JsonSerializer.Deserialize<PersistedStats>(
                File.ReadAllText(StatsPath),
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

            if (loaded is null)
                return NewPersisted();

            loaded.Today ??= CreateZeroCounts();
            loaded.Lifetime ??= CreateZeroCounts();
            FillMissing(loaded.Today);
            FillMissing(loaded.Lifetime);

            string today = DateTime.Now.ToString("yyyy-MM-dd");
            if (!string.Equals(loaded.Day, today, StringComparison.Ordinal))
            {
                loaded.Day = today;
                loaded.Today = CreateZeroCounts();
            }

            return loaded;
        }
        catch
        {
            return NewPersisted();
        }
    }

    private static PersistedStats NewPersisted()
        => new()
        {
            Day = DateTime.Now.ToString("yyyy-MM-dd"),
            Today = CreateZeroCounts(),
            Lifetime = CreateZeroCounts(),
        };

    private static void Save()
    {
        Directory.CreateDirectory(StatsDirectory);
        string temp = StatsPath + ".tmp";
        string json = JsonSerializer.Serialize(Data, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(temp, json);
        File.Move(temp, StatsPath, true);
    }

    private sealed class PersistedStats
    {
        public string Day { get; set; } = "";
        public Dictionary<string, int> Today { get; set; } = new(StringComparer.Ordinal);
        public Dictionary<string, int> Lifetime { get; set; } = new(StringComparer.Ordinal);
    }
}
'''
write(stats_path, stats_code)

# ---------------------------------------------------------------------------
# 2) Expose OCR line reading so the confirmed result screen can be scanned
#    in one pass rather than adding 11 independent full-frame OCR targets.
# ---------------------------------------------------------------------------
ocr = read(ocr_path)
ocr_anchor = '''    private async Task<DetectionResult> FindAtScaleAsync(Bitmap frame, Rectangle roi, string wanted, int maxEditDistance, int scale, CancellationToken ct)
'''
ocr_helper = r'''    // V0168_ABYSS_LOOT_OCR_LINES
    public async Task<IReadOnlyList<DetectionResult>> ReadLinesAsync(
        Bitmap frame,
        Rectangle roi,
        int scale,
        CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        roi = Rectangle.Intersect(new Rectangle(Point.Empty, frame.Size), roi);
        if (roi.Width <= 0 || roi.Height <= 0)
            return Array.Empty<DetectionResult>();

        using var crop = frame.Clone(roi, PixelFormat.Format24bppRgb);
        using var prepared = scale == 1
            ? (Bitmap)crop.Clone()
            : ResizeNearest(crop, crop.Width * scale, crop.Height * scale);
        using var software = await ToSoftwareBitmapAsync(prepared);
        var ocr = await _engine.RecognizeAsync(software);
        ct.ThrowIfCancellationRequested();

        var lines = new List<DetectionResult>();
        foreach (var line in ocr.Lines)
        {
            if (line.Words.Count == 0)
                continue;

            string lineText = string.Join(" ", line.Words.Select(w => w.Text));
            double left = line.Words.Min(w => w.BoundingRect.X);
            double top = line.Words.Min(w => w.BoundingRect.Y);
            double right = line.Words.Max(w => w.BoundingRect.X + w.BoundingRect.Width);
            double bottom = line.Words.Max(w => w.BoundingRect.Y + w.BoundingRect.Height);

            var bounds = Rectangle.FromLTRB(
                roi.X + (int)Math.Round(left / scale),
                roi.Y + (int)Math.Round(top / scale),
                roi.X + (int)Math.Round(right / scale),
                roi.Y + (int)Math.Round(bottom / scale));

            lines.Add(new DetectionResult(true, bounds, 1.0, lineText));
        }

        return lines;
    }

'''
if ocr.count(ocr_anchor) != 1:
    raise SystemExit("OcrRecognizer FindAtScale anchor mismatch")
ocr = ocr.replace(ocr_anchor, ocr_helper + ocr_anchor, 1)
write(ocr_path, ocr)

# ---------------------------------------------------------------------------
# 3) Scan tracked loot only after the real Abyss result screen is confirmed.
#    Count each tracked item at most once per result/round.
# ---------------------------------------------------------------------------
retry = read(retry_path)

field_anchor = '''    private string _lastAbyssResultDiagnostic = "no-frame";
'''
field_insert = '''    private string _lastAbyssResultDiagnostic = "no-frame";

    // V0168_ABYSS_LOOT_TRACKING
    private OcrRecognizer? _abyssLootOcr;
    private bool _abyssLootCountedForCurrentResult;
    private static readonly Rectangle AbyssLootCanonicalRoi = new(20, 80, 760, 800);
'''
if retry.count(field_anchor) != 1:
    raise SystemExit("Abyss retry field anchor mismatch")
retry = retry.replace(field_anchor, field_insert, 1)

method_anchor = '''    private async Task RetryAbyssResultAsync(CancellationToken ct)
'''
loot_methods = r'''    private static bool AbyssLootTextLooksPlus(Bitmap frame, Rectangle textBounds, string rawText)
    {
        if (rawText.Contains('+'))
            return true;

        Rectangle bounds = Rectangle.Intersect(
            new Rectangle(Point.Empty, frame.Size),
            Rectangle.Inflate(textBounds, 4, 3));
        if (bounds.Width <= 0 || bounds.Height <= 0)
            return false;

        int blue = 0;
        int green = 0;
        for (int y = bounds.Top; y < bounds.Bottom; y += 2)
        {
            for (int x = bounds.Left; x < bounds.Right; x += 2)
            {
                Color c = frame.GetPixel(x, y);
                if (c.B >= 125 && c.B >= c.G + 18 && c.B >= c.R + 28)
                    blue++;
                if (c.G >= 115 && c.G >= c.B + 12 && c.G >= c.R + 22)
                    green++;
            }
        }

        return blue >= 4 && blue > green * 1.15;
    }

    private static void ClassifyAbyssLootLine(
        Bitmap frame,
        DetectionResult line,
        HashSet<string> found)
    {
        string raw = line.ReadText ?? "";
        string norm = FuzzyText.Normalize(raw);
        if (string.IsNullOrEmpty(norm))
            return;

        if (norm.Contains(FuzzyText.Normalize("허상의 마력석"), StringComparison.OrdinalIgnoreCase))
            found.Add(FishingAutomation.LootStats.HallucinationStone);
        if (norm.Contains(FuzzyText.Normalize("포식의 마력석"), StringComparison.OrdinalIgnoreCase))
            found.Add(FishingAutomation.LootStats.DevouringStone);
        if (norm.Contains(FuzzyText.Normalize("심해의 마력석"), StringComparison.OrdinalIgnoreCase))
            found.Add(FishingAutomation.LootStats.AbyssStone);

        if (norm.Contains(FuzzyText.Normalize("룬새김 장식"), StringComparison.OrdinalIgnoreCase))
        {
            found.Add(AbyssLootTextLooksPlus(frame, line.Bounds, raw)
                ? FishingAutomation.LootStats.RuneEngraving10Plus
                : FishingAutomation.LootStats.RuneEngraving10);
        }

        if (norm.Contains(FuzzyText.Normalize("룬결속 장식"), StringComparison.OrdinalIgnoreCase))
        {
            found.Add(AbyssLootTextLooksPlus(frame, line.Bounds, raw)
                ? FishingAutomation.LootStats.RuneBinding10Plus
                : FishingAutomation.LootStats.RuneBinding10);
        }

        if (norm.Contains(FuzzyText.Normalize("모르 코르셰어 코트"), StringComparison.OrdinalIgnoreCase))
            found.Add(FishingAutomation.LootStats.MorCorsairCoat);
        if (norm.Contains(FuzzyText.Normalize("모르 코르셰어 글러브"), StringComparison.OrdinalIgnoreCase))
            found.Add(FishingAutomation.LootStats.MorCorsairGloves);
        if (norm.Contains(FuzzyText.Normalize("모르 코르셰어 부츠"), StringComparison.OrdinalIgnoreCase))
            found.Add(FishingAutomation.LootStats.MorCorsairBoots);
        if (norm.Contains(FuzzyText.Normalize("모르 코르셰어 트리코른"), StringComparison.OrdinalIgnoreCase))
            found.Add(FishingAutomation.LootStats.MorCorsairTricorne);
    }

    private async Task<HashSet<string>> DetectAbyssLootAsync(Bitmap frame, CancellationToken ct)
    {
        _abyssLootOcr ??= new OcrRecognizer();
        var roi = ScaleAbyssResultRoi(AbyssLootCanonicalRoi, frame.Size);
        var found = new HashSet<string>(StringComparer.Ordinal);

        // Run both native and 2x OCR on the same already-confirmed result frame.
        // Unioning exact item-name hits improves recall without changing the result state machine.
        foreach (int scale in new[] { 1, 2 })
        {
            var lines = await _abyssLootOcr.ReadLinesAsync(frame, roi, scale, ct);
            foreach (var line in lines)
                ClassifyAbyssLootLine(frame, line, found);
        }

        return found;
    }

'''
if retry.count(method_anchor) != 1:
    raise SystemExit("RetryAbyssResultAsync method anchor mismatch")
retry = retry.replace(method_anchor, loot_methods + method_anchor, 1)

click_anchor = '''                ct.ThrowIfCancellationRequested();
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} source={retry.ReadText} safe={AbyssRetrySafeRoi}");
'''
click_replace = '''                ct.ThrowIfCancellationRequested();

                if (!_abyssLootCountedForCurrentResult)
                {
                    try
                    {
                        var foundLoot = await DetectAbyssLootAsync(frame, ct);
                        FishingAutomation.LootStats.RecordRound(foundLoot);
                        _abyssLootCountedForCurrentResult = true;

                        if (foundLoot.Count == 0)
                        {
                            Log?.Invoke("[어비스 전리품] 추적 대상 없음 -> 카운트 +0");
                        }
                        else
                        {
                            string names = string.Join(", ", foundLoot.Select(FishingAutomation.LootStats.GetDisplayName));
                            Log?.Invoke($"[어비스 전리품] 이번 판 획득 카운트: {names}");
                        }
                    }
                    catch (OperationCanceledException)
                    {
                        throw;
                    }
                    catch (Exception ex)
                    {
                        // Loot statistics must never block the existing retry flow.
                        _abyssLootCountedForCurrentResult = true;
                        Log?.Invoke($"[어비스 전리품] 인식/저장 실패 -> 다시 하기 흐름 계속: {ex.Message}");
                    }
                }

                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} source={retry.ReadText} safe={AbyssRetrySafeRoi}");
'''
if retry.count(click_anchor) != 1:
    raise SystemExit("Abyss retry click anchor mismatch")
retry = retry.replace(click_anchor, click_replace, 1)

reset_anchor = '''                    Log?.Invoke("[어비스] 다시 하기 결과 화면 이탈 확인 -> 선택 화면 없이 전투 대기로 복귀");
                    return;
'''
reset_replace = '''                    _abyssLootCountedForCurrentResult = false;
                    Log?.Invoke("[어비스] 다시 하기 결과 화면 이탈 확인 -> 선택 화면 없이 전투 대기로 복귀");
                    return;
'''
if retry.count(reset_anchor) != 1:
    raise SystemExit("Abyss retry transition reset anchor mismatch")
retry = retry.replace(reset_anchor, reset_replace, 1)

write(retry_path, retry)

# ---------------------------------------------------------------------------
# 4) Telegram commands.
# ---------------------------------------------------------------------------
telegram = read(telegram_path)
tg_anchor = '''            case "/status":
                return GetRemoteStatus();

            case "/stop":
'''
tg_replace = '''            case "/status":
                return GetRemoteStatus();

            case "/stone":
                return LootStats.GetTelegramReport();

            case "/stonereset":
                return LootStats.ResetLifetime();

            case "/stop":
'''
if telegram.count(tg_anchor) != 1:
    raise SystemExit("Telegram command anchor mismatch")
telegram = telegram.replace(tg_anchor, tg_replace, 1)
write(telegram_path, telegram)

# ---------------------------------------------------------------------------
# 5) Version metadata.
# ---------------------------------------------------------------------------
project = read(project_path)
for old, new in (
    ("<Version>0.1.67</Version>", "<Version>0.1.68</Version>"),
    ("<AssemblyVersion>0.1.67.0</AssemblyVersion>", "<AssemblyVersion>0.1.68.0</AssemblyVersion>"),
    ("<FileVersion>0.1.67.0</FileVersion>", "<FileVersion>0.1.68.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.67"' not in update:
    raise SystemExit("UpdateManager V0.1.67 marker missing")
update = update.replace('CurrentVersion = "V0.1.67"', 'CurrentVersion = "V0.1.68"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 6) Static verification / scope restriction.
# ---------------------------------------------------------------------------
patched_retry = read(retry_path)
patched_ocr = read(ocr_path)
patched_tg = read(telegram_path)
patched_stats = read(stats_path)

for marker in (
    "V0168_ABYSS_LOOT_TRACKING",
    "DetectAbyssLootAsync",
    "_abyssLootCountedForCurrentResult",
    "[어비스 전리품] 이번 판 획득 카운트:",
    "V0168_ABYSS_LOOT_OCR_LINES",
    "ReadLinesAsync",
    'case "/stone":',
    'case "/stonereset":',
    "허상의 마력석",
    "포식의 마력석",
    "심해의 마력석",
    "룬새김 장식(★10)+",
    "룬결속 장식(★10)+",
    "모르 코르셰어 코트",
    "모르 코르셰어 글러브",
    "모르 코르셰어 부츠",
    "모르 코르셰어 트리코른",
):
    if marker not in (patched_retry + patched_ocr + patched_tg + patched_stats):
        raise SystemExit(f"required V0.1.68 marker missing: {marker}")

# Preserve current critical Abyss behavior.
engine_all = "\n".join(
    read(p) for p in (app / "dungeon").glob("ScenarioEngine*.cs")
)
for marker in (
    "V0167_ABYSS_DEATH_WAIT_NONBLOCKING",
    "V0166_ABYSS_SCENE_SKIP_OUTLINE",
    "V0164_ABYSS_CLEAR_LOG_SIMPLIFIED",
    "실제 결과 화면 2/2 확인",
):
    if marker not in engine_all:
        raise SystemExit(f"existing critical marker missing: {marker}")

allowed = {
    retry_path.relative_to(root).as_posix(),
    ocr_path.relative_to(root).as_posix(),
    telegram_path.relative_to(root).as_posix(),
    stats_path.relative_to(root).as_posix(),
    project_path.relative_to(root).as_posix(),
    update_path.relative_to(root).as_posix(),
}
after_tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
                 {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat"}]
after = {p.relative_to(root).as_posix(): digest(p) for p in after_tracked}
changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
unexpected = sorted(changed - allowed)
if unexpected:
    raise SystemExit("unexpected runtime/source changes: " + ", ".join(unexpected))

print("V0.1.68 applied: Abyss loot counting + persistent stats + Telegram /stone /stonereset")
