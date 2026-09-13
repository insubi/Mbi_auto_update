using System.Diagnostics;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text.Json;

namespace FishingAutomation;

internal sealed record ReleaseUpdateInfo(
    string Tag,
    string Name,
    string Notes,
    string AssetName,
    string DownloadUrl,
    long AssetSize,
    string Sha256Url);

internal static class UpdateManager
{
    public const string CurrentVersion = "v33";
    public const string RepositoryOwner = "insubi";
    public const string RepositoryName = "Mbi_auto_update";

    private static readonly HttpClient Http = CreateHttpClient();

    private static HttpClient CreateHttpClient()
    {
        var http = new HttpClient { Timeout = TimeSpan.FromSeconds(20) };
        http.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("MabiAuto", "33"));
        http.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        return http;
    }

    public static async Task<bool> CheckConnectionAsync(CancellationToken ct = default)
    {
        try
        {
            string url = $"https://api.github.com/repos/{RepositoryOwner}/{RepositoryName}/releases/latest";
            using var response = await Http.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, ct);
            return response.IsSuccessStatusCode;
        }
        catch { return false; }
    }

    public static async Task<ReleaseUpdateInfo?> CheckLatestAsync(CancellationToken ct = default)
    {
        string url = $"https://api.github.com/repos/{RepositoryOwner}/{RepositoryName}/releases/latest";
        using var response = await Http.GetAsync(url, ct);
        response.EnsureSuccessStatusCode();
        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        using var json = await JsonDocument.ParseAsync(stream, cancellationToken: ct);

        string tag = json.RootElement.TryGetProperty("tag_name", out var tagNode) ? tagNode.GetString() ?? "" : "";
        if (string.IsNullOrWhiteSpace(tag) || CompareVersions(tag, CurrentVersion) <= 0) return null;

        string name = json.RootElement.TryGetProperty("name", out var nameNode) ? nameNode.GetString() ?? tag : tag;
        string notes = json.RootElement.TryGetProperty("body", out var bodyNode) ? bodyNode.GetString() ?? "" : "";

        var assets = new List<(string Name, string Url, long Size)>();
        if (json.RootElement.TryGetProperty("assets", out var assetNodes) && assetNodes.ValueKind == JsonValueKind.Array)
        {
            foreach (var a in assetNodes.EnumerateArray())
            {
                string assetName = a.TryGetProperty("name", out var n) ? n.GetString() ?? "" : "";
                string download = a.TryGetProperty("browser_download_url", out var d) ? d.GetString() ?? "" : "";
                long size = a.TryGetProperty("size", out var s) && s.TryGetInt64(out long v) ? v : 0;
                if (!string.IsNullOrWhiteSpace(assetName) && !string.IsNullOrWhiteSpace(download)) assets.Add((assetName, download, size));
            }
        }

        var asset = assets.FirstOrDefault(a =>
            a.Name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) &&
            a.Name.Contains("Windows_Lite", StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(asset.Url))
            asset = assets.FirstOrDefault(a =>
                a.Name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) &&
                a.Name.Contains("Windows_Ready", StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(asset.Url))
            asset = assets.FirstOrDefault(a =>
                a.Name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) &&
                (a.Name.Contains("CombinedFishingDungeon", StringComparison.OrdinalIgnoreCase) || a.Name.Contains("Mabi", StringComparison.OrdinalIgnoreCase)));
        if (string.IsNullOrWhiteSpace(asset.Url))
            asset = assets.FirstOrDefault(a => a.Name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(asset.Url))
            throw new InvalidOperationException($"GitHub {tag} 릴리스에 업데이트 ZIP 파일이 없습니다.");

        string shaName = asset.Name + ".sha256";
        string shaUrl = assets.FirstOrDefault(a => a.Name.Equals(shaName, StringComparison.OrdinalIgnoreCase)).Url ?? "";
        if (string.IsNullOrWhiteSpace(shaUrl) && asset.Name.Contains("Windows_Lite", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException($"GitHub {tag} 릴리스에 SHA256 파일({shaName})이 없습니다.");

        return new ReleaseUpdateInfo(tag, name, notes, asset.Name, asset.Url, asset.Size, shaUrl);
    }

    public static async Task<string> DownloadAsync(ReleaseUpdateInfo info, IProgress<int>? progress = null, CancellationToken ct = default)
    {
        string temp = Path.Combine(Path.GetTempPath(), $"MabiAuto_{info.Tag}_{Guid.NewGuid():N}.zip");
        try
        {
            using (var response = await Http.GetAsync(info.DownloadUrl, HttpCompletionOption.ResponseHeadersRead, ct))
            {
                response.EnsureSuccessStatusCode();
                long total = response.Content.Headers.ContentLength ?? info.AssetSize;
                await using var input = await response.Content.ReadAsStreamAsync(ct);
                await using var output = new FileStream(temp, FileMode.Create, FileAccess.Write, FileShare.None, 81920, true);
                var buffer = new byte[81920];
                long readTotal = 0;
                while (true)
                {
                    int read = await input.ReadAsync(buffer, ct);
                    if (read <= 0) break;
                    await output.WriteAsync(buffer.AsMemory(0, read), ct);
                    readTotal += read;
                    if (total > 0) progress?.Report((int)Math.Clamp(readTotal * 100 / total, 0, 100));
                }
                await output.FlushAsync(ct);
            }

            if (!string.IsNullOrWhiteSpace(info.Sha256Url))
            {
                string shaText = await Http.GetStringAsync(info.Sha256Url, ct);
                string expected = shaText.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? "";
                if (expected.Length != 64 || !expected.All(Uri.IsHexDigit))
                    throw new InvalidOperationException("업데이트 SHA256 파일 형식이 올바르지 않습니다.");

                await using var fs = File.OpenRead(temp);
                string actual = Convert.ToHexString(await SHA256.HashDataAsync(fs, ct)).ToLowerInvariant();
                if (!actual.Equals(expected, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("업데이트 파일 SHA256 검증에 실패했습니다. 파일이 손상되었거나 변경되었습니다.");
            }

            progress?.Report(100);
            return temp;
        }
        catch
        {
            try { File.Delete(temp); } catch { }
            throw;
        }
    }

    public static void LaunchUpdater(string zipPath)
    {
        string root = FindPackageRoot();
        string script = Path.Combine(root, "tools", "ApplyUpdate.ps1");
        if (!File.Exists(script)) throw new FileNotFoundException("업데이트 적용 스크립트를 찾지 못했습니다.", script);

        var psi = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = root
        };
        psi.ArgumentList.Add("-NoProfile");
        psi.ArgumentList.Add("-ExecutionPolicy");
        psi.ArgumentList.Add("Bypass");
        psi.ArgumentList.Add("-File");
        psi.ArgumentList.Add(script);
        psi.ArgumentList.Add("-ZipPath");
        psi.ArgumentList.Add(zipPath);
        psi.ArgumentList.Add("-InstallRoot");
        psi.ArgumentList.Add(root);
        psi.ArgumentList.Add("-ProcessId");
        psi.ArgumentList.Add(Environment.ProcessId.ToString());
        var updaterProcess = Process.Start(psi);
        if (updaterProcess is null)
            throw new InvalidOperationException("업데이트 도우미를 실행하지 못했습니다.");
    }

    public static void MarkStartupHealthy()
    {
        try
        {
            string root = FindPackageRoot();
            string pending = Path.Combine(root, ".update_pending");
            if (!File.Exists(pending)) return;
            string token = File.ReadAllText(pending).Trim();
            if (string.IsNullOrWhiteSpace(token)) return;
            File.WriteAllText(Path.Combine(root, ".update_healthy"), token);
        }
        catch { }
    }

    public static string FindPackageRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        for (int i = 0; i < 7 && dir is not null; i++, dir = dir.Parent)
        {
            if (File.Exists(Path.Combine(dir.FullName, "START.cmd")) && Directory.Exists(Path.Combine(dir.FullName, "FishingAutomation")))
                return dir.FullName;
        }
        var baseDir = new DirectoryInfo(AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar));
        if (baseDir.Name.Equals("release", StringComparison.OrdinalIgnoreCase) && baseDir.Parent is not null) return baseDir.Parent.FullName;
        return AppContext.BaseDirectory;
    }

    private static int CompareVersions(string left, string right)
    {
        static int[] Parts(string v)
        {
            string cleaned = v.Trim().TrimStart('v', 'V');
            return cleaned.Split('.', '-', '_')
                .Select(p => int.TryParse(new string(p.TakeWhile(char.IsDigit).ToArray()), out int n) ? n : 0)
                .ToArray();
        }
        int[] a = Parts(left), b = Parts(right);
        int len = Math.Max(a.Length, b.Length);
        for (int i = 0; i < len; i++)
        {
            int av = i < a.Length ? a[i] : 0;
            int bv = i < b.Length ? b[i] : 0;
            if (av != bv) return av.CompareTo(bv);
        }
        return 0;
    }
}
