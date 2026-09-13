#!/usr/bin/env python3
from pathlib import Path
import base64
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
templates = app / "life" / "templates"
parts = Path(__file__).resolve().parent / "v35_parts"

def rep(path: Path, old: str, new: str, bom=False):
    enc = "utf-8-sig" if bom else "utf-8"
    text = path.read_text(encoding=enc)
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"marker missing: {path}")
    path.write_text(text.replace(old, new, 1), encoding=enc)

rep(app/"UpdateManager.cs", 'public const string CurrentVersion = "v34";', 'public const string CurrentVersion = "v35";', True)
rep(app/"MainForm.cs", 'Text = "MABI AUTO · v34";', 'Text = "MABI AUTO · v35";', True)
rep(app/"MainForm.Dashboard.cs", 'Text = "자동화 대시보드  ·  Dashboard v34",', 'Text = "자동화 대시보드  ·  Dashboard v35",', True)
rep(app/"MainForm.Dashboard.cs", 'Text = "v34  |  Mabi Auto"', 'Text = "v35  |  Mabi Auto"', True)
for old, new in [("<Version>34.0.0</Version>", "<Version>35.0.0</Version>"), ("<AssemblyVersion>34.0.0.0</AssemblyVersion>", "<AssemblyVersion>35.0.0.0</AssemblyVersion>"), ("<FileVersion>34.0.0.0</FileVersion>", "<FileVersion>35.0.0.0</FileVersion>")]:
    rep(app/"FishingAutomation.csproj", old, new)

for name in ["processing_menu_off.jpg", "processing_menu_on.jpg", "slot_cloth_icon.jpg", "slot_cloth.jpg", "slot_done.jpg", "slot_empty.jpg"]:
    src = parts / f"{name}.b64"
    if not src.exists():
        raise RuntimeError(f"missing v35 template part: {src}")
    (templates/name).write_bytes(base64.b64decode(src.read_text(encoding="ascii").strip()))

engine = app/"LifeAutomationEngine.cs"
old_open = '''    private async Task OpenProcessingFacilityAsync(CancellationToken ct)
    {
        await ClickTemplateAsync("processing_tab.jpg", "가공 탭", 20, ct, threshold: 0.55);

        using (var frame = _capture.CaptureClient(_hwnd))
        {
            if (!Found(frame, "processing_menu_on.jpg", 0.55))
            {
                // The inactive version is intentionally preferred so the click is only sent when needed.
                await ClickTemplateAsync("processing_menu_off.jpg", "가공 메뉴", 12, ct, threshold: 0.50);
                await WaitTemplateAsync("processing_menu_on.jpg", "가공 메뉴 활성화", 8, ct, threshold: 0.50);
            }
            else
            {
                Emit("가공 메뉴가 이미 활성 상태입니다.");
            }
        }

        await ClickTemplateAsync("cloth_processing.jpg", "옷감 가공", 15, ct, threshold: 0.52);
        await ClickTemplateOrTextAsync("go_facility.jpg", "설비로 이동", "설비로 이동", 15, ct, 0.55);

        Stage("설비 이동 중");
        await WaitForProcessingScreenAsync(ct);
    }

'''
new_open = '''    private async Task OpenProcessingFacilityAsync(CancellationToken ct)
    {
        await ClickTemplateAsync("processing_tab.jpg", "가공 탭", 20, ct, threshold: 0.55);

        bool menuActive;
        using (var frame = _capture.CaptureClient(_hwnd))
            menuActive = Found(frame, "processing_menu_on.jpg", 0.48);

        if (!menuActive)
        {
            bool clicked = await TryClickTemplateAsync("processing_menu_off.jpg", 6, ct, 0.46);
            if (!clicked)
                await ClickExactTextAsync("가공", "가공 메뉴", 6, ct);

            await WaitTemplateAsync("processing_menu_on.jpg", "가공 메뉴 활성화", 8, ct, threshold: 0.46);
            Emit("가공 메뉴 활성화 확인");
        }
        else
        {
            Emit("가공 메뉴가 이미 활성 상태입니다.");
        }

        await ClickTemplateAsync("cloth_processing.jpg", "옷감 가공", 15, ct, threshold: 0.52);
        await ClickTemplateOrTextAsync("go_facility.jpg", "설비로 이동", "설비로 이동", 15, ct, 0.55);

        Stage("설비 이동 중");
        await WaitForProcessingScreenAsync(ct);
    }

'''
rep(engine, old_open, new_open, True)

