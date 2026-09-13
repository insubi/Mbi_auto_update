#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read_text(path: Path):
    raw = path.read_bytes()
    enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    return raw.decode("utf-8-sig"), enc


def write_text(path: Path, text: str, enc: str):
    path.write_text(text, encoding=enc)


def replace_once(path: Path, pattern: str, replacement: str, flags=0):
    text, enc = read_text(path)
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"required marker missing: {path}")
    write_text(path, new, enc)


# Version bump from v37.
replace_once(
    app / "UpdateManager.cs",
    r'public const string CurrentVersion = "v37";',
    'public const string CurrentVersion = "v38";',
)

# Remove the GDI+ Bitmap.Clone/new Bitmap(templatePath) path from dungeon/Abyss
# template matching. On some Windows/GDI+ combinations it throws the generic
# ArgumentException "Parameter is not valid." before the first Abyss click.
# Keep System.Drawing only for the captured frame; do ROI and template loading in OpenCV.
template_matcher = r'''using OpenCvSharp;
using OpenCvSharp.Extensions;

namespace DungeonVisionBot;

internal sealed class TemplateMatcher
{
    private readonly string _baseDir;
    public TemplateMatcher(string baseDir) => _baseDir = baseDir;

    public DetectionResult Find(Bitmap frame, Rectangle roi, string templatePath, double threshold)
        => FindMultiScale(frame, roi, templatePath, threshold, 1.0, 1.0, 0.10);

    public DetectionResult FindMultiScale(
        Bitmap frame,
        Rectangle roi,
        string templatePath,
        double threshold,
        double minScale,
        double maxScale,
        double step)
    {
        string fullPath = Path.IsPathRooted(templatePath)
            ? templatePath
            : Path.Combine(_baseDir, templatePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(fullPath)) return DetectionResult.NotFound;
        if (frame.Width < 2 || frame.Height < 2) return DetectionResult.NotFound;

        Rectangle safeRoi = Rectangle.Intersect(
            new Rectangle(0, 0, frame.Width, frame.Height), roi);
        if (safeRoi.Width < 2 || safeRoi.Height < 2) return DetectionResult.NotFound;

        minScale = Math.Clamp(minScale, 0.20, 3.00);
        maxScale = Math.Clamp(maxScale, minScale, 3.00);
        step = Math.Clamp(step, 0.02, 0.50);

        using var frameMat = BitmapConverter.ToMat(frame);
        if (frameMat.Empty()) return DetectionResult.NotFound;

        using var frameGray = new Mat();
        if (frameMat.Channels() == 4)
            Cv2.CvtColor(frameMat, frameGray, ColorConversionCodes.BGRA2GRAY);
        else if (frameMat.Channels() == 3)
            Cv2.CvtColor(frameMat, frameGray, ColorConversionCodes.BGR2GRAY);
        else
            frameMat.CopyTo(frameGray);

        var cvRoi = new OpenCvSharp.Rect(safeRoi.X, safeRoi.Y, safeRoi.Width, safeRoi.Height);
        using var srcGray = new Mat(frameGray, cvRoi);
        using var tplGrayOriginal = Cv2.ImRead(fullPath, ImreadModes.Grayscale);
        if (tplGrayOriginal.Empty()) return DetectionResult.NotFound;

        double bestScore = double.MinValue;
        OpenCvSharp.Point bestLoc = default;
        int bestW = 0;
        int bestH = 0;

        var scales = new List<double>();
        for (double scale = minScale; scale <= maxScale + 1e-9; scale += step)
            scales.Add(scale);
        if (scales.Count == 0 || Math.Abs(scales[^1] - maxScale) > 1e-6)
            scales.Add(maxScale);

        foreach (double scale in scales)
        {
            int w = Math.Max(8, (int)Math.Round(tplGrayOriginal.Width * scale));
            int h = Math.Max(8, (int)Math.Round(tplGrayOriginal.Height * scale));
            if (w > srcGray.Width || h > srcGray.Height) continue;

            using var tplGray = new Mat();
            if (w == tplGrayOriginal.Width && h == tplGrayOriginal.Height)
                tplGrayOriginal.CopyTo(tplGray);
            else
                Cv2.Resize(
                    tplGrayOriginal,
                    tplGray,
                    new OpenCvSharp.Size(w, h),
                    0,
                    0,
                    scale < 1.0 ? InterpolationFlags.Area : InterpolationFlags.Cubic);

            using var result = new Mat();
            Cv2.MatchTemplate(srcGray, tplGray, result, TemplateMatchModes.CCoeffNormed);
            Cv2.MinMaxLoc(result, out _, out double maxVal, out _, out OpenCvSharp.Point maxLoc);

            if (maxVal > bestScore)
            {
                bestScore = maxVal;
                bestLoc = maxLoc;
                bestW = w;
                bestH = h;
            }
        }

        if (bestW <= 0 || bestH <= 0 || bestScore < threshold)
            return DetectionResult.NotFound;

        var bounds = new Rectangle(
            safeRoi.X + bestLoc.X,
            safeRoi.Y + bestLoc.Y,
            bestW,
            bestH);
        return new DetectionResult(true, bounds, bestScore, null);
    }
}
'''
write_text(app / "Dungeon" / "TemplateMatcher.cs", template_matcher, "utf-8")

