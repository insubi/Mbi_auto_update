#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, json, sys, zipfile, io

if len(sys.argv) != 2:
    raise SystemExit("usage: v0135_visual_test_environment.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
refui_path = app / "MainForm.ReferenceUI.cs"
uploader_path = app / "RuntimeErrorUploader.cs"
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

# Restore compact fixture ZIP assembled from real screenshots previously supplied by the user.
asset_zip = base64.b64decode("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[...truncated...]")
asset_sha = hashlib.sha256(asset_zip).hexdigest()
EXPECTED_ASSET_ZIP_SHA = "f4a3354f83a906761e5acaa2e50bc566f3514c839ea4bb755d89a64f5c92e840"
if asset_sha != EXPECTED_ASSET_ZIP_SHA:
    raise RuntimeError(f"visual-test asset ZIP hash mismatch: {asset_sha}")

asset_dir = app / "visual-tests" / "assets"
asset_dir.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(asset_zip), "r") as zf:
    zf.extractall(asset_dir)

expected_assets = {
    "peaca_label.jpg": "10d2eb1ac7df81dd25555a70aab4db903169d98fa8a50adc0138f64a7d4d109d",
    "fiod_label.jpg": "78685b19df71aad991c9ee6486ae9dfe956fb7007da9bb60e0f82ccfdac3c71d",
    "peaca_popup_title.jpg": "dd6538c2fe9c92253bd289cedb779a1c25d3e97f6affb33050c06e4aabdb2da2",
    "go_here.jpg": "496e016e295a8d63de38e2ece039f7efdbffa7babc10e6ce39843183aeadad4f",
    "d1_slots.jpg": "9fd8bf057e4b1b5d956210e6b569e3bf5383116deb0c1a23241273fda78d4a32",
    "d2_slots.jpg": "62e6ca80ad9510e9d31d8bf354575c9ec1fef0811837c0d39b67de9993e7c9d6",
    "d2_enter.jpg": "92b1a509ba745c220115dadeb7b8d086e563e9c3a932a906465e7aa24429b74a",
    "retry_candidate.jpg": "1757c54deec2ffbc4f3f7bffc7e85f372a0532f682460c005f443d9d2c418800",
}
for name, expected in expected_assets.items():
    p = asset_dir / name
    if not p.exists():
        raise RuntimeError(f"visual-test fixture missing after extraction: {name}")
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"visual-test fixture hash mismatch: {name} {actual}")

