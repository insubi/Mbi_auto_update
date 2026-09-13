using System.Drawing.Imaging;
using OpenCvSharp;
using OpenCvSharp.Extensions;
using Windows.Globalization;
using Windows.Graphics.Imaging;
using Windows.Media.Ocr;
using Windows.Storage.Streams;
using Rect = System.Drawing.Rectangle;

namespace FishingAutomation.Life;

internal sealed class LifeVision : IDisposable
{
    private readonly string _baseDir;
    private readonly LifeProfile _profile;
    private readonly Dictionary<string, LifeTarget> _targets;
    private readonly Dictionary<string, (Mat Image, Mat? Mask)> _images = new();
    private readonly OcrEngine _ocr;

    public LifeVision(string baseDir, LifeProfile profile)
    {
        _baseDir = baseDir;
        _profile = profile;
        _targets = profile.Targets.ToDictionary(t => t.Id);
        _ocr = OcrEngine.TryCreateFromLanguage(new Language("ko-KR"))
            ?? throw new InvalidOperationException("생활 기능에는 Windows 한국어 OCR이 필요합니다.");
    }

    public Rect? Find(Bitmap frame, string id)
    {
        var search = ResolveSearch(frame, id);
        return search is null ? null : FindAll(frame, id, search.Value, 1).Cast<Rect?>().FirstOrDefault();
    }

    private Rect? ResolveSearch(Bitmap frame, string id)
    {
        var target = _targets[id];
        var search = target.Search.Rectangle;
        if (target.Anchor is { } anchor)
        {
            var a = Find(frame, anchor);
            if (a is null) return null;
            search.Offset(a.Value.Location);
        }
        return search;
    }

    public List<Rect> FindAll(Bitmap frame, string id, Rect search, int max = 20)
    {
        var target = _targets[id];
        var found = new List<Rect>();
        // Reject clipped regions rather than silently cropping away a '+' or number.
        if (!new Rect(System.Drawing.Point.Empty, frame.Size).Contains(search)) return found;
        var (template, mask) = Load(target.Template);
        if (template.Width > search.Width || template.Height > search.Height) return found;
        using var crop = frame.Clone(search, PixelFormat.Format24bppRgb);
        using var bgr = BitmapConverter.ToMat(crop);
        using var gray = new Mat();
        Cv2.CvtColor(bgr, gray, ColorConversionCodes.BGR2GRAY);
        using var result = new Mat();
        if (mask is null) Cv2.MatchTemplate(gray, template, result, TemplateMatchModes.CCoeffNormed);
        else Cv2.MatchTemplate(gray, template, result, TemplateMatchModes.CCorrNormed, mask);
        for (int i = 0; i < max; i++)
        {
            Cv2.MinMaxLoc(result, out _, out double score, out _, out OpenCvSharp.Point point);
            if (!double.IsFinite(score) || score < target.Threshold) break;
            var hit = new Rect(search.X + point.X, search.Y + point.Y, template.Width, template.Height);
            if (target.ActiveColor is null || ColorFraction(frame, hit, target.ActiveColor) >= target.MinimumColorFraction)
                found.Add(hit);
            // Non-maximum suppression allows exact-name verification of every item candidate.
            int left = Math.Max(0, point.X - template.Width / 2), top = Math.Max(0, point.Y - template.Height / 2);
            int right = Math.Min(result.Width, point.X + template.Width / 2 + 1);
            int bottom = Math.Min(result.Height, point.Y + template.Height / 2 + 1);
            using var removed = new Mat(result, new OpenCvSharp.Rect(left, top, right - left, bottom - top));
            removed.SetTo(Scalar.All(-1));
        }
        return found;
    }

    public bool QueueCloth(Bitmap frame, int index, Rect anchor) =>
        FindAll(frame, "queue_cloth", Offset(_profile.QueueSlots[index].Rectangle, anchor), 1).Count > 0;

    public async Task<bool> Slot7CompleteAsync(Bitmap frame, Rect anchor, CancellationToken ct)
    {
        var lines = await ReadAsync(frame, Offset(_profile.Slot7Percent.Rectangle, anchor), 3, ct);
        return lines.Count == 1 && LifeRules.Complete(lines[0].Text);
    }

