#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0134_runtime_error_upload.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
main_path = app / "MainForm.cs"
refui_path = app / "MainForm.ReferenceUI.cs"
csproj_path = app / "FishingAutomation.csproj"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)

main = read(main_path)
main = replace_once(
    main,
    '''    private readonly AppLog _log;\n    private readonly TelegramNotifier _notifier;\n    private readonly WatchdogClient _watchdog;\n''',
    '''    private readonly AppLog _log;\n    private readonly TelegramNotifier _notifier;\n    private readonly RuntimeErrorUploader _errorUploader;\n    private readonly WatchdogClient _watchdog;\n''',
    "MainForm uploader field",
)
main = replace_once(
    main,
    '''        _log = new AppLog(Path.Combine(baseDir, cfg.LogFile), cfg.LogMaxBytes);\n        _notifier = new TelegramNotifier(Path.Combine(baseDir, "notification.json"), _log);\n        _watchdog = new WatchdogClient(baseDir);\n''',
    '''        string runtimeLogPath = Path.Combine(baseDir, cfg.LogFile);\n        _log = new AppLog(runtimeLogPath, cfg.LogMaxBytes);\n        _notifier = new TelegramNotifier(Path.Combine(baseDir, "notification.json"), _log);\n        _errorUploader = new RuntimeErrorUploader(_log, runtimeLogPath);\n        _watchdog = new WatchdogClient(baseDir);\n''',
    "MainForm uploader init",
)
old_alert_count = main.count("_notifier.SendAlertAsync(")
if old_alert_count < 5:
    raise RuntimeError(f"expected existing runtime alerts, found {old_alert_count}")
main = main.replace("_notifier.SendAlertAsync(", "SendRuntimeAlertAsync(")
write(main_path, main)

refui = read(refui_path)
refui = replace_once(
    refui,
    '''            AddButton("텔레그램", new(18, 371, 170, 59), owner.ShowTelegramSettings, "bell", "nav");\n            AddButton("미니 모드", new(18, 991, 170, 46), () => owner.ToggleMini(true), "", "quiet");\n''',
    '''            AddButton("텔레그램", new(18, 371, 170, 59), owner.ShowTelegramSettings, "bell", "nav");\n            AddButton("에러 전송", new(18, 441, 170, 59), owner.ShowErrorUploadSettings, "send", "nav");\n            AddButton("미니 모드", new(18, 991, 170, 46), () => owner.ToggleMini(true), "", "quiet");\n''',
    "reference UI error upload button",
)
write(refui_path, refui)

csproj = read(csproj_path)
if "System.Security.Cryptography.ProtectedData" not in csproj:
    csproj = replace_once(
        csproj,
        '''    <PackageReference Include="OpenCvSharp4.Extensions" Version="4.13.0.20260627" />\n''',
        '''    <PackageReference Include="OpenCvSharp4.Extensions" Version="4.13.0.20260627" />\n    <PackageReference Include="System.Security.Cryptography.ProtectedData" Version="8.0.0" />\n''',
        "ProtectedData package",
    )
write(csproj_path, csproj)