tester = r'''using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using DungeonVisionBot;

namespace FishingAutomation;

// VISUAL_TEST_ENV_V10
// Offline recognition regression test. It never resolves a game window and never invokes
// Interception/input APIs. Real stored screenshot pixels are rendered into an 800x1000
// synthetic client frame and passed to the same OCR/OpenCV detector used by the live bot.
public sealed class VisualTestOutcome
{
    public string Id { get; init; } = "";
    public string Label { get; init; } = "";
    public string Status { get; init; } = "FAIL";
    public string Method { get; init; } = "";
    public string Detail { get; init; } = "";
    public double Score { get; init; }
    public Rectangle Bounds { get; init; }
    public byte[]? FailurePng { get; init; }
}

public sealed class VisualTestRunReport
{
    public DateTimeOffset Time { get; init; } = DateTimeOffset.Now;
    public string Version { get; init; } = UpdateManager.CurrentVersion;
    public List<VisualTestOutcome> Outcomes { get; init; } = new();
    public int Passed => Outcomes.Count(x => x.Status == "PASS");
    public int Failed => Outcomes.Count(x => x.Status == "FAIL");
    public int Skipped => Outcomes.Count(x => x.Status == "SKIP");
}

public sealed class VisualRecognitionTester
{
    private readonly string _baseDir;
    private readonly string _dungeonDir;
    private readonly string _assetDir;
    private readonly TargetDetector _detector;
    private readonly OcrRecognizer _ocr;

    public VisualRecognitionTester(string baseDir)
    {
        _baseDir = baseDir;
        _dungeonDir = Path.Combine(baseDir, "dungeon");
        _assetDir = Path.Combine(baseDir, "visual-tests", "assets");
        string targetPath = Path.Combine(_dungeonDir, "config", "targets.json");
        if (!File.Exists(targetPath))
            throw new FileNotFoundException("인식 테스트용 targets.json을 찾지 못했습니다.", targetPath);

        var targets = System.Text.Json.JsonSerializer.Deserialize<List<TargetDefinition>>(
            File.ReadAllText(targetPath),
            new System.Text.Json.JsonSerializerOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidDataException("던전 targets.json을 읽지 못했습니다.");

        _detector = new TargetDetector(targets, _dungeonDir);
        _ocr = new OcrRecognizer();
    }

    public async Task<VisualTestRunReport> RunAllAsync(
        IProgress<string>? progress = null,
        CancellationToken ct = default)
    {
        var report = new VisualTestRunReport();
        progress?.Report("[인식 테스트] 실제 게임 입력 없음 · 저장 스크린샷만 사용");

        await AddTarget(report, progress, "peaca-map", "월드맵 · 페카 고분 OCR",
            "peaca_label.jpg", new Rectangle(80, 180, 230, 155), "route_peaca_map", ct);

        await AddDirectOcr(report, progress, "fiod-map", "월드맵 · 피오드 던전 OCR",
            "fiod_label.jpg", new Rectangle(180, 260, 220, 180),
            new Rectangle(20, 110, 660, 650), "피오드 던전", 2, ct);

        await AddTarget(report, progress, "peaca-popup", "페카 팝업 · 페카 고분",
            "peaca_popup_title.jpg", new Rectangle(100, 520, 600, 260),
            "route_peaca_popup_title", ct);

        await AddTarget(report, progress, "go-here", "페카 팝업 · 여기로 가기",
            "go_here.jpg", new Rectangle(90, 805, 620, 178),
            "route_go_here", ct);

        await AddTarget(report, progress, "d1-1", "심층 던전 · D1-1",
            "d1_slots.jpg", new Rectangle(160, 400, 470, 250),
            "route_d1_1", ct);

        await AddTarget(report, progress, "d2-1", "심층 던전 · D2-1",
            "d2_slots.jpg", new Rectangle(180, 680, 420, 255),
            "route_d2_1", ct);

        await AddTarget(report, progress, "d2-enter", "심층 던전 · 2층 1구역 진입",
            "d2_enter.jpg", new Rectangle(85, 850, 630, 129),
            "route_enter_d2_1", ct);

        await AddTarget(report, progress, "retry", "결과 화면 · 다시 하기 하이브리드",
            "retry_candidate.jpg", new Rectangle(235, 835, 300, 155),
            "retry", ct);

        var runda = new VisualTestOutcome
        {
            Id = "runda-map",
            Label = "월드맵 · 룬다 던전 OCR",
            Status = "SKIP",
            Method = "OCR",
            Detail = "룬다 던전이 보이는 기존 스크린샷이 아직 없어 테스트를 건너뜁니다."
        };
        report.Outcomes.Add(runda);
        progress?.Report(Format(runda));

        progress?.Report($"[인식 테스트] 완료 · PASS {report.Passed} / FAIL {report.Failed} / SKIP {report.Skipped}");
        return report;
    }

    private async Task AddTarget(
        VisualTestRunReport report,
        IProgress<string>? progress,
        string id,
        string label,
        string asset,
        Rectangle destination,
        string targetId,
        CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        using var frame = BuildFrame(asset, destination);
        DetectionResult result;
        try
        {
            result = await _detector.DetectAsync(targetId, frame, ct);
        }
        catch (Exception ex)
        {
            var error = Fail(id, label, _detector.Get(targetId).Kind, "검출기 예외: " + ex.Message, frame);
            report.Outcomes.Add(error);
            progress?.Report(Format(error));
            return;
        }

        string method = _detector.Get(targetId).Kind;
        var outcome = result.Found
            ? new VisualTestOutcome
            {
                Id = id, Label = label, Status = "PASS", Method = method,
                Detail = string.IsNullOrWhiteSpace(result.Text)
                    ? $"검출 성공 · score={result.Score:0.000}"
                    : $"검출 성공 · OCR=\"{result.Text}\"",
                Score = result.Score, Bounds = result.Bounds
            }
            : Fail(id, label, method,
                $"검출 실패 · best score={result.Score:0.000} · target={targetId}", frame, result.Score, result.Bounds);

        report.Outcomes.Add(outcome);
        progress?.Report(Format(outcome));
    }

    private async Task AddDirectOcr(
        VisualTestRunReport report,
        IProgress<string>? progress,
        string id,
        string label,
        string asset,
        Rectangle destination,
        Rectangle roi,
        string wanted,
        int editDistance,
        CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        using var frame = BuildFrame(asset, destination);
        DetectionResult result;
        try
        {
            result = await _ocr.FindTextAsync(frame, roi, wanted, editDistance, true, ct);
        }
        catch (Exception ex)
        {
            var error = Fail(id, label, "ocr", "OCR 예외: " + ex.Message, frame);
            report.Outcomes.Add(error);
            progress?.Report(Format(error));
            return;
        }

        var outcome = result.Found
            ? new VisualTestOutcome
            {
                Id = id, Label = label, Status = "PASS", Method = "ocr",
                Detail = $"검출 성공 · OCR=\"{result.Text}\"",
                Score = result.Score, Bounds = result.Bounds
            }
            : Fail(id, label, "ocr", $"OCR 실패 · wanted=\"{wanted}\"", frame, result.Score, result.Bounds);

        report.Outcomes.Add(outcome);
        progress?.Report(Format(outcome));
    }

    private Bitmap BuildFrame(string assetName, Rectangle destination)
    {
        string path = Path.Combine(_assetDir, assetName);
        if (!File.Exists(path))
            throw new FileNotFoundException("인식 테스트 이미지를 찾지 못했습니다.", path);

        using var src = new Bitmap(path);
        var frame = new Bitmap(800, 1000, PixelFormat.Format24bppRgb);
        using var g = Graphics.FromImage(frame);
        g.Clear(Color.Black);
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
        g.DrawImage(src, destination);
        return frame;
    }

    private static VisualTestOutcome Fail(
        string id,
        string label,
        string method,
        string detail,
        Bitmap frame,
        double score = 0,
        Rectangle bounds = default)
    {
        using var ms = new MemoryStream();
        frame.Save(ms, ImageFormat.Png);
        return new VisualTestOutcome
        {
            Id = id, Label = label, Status = "FAIL", Method = method,
            Detail = detail, Score = score, Bounds = bounds, FailurePng = ms.ToArray()
        };
    }

    private static string Format(VisualTestOutcome x)
        => $"[{x.Status}] {x.Label} · {x.Detail}";
}
'''
write(app / "VisualRecognitionTester.cs", tester)

