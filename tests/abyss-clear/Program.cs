using System.Drawing;
namespace DungeonVisionBot;
internal record DetectionResult(bool Found, Rectangle Bounds, double Score, string? ReadText)
{
    public Point Center => new(Bounds.X + Bounds.Width / 2, Bounds.Y + Bounds.Height / 2);
    public static DetectionResult NotFound => new(false, Rectangle.Empty, 0, null);
}
internal class OcrRecognizer
{
    public Task<DetectionResult> FindTextAsync(Bitmap b, Rectangle r, string text, int distance, bool scale, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        bool found = (string?)b.Tag == "clearocr";
        return Task.FromResult(found ? new DetectionResult(true, text.Contains("클리어") ? new(280,210,240,40) : new(300,930,220,25),1,text) : DetectionResult.NotFound);
    }
    public Task<DetectionResult> FindCompactLabelAsync(Bitmap b, Rectangle r, string text, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        return Task.FromResult((string?)b.Tag == "result" ? new DetectionResult(true,new(350,930,100,25),1,text) : DetectionResult.NotFound);
    }
}
internal class Detector
{
    public Task<DetectionResult> DetectAsync(string name, Bitmap b, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        bool title = name == "abyss_dungeon_clear_visual";
        bool touch = name == "abyss_touch_screen";
        bool found = (string?)b.Tag == "clear" && (title || touch);
        return Task.FromResult(found ? new DetectionResult(true,title ? new(280,210,240,40) : new(300,930,220,25),1,name) : DetectionResult.NotFound);
    }
}
internal class Input { public List<Point> Clicks = new(); public void ClickClientPoint(nint h, Point p) => Clicks.Add(p); }
internal static class NativeMethods { public static void SetForegroundWindow(nint h) {} }
internal sealed partial class ScenarioEngine
{
    private string _baseDir = "abyss";
    private Detector _detector = new();
    private Input _input = new();
    private nint _hwnd;
    private Action<string>? Log;
    private Settings _settings = new();
    private Scenario _scenario = new();
    private class Settings { public int PollIntervalMs = 1; public int ClickSettleMs = 1; }
    private class Step { public string Target = "abyss_touch_screen"; }
    private class Scenario { public List<Step> Steps = new() {new()}; }
    private string _phase = "clear";
    private int _advances;
    private bool _transient;
    private Task<Bitmap> CaptureGameWindowAsync(CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        var b = new Bitmap(800,1000) { Tag = _phase };
        if (_transient) { _phase = "result"; _transient = false; }
        else if (_phase == "result" && _input.Clicks.Count > 0) _phase = "combat";
        return Task.FromResult(b);
    }
    private Task<nint> ResolveRequiredGameWindowAsync(CancellationToken ct) { ct.ThrowIfCancellationRequested(); return Task.FromResult((nint)1); }
    private Task<bool> DetectAbyssOutsideWorkflowAsync(Bitmap b, CancellationToken ct) => Task.FromResult(false);
    // Stub the I/O transition; the production method is compiled separately by the app build.
    private Task AdvanceAbyssClearScreenAsync(DetectionResult r, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested(); _advances++; _phase = "result"; return Task.CompletedTask;
    }
    private static void Check(bool value, string message) { if (!value) throw new Exception(message); }
    public static async Task Main()
    {
        foreach (var initial in new[] {"clear", "clearocr", "result"})
        {
            var e = new ScenarioEngine { _phase = initial };
            await e.RetryAbyssResultAsync(CancellationToken.None);
            Check(e._advances == (initial == "result" ? 0 : 1), "clear transition count " + initial);
            Check(e._input.Clicks.Count == 1 && AbyssRetrySafeRoi.Contains(e._input.Clicks[0]), "retry only clicks once inside center ROI");
        }
        var transient = new ScenarioEngine { _transient = true };
        await transient.RetryAbyssResultAsync(CancellationToken.None);
        Check(transient._advances == 0, "one clear frame cannot authorize touch");
        var detector = new ScenarioEngine();
        using var green = new Bitmap(800,1000) { Tag = "clear" };
        using(var g = Graphics.FromImage(green)) g.Clear(Color.LimeGreen);
        Check(!(await detector.DetectAbyssResultRetryAsync(green,CancellationToken.None)).Found, "clear wins over green result fallback");
        green.Tag = "unknown";
        Check((await detector.DetectAbyssResultRetryAsync(green,CancellationToken.None)).Found, "existing green result fallback preserved");
        using var blank = new Bitmap(800,1000);
        Check(!(await detector.DetectAbyssClearPromptAsync(blank,CancellationToken.None)).Found, "blank cannot authorize touch");
        using var wrongSize = new Bitmap(799,1000) {Tag="clear"};
        Check(!(await detector.DetectAbyssClearPromptAsync(wrongSize,CancellationToken.None)).Found, "wrong size cannot authorize touch");
        var cancelled = new ScenarioEngine();
        using var cts = new CancellationTokenSource(); cts.Cancel();
        try { await cancelled.RetryAbyssResultAsync(cts.Token); throw new Exception("cancellation ignored"); }
        catch (OperationCanceledException) { Check(cancelled._advances == 0 && cancelled._input.Clicks.Count == 0, "cancel before input"); }
        Console.WriteLine("ABYSS_CLEAR_REGRESSION_OK: template/OCR recovery, direct result, transient clear, green conflict, blank, size, cancellation");
    }
}