uploader = r'''using System.Drawing.Imaging;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using DungeonVisionBot;

namespace FishingAutomation;

public sealed class ErrorUploadSettings
{
    public bool Enabled { get; set; } = false;
    public string Repository { get; set; } = "";
    public string Branch { get; set; } = "main";
    public bool SendScreenshot { get; set; } = true;
    public int RecentLogLines { get; set; } = 300;
    public string ProtectedToken { get; set; } = "";
}

public sealed class RuntimeErrorReport
{
    public DateTimeOffset Time { get; set; }
    public string Version { get; set; } = "";
    public string Title { get; set; } = "";
    public string Detail { get; set; } = "";
    public string Mode { get; set; } = "";
    public string SelectedTarget { get; set; } = "";
    public string ScreenStatus { get; set; } = "";
}

// RUNTIME_ERROR_GITHUB_UPLOAD_V9
// Uploads only explicit runtime alert events. The fine-grained PAT is encrypted with
// Windows DPAPI for the current Windows account and is never written to the app log.
public sealed class RuntimeErrorUploader
{
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(35) };
    private readonly AppLog _log;
    private readonly string _runtimeLogPath;
    private readonly string _settingsPath;
    private readonly SemaphoreSlim _uploadGate = new(1, 1);

    public RuntimeErrorUploader(AppLog log, string runtimeLogPath)
    {
        _log = log;
        _runtimeLogPath = runtimeLogPath;
        string dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MabiAuto");
        Directory.CreateDirectory(dir);
        _settingsPath = Path.Combine(dir, "error-upload.json");
    }

    public ErrorUploadSettings Settings => LoadSettings();
    public bool HasStoredToken => !string.IsNullOrWhiteSpace(LoadSettings().ProtectedToken);

    public void SaveSettings(ErrorUploadSettings settings, string? newToken)
    {
        var old = LoadSettings();
        if (string.IsNullOrWhiteSpace(newToken))
            settings.ProtectedToken = old.ProtectedToken;
        else
            settings.ProtectedToken = ProtectToken(newToken.Trim());

        settings.Repository = NormalizeRepository(settings.Repository);
        settings.Branch = string.IsNullOrWhiteSpace(settings.Branch) ? "main" : settings.Branch.Trim();
        settings.RecentLogLines = Math.Clamp(settings.RecentLogLines, 50, 1000);
        Directory.CreateDirectory(Path.GetDirectoryName(_settingsPath)!);
        string temp = _settingsPath + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(settings, new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
        File.Move(temp, _settingsPath, true);
    }

    public async Task<(bool Ok, string Message)> TestConnectionAsync(string repository, string branch, string? tokenOverride)
    {
        try
        {
            string repo = NormalizeRepository(repository);
            string useBranch = string.IsNullOrWhiteSpace(branch) ? "main" : branch.Trim();
            string? token = string.IsNullOrWhiteSpace(tokenOverride) ? GetStoredToken() : tokenOverride.Trim();
            if (!IsValidRepository(repo)) return (false, "저장소는 owner/repo 형식으로 입력하세요.");
            if (string.IsNullOrWhiteSpace(token)) return (false, "Fine-grained token을 입력하세요.");

            using var repoRequest = CreateRequest(HttpMethod.Get, $"https://api.github.com/repos/{repo}", token);
            using var repoResponse = await Http.SendAsync(repoRequest);
            if (!repoResponse.IsSuccessStatusCode)
                return (false, $"저장소 접근 실패: HTTP {(int)repoResponse.StatusCode}");

            using var branchRequest = CreateRequest(HttpMethod.Get, $"https://api.github.com/repos/{repo}/branches/{Uri.EscapeDataString(useBranch)}", token);
            using var branchResponse = await Http.SendAsync(branchRequest);
            if (!branchResponse.IsSuccessStatusCode)
                return (false, $"브랜치 '{useBranch}' 확인 실패: HTTP {(int)branchResponse.StatusCode} · README 등으로 저장소를 먼저 초기화하세요.");

            return (true, $"연결 성공: {repo} / {useBranch}");
        }
        catch (Exception ex)
        {
            return (false, "연결 실패: " + ex.Message);
        }
    }

    public async Task UploadAlertAsync(RuntimeErrorReport report, bool requestedScreenshot = true)
    {
        var settings = LoadSettings();
        if (!settings.Enabled) return;
        string repo = NormalizeRepository(settings.Repository);
        string? token = GetStoredToken(settings);
        if (!IsValidRepository(repo) || string.IsNullOrWhiteSpace(token))
        {
            _log.Write("[에러전송] 설정이 불완전하여 업로드하지 않았습니다.");
            return;
        }

        await _uploadGate.WaitAsync();
        try
        {
            string safeTitle = SanitizePathPart(report.Title);
            string unique = Guid.NewGuid().ToString("N")[..6];
            string folder = $"runtime-errors/{report.Time:yyyy-MM-dd}/{report.Time:yyyyMMdd_HHmmss_fff}_{safeTitle}_{unique}";
            string branch = string.IsNullOrWhiteSpace(settings.Branch) ? "main" : settings.Branch.Trim();

            var summary = new
            {
                schema = 1,
                source = "runtime",
                version = report.Version,
                timeLocal = report.Time.ToString("O"),
                timeUtc = report.Time.ToUniversalTime().ToString("O"),
                title = report.Title,
                detail = report.Detail,
                mode = report.Mode,
                selectedTarget = report.SelectedTarget,
                screenStatus = report.ScreenStatus,
                processId = Environment.ProcessId
            };
            byte[] summaryBytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(summary, new JsonSerializerOptions { WriteIndented = true }));
            await PutFileAsync(repo, branch, token, $"{folder}/summary.json", summaryBytes, $"runtime error: {report.Title}");

            string recent = ReadRecentLog(settings.RecentLogLines);
            if (!string.IsNullOrWhiteSpace(recent))
                await PutFileAsync(repo, branch, token, $"{folder}/recent.log", Encoding.UTF8.GetBytes(recent), $"runtime log: {report.Title}");

            if (requestedScreenshot && settings.SendScreenshot)
            {
                byte[]? screenshot = CaptureGameWindowPng();
                if (screenshot is not null)
                    await PutFileAsync(repo, branch, token, $"{folder}/screen.png", screenshot, $"runtime screenshot: {report.Title}");
            }

            _log.Write($"[에러전송] 업로드 완료: {repo}/{folder}");
        }
        catch (Exception ex)
        {
            _log.Write("[에러전송] 실패: " + ex.Message);
        }
        finally
        {
            _uploadGate.Release();
        }
    }

    private async Task PutFileAsync(string repo, string branch, string token, string path, byte[] data, string message)
    {
        string encodedPath = string.Join("/", path.Split('/', StringSplitOptions.RemoveEmptyEntries).Select(Uri.EscapeDataString));
        string url = $"https://api.github.com/repos/{repo}/contents/{encodedPath}";
        string json = JsonSerializer.Serialize(new
        {
            message,
            content = Convert.ToBase64String(data),
            branch
        });
        using var request = CreateRequest(HttpMethod.Put, url, token);
        request.Content = new StringContent(json, Encoding.UTF8, "application/json");
        using var response = await Http.SendAsync(request);
        if (!response.IsSuccessStatusCode)
        {
            string body = await response.Content.ReadAsStringAsync();
            if (body.Length > 300) body = body[..300];
            throw new HttpRequestException($"GitHub 업로드 HTTP {(int)response.StatusCode}: {body}");
        }
    }

    private static HttpRequestMessage CreateRequest(HttpMethod method, string url, string token)
    {
        var request = new HttpRequestMessage(method, url);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
        request.Headers.UserAgent.ParseAdd("MabiAuto/0.1.34");
        return request;
    }

    private ErrorUploadSettings LoadSettings()
    {
        try
        {
            if (!File.Exists(_settingsPath)) return new();
            return JsonSerializer.Deserialize<ErrorUploadSettings>(File.ReadAllText(_settingsPath), new JsonSerializerOptions { PropertyNameCaseInsensitive = true }) ?? new();
        }
        catch { return new(); }
    }

    private string? GetStoredToken() => GetStoredToken(LoadSettings());

    private static string? GetStoredToken(ErrorUploadSettings settings)
    {
        if (string.IsNullOrWhiteSpace(settings.ProtectedToken)) return null;
        try
        {
            byte[] protectedBytes = Convert.FromBase64String(settings.ProtectedToken);
            byte[] clear = ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.CurrentUser);
            return Encoding.UTF8.GetString(clear);
        }
        catch { return null; }
    }

    private static string ProtectToken(string token)
    {
        byte[] clear = Encoding.UTF8.GetBytes(token);
        byte[] protectedBytes = ProtectedData.Protect(clear, null, DataProtectionScope.CurrentUser);
        return Convert.ToBase64String(protectedBytes);
    }

    private string ReadRecentLog(int lines)
    {
        try
        {
            if (!File.Exists(_runtimeLogPath)) return "";
            return string.Join(Environment.NewLine, File.ReadLines(_runtimeLogPath).TakeLast(Math.Clamp(lines, 50, 1000)));
        }
        catch { return ""; }
    }

    private static byte[]? CaptureGameWindowPng()
    {
        try
        {
            nint hwnd = WindowTools.FindRequiredGameWindow();
            if (hwnd == 0) return null;
            Rectangle rect = WindowTools.GetClientScreenRect(hwnd);
            if (rect.Width <= 0 || rect.Height <= 0) return null;
            using var bmp = new Bitmap(rect.Width, rect.Height, PixelFormat.Format32bppArgb);
            using (Graphics g = Graphics.FromImage(bmp))
                g.CopyFromScreen(rect.Left, rect.Top, 0, 0, rect.Size, CopyPixelOperation.SourceCopy);
            using var ms = new MemoryStream();
            bmp.Save(ms, ImageFormat.Png);
            return ms.ToArray();
        }
        catch { return null; }
    }

    private static string NormalizeRepository(string value)
    {
        string repo = (value ?? "").Trim();
        if (repo.StartsWith("https://github.com/", StringComparison.OrdinalIgnoreCase))
            repo = repo["https://github.com/".Length..];
        return repo.Trim().Trim('/');
    }

    private static bool IsValidRepository(string repo)
    {
        string[] parts = repo.Split('/', StringSplitOptions.RemoveEmptyEntries);
        return parts.Length == 2 && parts.All(p => p.All(ch => char.IsLetterOrDigit(ch) || ch is '-' or '_' or '.'));
    }

    private static string SanitizePathPart(string value)
    {
        var chars = (value ?? "error").Select(ch => char.IsLetterOrDigit(ch) || ch is '-' or '_' ? ch : '_').ToArray();
        string result = new string(chars).Trim('_');
        if (result.Length == 0) result = "error";
        return result.Length <= 40 ? result : result[..40];
    }
}
'''
write(app / "RuntimeErrorUploader.cs", uploader)