visual_ui = r'''namespace FishingAutomation;

public sealed partial class MainForm
{
    internal async void ShowVisualRecognitionTest()
    {
        if (AnyRunning)
        {
            MessageBox.Show(this, "매크로 실행 중에는 인식 테스트를 시작하지 않습니다.\nF10으로 정지한 뒤 실행하세요.",
                "MABI AUTO 인식 테스트", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        using var dialog = new Form
        {
            Text = "저장 스크린샷 인식 테스트",
            AccessibleName = "저장 스크린샷 인식 테스트",
            StartPosition = FormStartPosition.CenterParent,
            FormBorderStyle = FormBorderStyle.FixedDialog,
            MaximizeBox = false,
            MinimizeBox = false,
            ClientSize = new Size(760, 590),
            BackColor = Color.FromArgb(3, 28, 49),
            ForeColor = Color.White,
            Font = new Font("맑은 고딕", 9.5f),
            ShowInTaskbar = false
        };

        var title = new Label
        {
            Text = "OCR / 이미지 인식 오프라인 테스트",
            Location = new Point(24, 18), Size = new Size(690, 34),
            Font = new Font("맑은 고딕", 16f, FontStyle.Bold)
        };
        var note = new Label
        {
            Text = "실제 게임에는 키보드/마우스를 보내지 않습니다. 이전에 저장한 스크린샷을 현재 OCR/OpenCV 검출기에 넣어 확인합니다.",
            Location = new Point(26, 58), Size = new Size(700, 45),
            ForeColor = Color.FromArgb(188, 211, 233)
        };
        var output = new TextBox
        {
            Location = new Point(24, 112), Size = new Size(712, 390),
            Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical,
            BackColor = Color.FromArgb(0, 15, 29), ForeColor = Color.White,
            Font = new Font("Consolas", 9.5f), WordWrap = true
        };
        var status = new Label
        {
            Text = "준비",
            Location = new Point(24, 510), Size = new Size(430, 42),
            TextAlign = ContentAlignment.MiddleLeft,
            ForeColor = Color.FromArgb(188, 211, 233)
        };
        var run = new Button
        {
            Text = "전체 테스트 실행",
            Location = new Point(470, 516), Size = new Size(135, 40),
            BackColor = Color.FromArgb(0, 122, 190), ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat, Cursor = Cursors.Hand
        };
        var close = new Button
        {
            Text = "닫기",
            Location = new Point(615, 516), Size = new Size(120, 40),
            BackColor = Color.FromArgb(20, 52, 78), ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat, Cursor = Cursors.Hand
        };
        close.Click += (_, _) => dialog.Close();

        dialog.Controls.AddRange(new Control[] { title, note, output, status, run, close });

        run.Click += async (_, _) =>
        {
            run.Enabled = false;
            close.Enabled = false;
            output.Clear();
            status.Text = "테스트 실행 중...";
            status.ForeColor = Color.FromArgb(255, 194, 87);

            try
            {
                var progress = new Progress<string>(line =>
                {
                    output.AppendText(line + Environment.NewLine);
                    output.SelectionStart = output.TextLength;
                    output.ScrollToCaret();
                });

                var tester = new VisualRecognitionTester(AppContext.BaseDirectory);
                VisualTestRunReport report = await tester.RunAllAsync(progress);

                string? uploaded = await _errorUploader.UploadVisualTestRunAsync(report);
                if (!string.IsNullOrWhiteSpace(uploaded))
                    output.AppendText($"[TEST-UPLOAD] GitHub 전송 완료 · {uploaded}{Environment.NewLine}");
                else
                    output.AppendText("[TEST-UPLOAD] 에러 전송 설정 OFF/불완전 · 로컬 결과만 표시합니다." + Environment.NewLine);

                status.Text = report.Failed == 0
                    ? $"완료 · PASS {report.Passed} / FAIL 0 / SKIP {report.Skipped}"
                    : $"완료 · PASS {report.Passed} / FAIL {report.Failed} / SKIP {report.Skipped}";
                status.ForeColor = report.Failed == 0
                    ? Color.FromArgb(80, 230, 155)
                    : Color.Salmon;

                _log.Write($"[인식테스트] 완료 · PASS={report.Passed} FAIL={report.Failed} SKIP={report.Skipped}" +
                           (uploaded is null ? "" : $" · upload={uploaded}"));
            }
            catch (Exception ex)
            {
                output.AppendText("[TEST-ERROR] " + ex + Environment.NewLine);
                status.Text = "테스트 실행 오류";
                status.ForeColor = Color.Salmon;
                _log.Write("[인식테스트] 실행 오류: " + ex.Message);
            }
            finally
            {
                run.Enabled = true;
                close.Enabled = true;
            }
        };

        dialog.ShowDialog(this);
        await Task.CompletedTask;
    }
}
'''
write(app / "MainForm.VisualTest.cs", visual_ui)

