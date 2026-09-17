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
parts_dir = Path(__file__).resolve().parent / "visual-test-assets"
parts = [parts_dir / f"assets.b64.part{i}" for i in range(4)]
for p in parts:
    if not p.exists():
        raise RuntimeError(f"visual-test asset part missing: {p}")
encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
asset_zip = base64.b64decode(encoded)
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