# Make the in-app updater ignore standalone/test releases such as life-cloth-v1.
# Query the releases list and choose the highest normal v<number> tag.
p = app / "UpdateManager.cs"
text, enc = read_text(p)
check_latest = r'''    public static async Task<ReleaseUpdateInfo?> CheckLatestAsync(CancellationToken ct = default)
    {
        string url = $"https://api.github.com/repos/{RepositoryOwner}/{RepositoryName}/releases?per_page=30";
        using var response = await Http.GetAsync(url, ct);
        response.EnsureSuccessStatusCode();
        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        using var json = await JsonDocument.ParseAsync(stream, cancellationToken: ct);

        if (json.RootElement.ValueKind != JsonValueKind.Array) return null;

        JsonElement release = default;
        string tag = "";
        foreach (var candidate in json.RootElement.EnumerateArray())
        {
            bool draft = candidate.TryGetProperty("draft", out var d) && d.ValueKind == JsonValueKind.True;
            bool prerelease = candidate.TryGetProperty("prerelease", out var p) && p.ValueKind == JsonValueKind.True;
            if (draft || prerelease) continue;

            string candidateTag = candidate.TryGetProperty("tag_name", out var t) ? t.GetString() ?? "" : "";
            if (!IsMainReleaseTag(candidateTag)) continue;

            if (string.IsNullOrWhiteSpace(tag) || CompareVersions(candidateTag, tag) > 0)
            {
                tag = candidateTag;
                release = candidate;
            }
        }

        if (string.IsNullOrWhiteSpace(tag) || CompareVersions(tag, CurrentVersion) <= 0) return null;

        string name = release.TryGetProperty("name", out var nameNode) ? nameNode.GetString() ?? tag : tag;
        string notes = release.TryGetProperty("body", out var bodyNode) ? bodyNode.GetString() ?? "" : "";

        var assets = new List<(string Name, string Url, long Size)>();
        if (release.TryGetProperty("assets", out var assetNodes) && assetNodes.ValueKind == JsonValueKind.Array)
        {
            foreach (var a in assetNodes.EnumerateArray())
            {
                string assetName = a.TryGetProperty("name", out var n) ? n.GetString() ?? "" : "";
                string download = a.TryGetProperty("browser_download_url", out var dl) ? dl.GetString() ?? "" : "";
                long size = a.TryGetProperty("size", out var s) && s.TryGetInt64(out long v) ? v : 0;
                if (!string.IsNullOrWhiteSpace(assetName) && !string.IsNullOrWhiteSpace(download))
                    assets.Add((assetName, download, size));
            }
        }

        var asset = assets.FirstOrDefault(a =>
            a.Name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) &&
            a.Name.Contains("Windows_Lite", StringComparison.OrdinalIgnoreCase) &&
            a.Name.Contains(tag, StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(asset.Url))
            asset = assets.FirstOrDefault(a =>
                a.Name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) &&
                a.Name.Contains("Windows_Lite", StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(asset.Url))
            asset = assets.FirstOrDefault(a =>
                a.Name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) &&
                a.Name.Contains("Windows_Ready", StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(asset.Url))
            throw new InvalidOperationException($"GitHub {tag} 릴리스에 Windows 업데이트 ZIP 파일이 없습니다.");

        string shaName = asset.Name + ".sha256";
        string shaUrl = assets.FirstOrDefault(a => a.Name.Equals(shaName, StringComparison.OrdinalIgnoreCase)).Url ?? "";
        if (string.IsNullOrWhiteSpace(shaUrl))
            throw new InvalidOperationException($"GitHub {tag} 릴리스에 SHA256 파일({shaName})이 없습니다.");

        return new ReleaseUpdateInfo(tag, name, notes, asset.Name, asset.Url, asset.Size, shaUrl);
    }

    private static bool IsMainReleaseTag(string tag)
    {
        if (string.IsNullOrWhiteSpace(tag) || tag.Length < 2) return false;
        if (tag[0] is not ('v' or 'V')) return false;
        bool hasDigit = false;
        for (int i = 1; i < tag.Length; i++)
        {
            char c = tag[i];
            if (char.IsDigit(c)) { hasDigit = true; continue; }
            if (c == '.') continue;
            return false;
        }
        return hasDigit;
    }

'''
pattern = r'    public static async Task<ReleaseUpdateInfo\?> CheckLatestAsync\(CancellationToken ct = default\)\s*\{.*?\n    \}\n\n(?=    public static async Task<string> DownloadAsync)'
text, count = re.subn(pattern, check_latest, text, count=1, flags=re.S)
if count != 1:
    raise RuntimeError("CheckLatestAsync block not found")