# Extend the already-configured V0.1.34 uploader. Manual recognition tests use the same
# encrypted token/repository and always upload a compact summary; failed cases also upload
# the synthesized 800x1000 frame that failed recognition.
uploader = read(uploader_path)
upload_method = r'''
    public async Task<string?> UploadVisualTestRunAsync(VisualTestRunReport report)
    {
        var settings = LoadSettings();
        if (!settings.Enabled) return null;
        string repo = NormalizeRepository(settings.Repository);
        string? token = GetStoredToken(settings);
        if (!IsValidRepository(repo) || string.IsNullOrWhiteSpace(token))
        {
            _log.Write("[테스트전송] 설정이 불완전하여 업로드하지 않았습니다.");
            return null;
        }

        await _uploadGate.WaitAsync();
        try
        {
            string unique = Guid.NewGuid().ToString("N")[..6];
            string resultName = report.Failed == 0 ? "PASS" : "FAIL";
            string folder = $"test-runs/{report.Time:yyyy-MM-dd}/{report.Time:yyyyMMdd_HHmmss_fff}_{resultName}_{unique}";
            string branch = string.IsNullOrWhiteSpace(settings.Branch) ? "main" : settings.Branch.Trim();

            var summary = new
            {
                schema = 1,
                source = "visual-test",
                version = report.Version,
                timeLocal = report.Time.ToString("O"),
                timeUtc = report.Time.ToUniversalTime().ToString("O"),
                passed = report.Passed,
                failed = report.Failed,
                skipped = report.Skipped,
                gameInputSent = false,
                outcomes = report.Outcomes.Select(x => new
                {
                    id = x.Id,
                    label = x.Label,
                    status = x.Status,
                    method = x.Method,
                    detail = x.Detail,
                    score = x.Score,
                    bounds = new { x = x.Bounds.X, y = x.Bounds.Y, width = x.Bounds.Width, height = x.Bounds.Height }
                }).ToArray()
            };
            byte[] summaryBytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(summary, new JsonSerializerOptions { WriteIndented = true }));
            await PutFileAsync(repo, branch, token, $"{folder}/summary.json", summaryBytes, $"visual test: {resultName}");

            string lines = string.Join(Environment.NewLine, report.Outcomes.Select(x =>
                $"[{x.Status}] {x.Id} | {x.Label} | {x.Method} | score={x.Score:0.000} | {x.Detail}"));
            await PutFileAsync(repo, branch, token, $"{folder}/test.log", Encoding.UTF8.GetBytes(lines), $"visual test log: {resultName}");

            foreach (var failed in report.Outcomes.Where(x => x.Status == "FAIL" && x.FailurePng is not null))
                await PutFileAsync(repo, branch, token, $"{folder}/failures/{SanitizePathPart(failed.Id)}.png",
                    failed.FailurePng!, $"visual test failure: {failed.Id}");

            _log.Write($"[테스트전송] 업로드 완료: {repo}/{folder}");
            return $"{repo}/{folder}";
        }
        catch (Exception ex)
        {
            _log.Write("[테스트전송] 실패: " + ex.Message);
            return null;
        }
        finally
        {
            _uploadGate.Release();
        }
    }

'''
uploader = replace_once(
    uploader,
    "    private async Task PutFileAsync(string repo, string branch, string token, string path, byte[] data, string message)\n",
    upload_method + "    private async Task PutFileAsync(string repo, string branch, string token, string path, byte[] data, string message)\n",
    "visual test upload method")
