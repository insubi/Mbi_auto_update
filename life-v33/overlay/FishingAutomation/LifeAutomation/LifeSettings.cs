using System.Text.Json;
using System.Text.Json.Serialization;

namespace FishingAutomation.Life;

internal sealed class LifeSettings
{
    public int WoolTarget { get; set; } = 1000;
    [JsonExtensionData] public Dictionary<string, JsonElement>? Extra { get; set; }
    internal static readonly JsonSerializerOptions JsonOptions = new()
    { PropertyNameCaseInsensitive = true, WriteIndented = true };

    public static LifeSettings Load(string path)
    {
        if (!File.Exists(path)) return new();
        var value = JsonSerializer.Deserialize<LifeSettings>(File.ReadAllText(path), JsonOptions)
            ?? throw new InvalidDataException("생활 설정을 읽을 수 없습니다.");
        if (value.WoolTarget is < 1 or > 9999)
            throw new InvalidDataException("양털 목표 수량은 1~9999여야 합니다.");
        return value;
    }

    public void Save(string path)
    {
        if (WoolTarget is < 1 or > 9999) throw new ArgumentOutOfRangeException(nameof(WoolTarget));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string temp = path + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(this, JsonOptions));
        File.Move(temp, path, true);
    }
}

// All rectangles are game-client pixels. Anchored rectangles are relative to
// the recognized fixed HUD element, never to a character or scene background.
internal sealed class LifeRect
{
    public int X { get; set; }
    public int Y { get; set; }
    public int Width { get; set; }
    public int Height { get; set; }
    public Rectangle Rectangle => new(X, Y, Width, Height);
}

internal sealed class LifeTarget
{
    public string Id { get; set; } = "";
    public string Template { get; set; } = "";
    public LifeRect Search { get; set; } = new();
    public string? Anchor { get; set; }
    public string? Text { get; set; }
    public string? ActiveColor { get; set; }
    public double Threshold { get; set; } = 0.92;
    public double MinimumColorFraction { get; set; } = 0.10;
}

internal sealed class LifeProfile
{
    public bool Calibrated { get; set; }
    public int ClientWidth { get; set; } = 800;
    public int ClientHeight { get; set; } = 1000;
    public int PollMs { get; set; } = 250;
    public int SettleMs { get; set; } = 600;
    public int QuantityPollSeconds { get; set; } = 30;
    public int StepTimeoutSeconds { get; set; } = 30;
    public int TravelTimeoutSeconds { get; set; } = 180;
    public int QueueTimeoutSeconds { get; set; } = 1800;
    public List<LifeTarget> Targets { get; set; } = new();
    public List<LifeRect> QueueSlots { get; set; } = new();
    public LifeRect Slot7Percent { get; set; } = new();
    public LifeRect GatheringRoi { get; set; } = new();
    public List<LifeRect> GaugeExclusions { get; set; } = new();
    public LifeRect GoldenNameOffset { get; set; } = new();
    public LifeRect WoolNameOffset { get; set; } = new();
    public LifeRect WoolCountOffset { get; set; } = new();

    public static readonly string[] Required =
    ["field_hud", "processing_tab", "processing_menu", "processing_active", "cloth_processing",
     "move_facility", "cloth_item", "go_processing", "queue_anchor", "queue_add", "queue_cloth",
     "collect_all", "confirm_green", "materials_short", "close_white", "close_gray", "bag_close",
     "avatar_hud", "life_skills", "shearing", "sheep", "find_nearby", "bag", "items_tab",
     "items_active", "search_icon", "search_input", "search_apply", "golden_wool", "golden_plus",
     "how_to_get", "golden_shearing", "wool"];

    public static LifeProfile Load(string path) =>
        JsonSerializer.Deserialize<LifeProfile>(File.ReadAllText(path), LifeSettings.JsonOptions)
        ?? throw new InvalidDataException("생활 인식 프로필을 읽을 수 없습니다.");

    public List<string> Validate(string baseDir, int width, int height)
    {
        var errors = new List<string>();
        if (!Calibrated) errors.Add("단계별 이미지와 인식 영역 보정이 필요합니다.");
        if (ClientWidth != width || ClientHeight != height) errors.Add("기존 게임 창 설정과 생활 인식 크기가 다릅니다.");
        if (Targets.Select(t => t.Id).Distinct().Count() != Targets.Count) errors.Add("중복된 생활 타깃 ID가 있습니다.");
        foreach (string id in Required)
        {
            var t = Targets.FirstOrDefault(x => x.Id == id);
            if (t is null) { errors.Add($"이미지 설정 없음: {id}"); continue; }
            if (!ValidRect(t.Search.Rectangle)) errors.Add($"탐색 영역 없음: {id}");
            string path = Path.GetFullPath(Path.Combine(baseDir, t.Template));
            if (string.IsNullOrWhiteSpace(t.Template) || !path.StartsWith(Path.GetFullPath(baseDir) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
                || !File.Exists(path)) errors.Add($"템플릿 없음: {id}");
            if (t.Threshold is < 0.7 or > 1) errors.Add($"잘못된 일치 임계값: {id}");
            if (t.Anchor is not null && !Targets.Any(a => a.Id == t.Anchor && a.Anchor is null))
                errors.Add($"고정 HUD 기준점 설정 오류: {id}");
        }
        if (Targets.FirstOrDefault(t => t.Id == "processing_active")?.ActiveColor != "blue")
            errors.Add("가공 메뉴 파란색 활성 확인 설정이 필요합니다.");
        if (Targets.FirstOrDefault(t => t.Id == "items_active")?.ActiveColor != "orange")
            errors.Add("아이템 탭 주황색 활성 확인 설정이 필요합니다.");
        if (Targets.FirstOrDefault(t => t.Id == "confirm_green")?.ActiveColor != "green")
            errors.Add("초록색 확인 버튼 설정이 필요합니다.");
        if (QueueSlots.Count != 7 || QueueSlots.Any(r => !ValidRect(r.Rectangle))) errors.Add("대기열 7칸의 영역 설정이 필요합니다.");
        if (!ValidRect(Slot7Percent.Rectangle)) errors.Add("7번 슬롯 100% OCR 영역이 필요합니다.");
        if (!ValidRect(GatheringRoi.Rectangle)) errors.Add("중앙 채집 게이지 영역이 필요합니다.");
        if (!ValidRect(GoldenNameOffset.Rectangle) || !ValidRect(WoolNameOffset.Rectangle)
            || !ValidRect(WoolCountOffset.Rectangle)) errors.Add("아이템 전체 이름(+ 포함)·수량 영역이 필요합니다.");
        if (PollMs is < 100 or > 2000 || SettleMs is < 300 or > 5000 || QuantityPollSeconds is < 5 or > 300
            || StepTimeoutSeconds is < 5 or > 180 || TravelTimeoutSeconds is < 10 or > 600 || QueueTimeoutSeconds is < 60 or > 7200)
            errors.Add("생활 시간 간격 설정이 잘못되었습니다.");
        return errors;
    }
    private static bool ValidRect(Rectangle r) => r.Width >= 3 && r.Height >= 3;
}