    public async Task<bool> MaterialsShortAsync(Bitmap frame, CancellationToken ct)
    {
        var match = Find(frame, "materials_short");
        if (match is null) return false;
        var search = ResolveSearch(frame, "materials_short");
        if (search is null) return false;
        var lines = await ReadAsync(frame, search.Value, 2, ct);
        return lines.Any(x => LifeRules.NormalizeLabel(x.Text).TrimEnd('.', '。') == "재료가부족합니다");
    }

    public async Task<Rect?> ExactItemAsync(Bitmap frame, bool golden, CancellationToken ct)
    {
        string id = golden ? "golden_wool" : "wool";
        string name = golden ? "황금 양털" : "양털";
        var target = _targets[id];
        var area = target.Search.Rectangle;
        if (target.Anchor is { } anchor)
        {
            var a = Find(frame, anchor);
            if (a is null) return null;
            area.Offset(a.Value.Location);
        }
        var valid = new List<Rect>();
        foreach (var icon in FindAll(frame, id, area))
        {
            var nameArea = Offset((golden ? _profile.GoldenNameOffset : _profile.WoolNameOffset).Rectangle, icon);
            if (golden && FindAll(frame, "golden_plus", nameArea, 1).Count != 0) continue;
            var lines = await ReadAsync(frame, nameArea, 2, ct);
            if (lines.Count == 1 && !lines[0].Clipped && LifeRules.ExactItem(lines[0].Text, name)) valid.Add(icon);
        }
        // Do not guess between multiple indistinguishable stacks/results.
        return valid.Count == 1 ? valid[0] : null;
    }

    public async Task<int?> WoolQuantityAsync(Bitmap frame, CancellationToken ct)
    {
        var item = await ExactItemAsync(frame, false, ct);
        if (item is null) return null;
        var area = Offset(_profile.WoolCountOffset.Rectangle, item.Value);
        var first = await ReadAsync(frame, area, 2, ct);
        var second = await ReadAsync(frame, area, 3, ct);
        if (first.Count != 1 || second.Count != 1 || first[0].Clipped || second[0].Clipped) return null;
        var a = LifeRules.ReadQuantity(first[0].Text);
        var b = LifeRules.ReadQuantity(second[0].Text);
        return a is not null && a == b ? a : null;
    }

    public GaugeSample? Gauge(Bitmap frame)
    {
        Rect roi = _profile.GatheringRoi.Rectangle;
        if (!new Rect(System.Drawing.Point.Empty, frame.Size).Contains(roi)) return null;
        using var crop = frame.Clone(roi, PixelFormat.Format24bppRgb);
        using var bgr = BitmapConverter.ToMat(crop);
        using var hsv = new Mat();
        using var mask = new Mat();
        Cv2.CvtColor(bgr, hsv, ColorConversionCodes.BGR2HSV);
        Cv2.InRange(hsv, new Scalar(35, 85, 85), new Scalar(90, 255, 255), mask);
        foreach (var exclusion in _profile.GaugeExclusions)
        {
            Rect cut = Rect.Intersect(roi, exclusion.Rectangle);
            if (cut.IsEmpty) continue;
            using var excluded = new Mat(mask, new OpenCvSharp.Rect(cut.X - roi.X, cut.Y - roi.Y, cut.Width, cut.Height));
            excluded.SetTo(Scalar.All(0));
        }
        Cv2.FindContours(mask, out OpenCvSharp.Point[][] contours, out _, RetrievalModes.External, ContourApproximationModes.ApproxSimple);
        var bars = contours.Select(Cv2.BoundingRect)
            .Where(r => r.Height is >= 2 and <= 22 && r.Width >= 12 && r.Width >= r.Height * 3)
            .Where(r => { using var pixels = new Mat(mask, r); return Cv2.CountNonZero(pixels) >= r.Width * r.Height * 0.65; })
            .ToList();
        // Ambiguous moving objects cannot prove a gathering bar.
        if (bars.Count != 1) return null;
        var bar = bars[0];
        return new GaugeSample(roi.X + bar.X, roi.Y + bar.Y, bar.Width);
    }

    internal readonly record struct OcrLine(string Text, Rect Bounds, bool Clipped);