write(uploader_path, uploader)

refui = read(refui_path)
refui = replace_once(
    refui,
    '''            AddButton("에러 전송", new(18, 441, 170, 59), owner.ShowErrorUploadSettings, "send", "nav");\n            AddButton("미니 모드", new(18, 991, 170, 46), () => owner.ToggleMini(true), "", "quiet");\n''',
    '''            AddButton("에러 전송", new(18, 441, 170, 59), owner.ShowErrorUploadSettings, "send", "nav");\n            AddButton("인식 테스트", new(18, 511, 170, 59), owner.ShowVisualRecognitionTest, "test", "nav");\n            AddButton("미니 모드", new(18, 991, 170, 46), () => owner.ToggleMini(true), "", "quiet");\n''',
    "reference UI visual test button")
write(refui_path, refui)

csproj = read(csproj_path)
if "visual-tests\\assets\\**\\*" not in csproj:
    insert = '''  <ItemGroup>\n    <Content Include="visual-tests\\assets\\**\\*">\n      <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>\n      <CopyToPublishDirectory>PreserveNewest</CopyToPublishDirectory>\n    </Content>\n  </ItemGroup>\n'''
    csproj = csproj.replace("</Project>", insert + "</Project>")
write(csproj_path, csproj)

# Version bump after all V0.1.34 code has been injected.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.34", "V0.1.35")
                   .replace("0.1.34.0", "0.1.35.0")
                   .replace("0.1.34", "0.1.35"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.35_VISUAL_TEST_ENV.txt").write_text(
    "MABI AUTO V0.1.35 - OFFLINE OCR/OPENCV TEST ENVIRONMENT\n\n"
    "Adds an '인식 테스트' screen that runs real Windows.Media.Ocr and current TargetDetector/OpenCV against stored screenshot fixtures without touching the game window or sending any keyboard/mouse input.\n"
    "Current fixtures cover Peaca world-map OCR, Fiod world-map OCR, Peaca popup/title, Go Here, Deep D1-1, Deep D2-1, exact D2-1 entry text, and the hybrid Retry detector. Runda is reported as SKIP until a Runda-visible screenshot is added.\n"
    "Every manually started test run uploads summary.json + test.log to the same configured GitHub error repository under test-runs/. Failed test frames are also uploaded under failures/.\n"
    "V0.1.34 runtime error upload, V0.1.33 retry fast path, Ula fixed breadcrumb transition verification, dungeon/Abyss/fishing behavior and F10 safety are preserved.\n",
    encoding="utf-8"
)