text = engine.read_text(encoding="utf-8-sig")
text = text.replace('threshold: 0.60, minScale: 0.45, maxScale: 1.55, step: 0.08, maxMatches: 10).Count;', 'threshold: 0.56, minScale: 0.55, maxScale: 1.45, step: 0.06, maxMatches: 10).Count;', 1)
text = text.replace('threshold: 0.58, minScale: 0.45, maxScale: 1.55, step: 0.08, maxMatches: 10).Count;', 'threshold: 0.54, minScale: 0.55, maxScale: 1.45, step: 0.06, maxMatches: 10).Count;', 1)
text = text.replace('threshold: 0.59, minScale: 0.45, maxScale: 1.55, step: 0.08, maxMatches: 10).Count;', 'threshold: 0.55, minScale: 0.55, maxScale: 1.45, step: 0.06, maxMatches: 10).Count;', 1)

marker = '    private Rectangle GetProcessingSlotsRoi(Bitmap frame)\n'
if "private bool IsQueueEmpty(Bitmap frame)" not in text:
    helper = '''    private bool IsQueueEmpty(Bitmap frame)
    {
        Rectangle slotsRoi = GetProcessingSlotsRoi(frame);
        int empty = _matcher.FindAll(
            frame, slotsRoi, "slot_empty.jpg",
            threshold: 0.55, minScale: 0.55, maxScale: 1.45, step: 0.06, maxMatches: 10).Count;
        return empty >= 7;
    }

    private async Task<bool> WaitQueueEmptyAsync(int timeoutSeconds, CancellationToken ct)
    {
        DateTime deadline = DateTime.UtcNow.AddSeconds(timeoutSeconds);
        while (DateTime.UtcNow < deadline)
        {
            ct.ThrowIfCancellationRequested();
            using var frame = _capture.CaptureClient(_hwnd);
            if (IsQueueEmpty(frame))
                return true;
            await Task.Delay(Math.Max(250, _settings.TemplatePollMs), ct);
        }
        return false;
    }

'''
    if marker not in text:
        raise RuntimeError("slot ROI marker missing")
    text = text.replace(marker, helper + marker, 1)

old_receive = '''        await ClickTemplateOrTextAsync("confirm.jpg", "확인", "확인", 10, ct, 0.52);
        Emit("가공품 모두 받기 완료");
'''
new_receive = '''        await ClickTemplateOrTextAsync("confirm.jpg", "확인", "확인", 10, ct, 0.52);

        if (await WaitQueueEmptyAsync(5, ct))
            Emit("가공품 모두 받기 완료 · PC 빈 7칸 확인");
        else
            Emit("가공품 모두 받기 완료 · 빈 슬롯 확인은 다음 루프에서 계속");
'''
if new_receive not in text:
    if old_receive not in text:
        raise RuntimeError("receive marker missing")
    text = text.replace(old_receive, new_receive, 1)
engine.write_text(text, encoding="utf-8-sig")

(root/"CHANGES_v35_PC_PROCESSING_TEMPLATES.txt").write_text(
    "MABI AUTO v35\n\n- PC 화면 기준 가공 메뉴 비활성/활성 템플릿 교체\n- 가공 메뉴 이미지 인식 실패 시 OCR 정확 일치 '가공' 클릭 보조\n- PC 화면 기준 옷감 슬롯 아이콘/0%/100%/빈 슬롯 템플릿 교체\n- 7칸 채움과 7칸 100% 완료 분리 판정 유지\n- 모두 받기/확인 후 빈 7칸 상태 보조 확인\n- 나머지 기존 템플릿과 낚시/던전/어비스 기능 유지\n",
    encoding="utf-8")
print("v35 patch applied")