# Connection check must not depend on whichever release GitHub labels latest.
text = text.replace(
    'string url = $"https://api.github.com/repos/{RepositoryOwner}/{RepositoryName}/releases/latest";',
    'string url = $"https://api.github.com/repos/{RepositoryOwner}/{RepositoryName}/releases?per_page=1";',
    1,
)
write_text(p, text, enc)

# Keep the macro title distinct from the game title.
p = app / "MainForm.cs"
text, enc = read_text(p)
text = re.sub(r'Text\s*=\s*"MABI AUTO[^\"]*";', 'Text = "MABI AUTO · v38";', text, count=1)
write_text(p, text, enc)

# Cosmetic dashboard version labels.
p = app / "MainForm.Dashboard.cs"
if p.exists():
    text, enc = read_text(p)
    text = re.sub(r'Dashboard v\d+', 'Dashboard v38', text)
    text = re.sub(r'v\d+\s*\|\s*Mabi Auto', 'v38  |  Mabi Auto', text)
    write_text(p, text, enc)

# Windows file/product version.
p = app / "FishingAutomation.csproj"
text, enc = read_text(p)
for tag_name, value in {
    "Version": "38.0.0",
    "AssemblyVersion": "38.0.0.0",
    "FileVersion": "38.0.0.0",
}.items():
    pattern = rf'<{tag_name}>[^<]+</{tag_name}>'
    replacement = f'<{tag_name}>{value}</{tag_name}>'
    if re.search(pattern, text):
        text = re.sub(pattern, replacement, text, count=1)
    else:
        text = text.replace("<PropertyGroup>", "<PropertyGroup>\n    " + replacement, 1)
write_text(p, text, enc)

(root / "CHANGES_v38_ABYSS_GDIPLUS_FIX.txt").write_text(
    "MABI AUTO v38 - Abyss first-step image matching fix\n\n"
    "- Fixes immediate 'Parameter is not valid.' at Abyss step 1 / abyss_menu\n"
    "- Removes GDI+ Bitmap.Clone and Bitmap(templatePath) from Dungeon/Abyss template matching\n"
    "- Loads template images directly with OpenCV and performs ROI in Mat space\n"
    "- Main updater now ignores standalone/test releases such as life-cloth-v1\n"
    "- Main updater only selects normal numeric tags such as v38, v39, ...\n"
    "- v37/v32-based Fishing, Dungeon and Abyss behavior otherwise preserved\n",
    encoding="utf-8",
)

print("v38 applied: OpenCV-only Abyss template ROI and main-release-only updater")