# Structural/safety assertions.
tester_check = read(app / "VisualRecognitionTester.cs")
ui_check = read(app / "MainForm.VisualTest.cs")
uploader_check = read(uploader_path)
ref_check = read(refui_path)
project_check = read(csproj_path)

for marker in (
    "VISUAL_TEST_ENV_V10",
    "VisualRecognitionTester",
    "route_peaca_map",
    "피오드 던전",
    "route_d1_1",
    "route_d2_1",
    "route_enter_d2_1",
    '"retry"',
    'Status = "SKIP"',
    "룬다 던전이 보이는 기존 스크린샷이 아직 없어",
):
    if marker not in tester_check:
        raise RuntimeError(f"visual tester marker missing: {marker}")

for forbidden in ("ClickClientPoint", "TapScanCode", "DragClientPoint", "FindRequiredGameWindow", "SetForegroundWindow"):
    if forbidden in tester_check:
        raise RuntimeError(f"visual tester must never send/read live game input/window: {forbidden}")

for marker in ("UploadVisualTestRunAsync", '"test-runs/', 'source = "visual-test"', "gameInputSent = false", "failures/"):
    if marker not in uploader_check:
        raise RuntimeError(f"visual test uploader marker missing: {marker}")

if 'AddButton("인식 테스트"' not in ref_check:
    raise RuntimeError("visual test sidebar button missing")
if "visual-tests\\assets\\**\\*" not in project_check:
    raise RuntimeError("visual test assets copy rule missing")
if "<Version>0.1.35</Version>" not in project_check:
    raise RuntimeError("V0.1.35 project version missing")
if "RUNTIME_ERROR_GITHUB_UPLOAD_V9" not in uploader_check:
    raise RuntimeError("V0.1.34 runtime uploader regressed")

print("V0.1.35 patch applied: offline recognition test + GitHub test-runs upload")