dialog = r'''namespace FishingAutomation;

internal sealed class ErrorUploadSettingsDialog : Form
{
    private readonly CheckBox _enabled = new();
    private readonly TextBox _repo = new();
    private readonly TextBox _branch = new();
    private readonly TextBox _token = new();
    private readonly CheckBox _screenshot = new();
    private readonly NumericUpDown _logLines = new();
    private readonly Label _result = new();
    private readonly Func<string, string, string?, Task<(bool Ok, string Message)>> _test;

    public bool UploadEnabled => _enabled.Checked;
    public string Repository => _repo.Text.Trim();
    public string Branch => _branch.Text.Trim();
    public string Token => _token.Text.Trim();
    public bool SendScreenshot => _screenshot.Checked;
    public int RecentLogLines => (int)_logLines.Value;

    public ErrorUploadSettingsDialog(
        ErrorUploadSettings current,
        bool hasStoredToken,
        Func<string, string, string?, Task<(bool Ok, string Message)>> test)
    {
        _test = test;
        Text = "실전 에러 자동 전송";
        AccessibleName = "실전 에러 자동 전송 설정";
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        ClientSize = new Size(610, 465);
        BackColor = Color.FromArgb(3, 28, 49);
        ForeColor = Color.White;
        Font = new Font("맑은 고딕", 9.5f);
        ShowInTaskbar = false;

        Controls.Add(new Label
        {
            Text = "실전 에러 자동 전송",
            Location = new Point(24, 18), Size = new Size(420, 34),
            Font = new Font("맑은 고딕", 16f, FontStyle.Bold), ForeColor = Color.White
        });
        Controls.Add(new Label
        {
            Text = "오류/자동복구 경고 발생 시 summary.json, 최근 로그, 게임 스크린샷을 비공개 GitHub 저장소로 전송합니다.",
            Location = new Point(26, 55), Size = new Size(555, 42), ForeColor = Color.FromArgb(188, 211, 233)
        });

        _enabled.Text = "에러 자동 전송 사용";
        _enabled.Location = new Point(28, 103); _enabled.Size = new Size(230, 28); _enabled.Checked = current.Enabled;
        Controls.Add(_enabled);

        AddField("저장소 (owner/repo)", _repo, 145);
        _repo.Text = current.Repository;
        AddField("브랜치", _branch, 190);
        _branch.Text = string.IsNullOrWhiteSpace(current.Branch) ? "main" : current.Branch;
        AddField("Fine-grained token", _token, 235);
        _token.UseSystemPasswordChar = true;
        _token.PlaceholderText = hasStoredToken ? "저장된 토큰 유지 (변경할 때만 입력)" : "토큰 입력";

        _screenshot.Text = "게임 화면 스크린샷 포함";
        _screenshot.Location = new Point(176, 282); _screenshot.Size = new Size(230, 28); _screenshot.Checked = current.SendScreenshot;
        Controls.Add(_screenshot);

        Controls.Add(new Label { Text = "최근 로그 줄 수", Location = new Point(30, 322), Size = new Size(140, 28), TextAlign = ContentAlignment.MiddleLeft });
        _logLines.Location = new Point(176, 322); _logLines.Size = new Size(100, 28); _logLines.Minimum = 50; _logLines.Maximum = 1000; _logLines.Increment = 50;
        _logLines.Value = Math.Clamp(current.RecentLogLines, 50, 1000);
        Controls.Add(_logLines);

        var testButton = MakeButton("연결 테스트", new Rectangle(30, 365, 125, 38), Color.FromArgb(8, 66, 105));
        testButton.Click += async (_, _) =>
        {
            testButton.Enabled = false;
            _result.Text = "확인 중...";
            var r = await _test(_repo.Text.Trim(), _branch.Text.Trim(), string.IsNullOrWhiteSpace(_token.Text) ? null : _token.Text.Trim());
            _result.Text = r.Message;
            _result.ForeColor = r.Ok ? Color.FromArgb(80, 230, 155) : Color.Salmon;
            testButton.Enabled = true;
        };
        Controls.Add(testButton);

        _result.Location = new Point(170, 365); _result.Size = new Size(405, 44); _result.TextAlign = ContentAlignment.MiddleLeft; _result.AutoEllipsis = true;
        Controls.Add(_result);

        var save = MakeButton("저장", new Rectangle(383, 415, 92, 36), Color.FromArgb(0, 122, 190));
        save.DialogResult = DialogResult.OK;
        var cancel = MakeButton("취소", new Rectangle(485, 415, 92, 36), Color.FromArgb(20, 52, 78));
        cancel.DialogResult = DialogResult.Cancel;
        Controls.Add(save); Controls.Add(cancel);
        AcceptButton = save; CancelButton = cancel;
    }

    private void AddField(string caption, TextBox box, int y)
    {
        Controls.Add(new Label { Text = caption, Location = new Point(30, y), Size = new Size(140, 30), TextAlign = ContentAlignment.MiddleLeft });
        box.Location = new Point(176, y); box.Size = new Size(400, 30); box.BorderStyle = BorderStyle.FixedSingle;
        box.BackColor = Color.FromArgb(0, 17, 32); box.ForeColor = Color.White;
        Controls.Add(box);
    }

    private static Button MakeButton(string text, Rectangle bounds, Color backColor)
    {
        return new Button
        {
            Text = text, Bounds = bounds, BackColor = backColor, ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat, Cursor = Cursors.Hand, UseVisualStyleBackColor = false
        };
    }
}
'''
write(app / "ErrorUploadSettingsDialog.cs", dialog)