    public async Task<List<OcrLine>> ReadAsync(Bitmap frame, Rect roi, int scale, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        if (roi.Width < 2 || roi.Height < 2 || !new Rect(System.Drawing.Point.Empty, frame.Size).Contains(roi)) return new();
        using var crop = frame.Clone(roi, PixelFormat.Format24bppRgb);
        int longest = Math.Max(crop.Width, crop.Height);
        scale = Math.Clamp(scale, 1, Math.Max(1, (int)OcrEngine.MaxImageDimension / longest));
        using var enlarged = new Bitmap(crop.Width * scale, crop.Height * scale, PixelFormat.Format24bppRgb);
        using (var g = Graphics.FromImage(enlarged))
        {
            g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.NearestNeighbor;
            g.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.Half;
            g.DrawImage(crop, new Rect(0, 0, enlarged.Width, enlarged.Height));
        }
        using var png = new MemoryStream();
        enlarged.Save(png, ImageFormat.Png);
        using var stream = new InMemoryRandomAccessStream();
        using (var writer = new DataWriter(stream))
        {
            writer.WriteBytes(png.ToArray());
            await writer.StoreAsync();
            await writer.FlushAsync();
            writer.DetachStream();
        }
        stream.Seek(0);
        var decoder = await BitmapDecoder.CreateAsync(stream);
        using var software = await decoder.GetSoftwareBitmapAsync(BitmapPixelFormat.Bgra8, BitmapAlphaMode.Premultiplied);
        var result = await _ocr.RecognizeAsync(software);
        ct.ThrowIfCancellationRequested();
        var lines = new List<OcrLine>();
        foreach (var line in result.Lines.Where(l => l.Words.Count > 0))
        {
            double left = line.Words.Min(w => w.BoundingRect.X), top = line.Words.Min(w => w.BoundingRect.Y);
            double right = line.Words.Max(w => w.BoundingRect.X + w.BoundingRect.Width), bottom = line.Words.Max(w => w.BoundingRect.Y + w.BoundingRect.Height);
            bool clipped = left <= 1 || top <= 1 || right >= enlarged.Width - 1 || bottom >= enlarged.Height - 1;
            var bounds = Rect.FromLTRB(roi.X + (int)(left / scale), roi.Y + (int)(top / scale),
                roi.X + (int)Math.Ceiling(right / scale), roi.Y + (int)Math.Ceiling(bottom / scale));
            lines.Add(new OcrLine(line.Text, bounds, clipped));
        }
        return lines;
    }

    public static Rect Offset(Rect relative, Rect anchor) { relative.Offset(anchor.Location); return relative; }

    private (Mat Image, Mat? Mask) Load(string file)
    {
        if (_images.TryGetValue(file, out var cached)) return cached;
        using var raw = Cv2.ImRead(Path.Combine(_baseDir, file), ImreadModes.Unchanged);
        if (raw.Empty()) throw new InvalidDataException($"생활 템플릿을 읽을 수 없습니다: {file}");
        var gray = new Mat();
        Mat? mask = null;
        if (raw.Channels() == 4)
        {
            Cv2.CvtColor(raw, gray, ColorConversionCodes.BGRA2GRAY);
            mask = new Mat();
            Cv2.ExtractChannel(raw, mask, 3);
            Cv2.Threshold(mask, mask, 127, 255, ThresholdTypes.Binary);
            if (Cv2.CountNonZero(mask) < 20) { gray.Dispose(); mask.Dispose(); throw new InvalidDataException($"유효 픽셀이 부족한 템플릿: {file}"); }
        }
        else if (raw.Channels() == 3) Cv2.CvtColor(raw, gray, ColorConversionCodes.BGR2GRAY);
        else raw.CopyTo(gray);
        _images.Add(file, (gray, mask));
        return (gray, mask);
    }

    private static double ColorFraction(Bitmap frame, Rect region, string color)
    {
        using var crop = frame.Clone(region, PixelFormat.Format24bppRgb);
        using var bgr = BitmapConverter.ToMat(crop);
        using var hsv = new Mat();
        using var mask = new Mat();
        Cv2.CvtColor(bgr, hsv, ColorConversionCodes.BGR2HSV);
        var (lower, upper) = color switch
        {
            "blue" => (new Scalar(90, 90, 70), new Scalar(130, 255, 255)),
            "orange" => (new Scalar(4, 100, 90), new Scalar(27, 255, 255)),
            "green" => (new Scalar(35, 85, 85), new Scalar(90, 255, 255)),
            _ => throw new InvalidDataException("잘못된 활성 색상: " + color)
        };
        Cv2.InRange(hsv, lower, upper, mask);
        return (double)Cv2.CountNonZero(mask) / Math.Max(1, region.Width * region.Height);
    }

    public void Dispose()
    {
        foreach (var (image, mask) in _images.Values) { image.Dispose(); mask?.Dispose(); }
        _images.Clear();
    }
}