main_error_upload = r'''namespace FishingAutomation;

public sealed partial class MainForm
{
    private Task SendRuntimeAlertAsync(string title, string detail, bool screenshot = true)
    {
        string mode = _activeMode ?? SelectedMode;
        string selectedTarget = mode switch
        {
            "어비스" => SelectedAbyssDungeon,
            "던전" => SelectedDungeonDestination,
            _ => ""
        };
        var report = new RuntimeErrorReport
        {
            Time = DateTimeOffset.Now,
            Version = UpdateManager.CurrentVersion,
            Title = title,
            Detail = detail,
            Mode = mode,
            SelectedTarget = selectedTarget,
            ScreenStatus = _statusValue.Text
        };

        return Task.WhenAll(
            _notifier.SendAlertAsync(title, detail, screenshot),
            _errorUploader.UploadAlertAsync(report, screenshot));
    }

    private async void ShowErrorUploadSettings()
    {
        var current = _errorUploader.Settings;
        using var dialog = new ErrorUploadSettingsDialog(
            current,
            _errorUploader.HasStoredToken,
            (repo, branch, token) => _errorUploader.TestConnectionAsync(repo, branch, token));

        if (dialog.ShowDialog(this) != DialogResult.OK) return;
        try
        {
            var settings = new ErrorUploadSettings
            {
                Enabled = dialog.UploadEnabled,
                Repository = dialog.Repository,
                Branch = string.IsNullOrWhiteSpace(dialog.Branch) ? "main" : dialog.Branch,
                SendScreenshot = dialog.SendScreenshot,
                RecentLogLines = dialog.RecentLogLines,
            };
            _errorUploader.SaveSettings(settings, string.IsNullOrWhiteSpace(dialog.Token) ? null : dialog.Token);
            _log.Write(settings.Enabled
                ? $"[에러전송] 설정 저장 완료 · repo={settings.Repository} · branch={settings.Branch} · screenshot={(settings.SendScreenshot ? "ON" : "OFF")}"
                : "[에러전송] 자동 전송 OFF");
        }
        catch (Exception ex)
        {
            _log.Write("[에러전송] 설정 저장 실패: " + ex.Message);
            MessageBox.Show(this, "에러 전송 설정을 저장하지 못했습니다.\n" + ex.Message, "Mabi Auto", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        await Task.CompletedTask;
    }
}
'''
write(app / "MainForm.ErrorUpload.cs", main_error_upload)

# Bump runtime/package version after feature injection.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.33", "V0.1.34")
                   .replace("0.1.33.0", "0.1.34.0")
                   .replace("0.1.33", "0.1.34"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.34_RUNTIME_ERROR_UPLOAD.txt").write_text(
    "MABI AUTO V0.1.34 - RUNTIME ERROR AUTO UPLOAD\n\n"
    "Adds optional real-runtime error upload to a user-owned GitHub repository.\n"
    "Existing alert points (macro fatal error, auto-recovery start, network repeat, fishing stall, forced-exit delay, start failure) now fan out to both Telegram and the GitHub error uploader.\n"
    "Each upload writes summary.json, recent.log, and optionally screen.png under runtime-errors/YYYY-MM-DD/.\n"
    "The GitHub fine-grained PAT is stored only on the local PC encrypted with Windows DPAPI CurrentUser; it is never embedded in the package or written to the log.\n"
    "Upload is disabled by default and failures never stop the macro.\n"
    "V0.1.33 map/retry fixes and all existing dungeon/Abyss/fishing behavior are preserved.\n",
    encoding="utf-8"
)

# Final structural assertions.
main_check = read(main_path)
ref_check = read(refui_path)
uploader_check = read(app / "RuntimeErrorUploader.cs")
error_ui_check = read(app / "MainForm.ErrorUpload.cs")
project_check = read(csproj_path)
for marker in (
    "RuntimeErrorUploader _errorUploader",
    "SendRuntimeAlertAsync(",
    "DUNGEON_RESULT_RETRY_FASTPATH_V8",
    "var ullaBreadcrumbPoint = new Point(82, 66);",
):
    if marker not in main_check and marker not in error_ui_check:
        raise RuntimeError(f"required MainForm marker missing: {marker}")
if "_notifier.SendAlertAsync(" in main_check:
    raise RuntimeError("raw MainForm Telegram alert call remains; runtime uploader would be bypassed")
for marker in (
    "RUNTIME_ERROR_GITHUB_UPLOAD_V9",
    "ProtectedData.Protect",
    "DataProtectionScope.CurrentUser",
    '"runtime-errors/',
    'summary.json',
    'recent.log',
    'screen.png',
    '/contents/',
):
    if marker not in uploader_check:
        raise RuntimeError(f"uploader marker missing: {marker}")
if 'AddButton("에러 전송"' not in ref_check:
    raise RuntimeError("error upload settings button missing")
if "System.Security.Cryptography.ProtectedData" not in project_check:
    raise RuntimeError("ProtectedData package missing")
if "github_pat_" in (main_check + uploader_check + error_ui_check):
    raise RuntimeError("token-like literal must never be embedded")

print(f"V0.1.34 patch applied: runtime alert upload fan-out ({old_alert_count} existing alert call sites)")

