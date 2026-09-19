#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

engine = app / "dungeon" / "ScenarioEngine.cs"
s = read(engine)

old_wait_touch = '''    private async Task<DetectionResult> WaitForAbyssTouchPromptAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        int clearGoneConsecutive = 0;

        while (sw.Elapsed < TimeSpan.FromSeconds(20))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
            if (touch.Found)
            {
                Log?.Invoke($"[어비스] 화면 터치 문구 확인 -> 해당 위치 클릭 준비 @ {touch.Bounds}");
                return touch;
            }

            var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
            if (!clearTitle.Found)
            {
                clearGoneConsecutive++;
                if (clearGoneConsecutive >= 3)
                {
                    Log?.Invoke("[어비스] 터치 문구 대기 중 클리어 화면이 이미 3회 연속 사라짐 -> 전환 완료로 처리");
                    return DetectionResult.NotFound;
                }
            }
            else
            {
                clearGoneConsecutive = 0;
            }

            await Task.Delay(Math.Max(200, _settings.PollIntervalMs), ct);
        }

        throw new TimeoutException("어비스 클리어 화면은 감지했지만 '화면을 터치해 주세요' 이미지를 20초 안에 찾지 못했습니다.");
    }
'''
new_wait_touch = '''    private async Task<DetectionResult> WaitForAbyssTouchPromptAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        int clearTitleConsecutive = 0;

        while (sw.Elapsed < TimeSpan.FromSeconds(20))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            // The only valid reason to finish waiting without a touch click is that
            // the actual result screen is already visible.
            var result = await DetectAbyssResultRetryAsync(frame, ct);
            if (result.Found)
            {
                Log?.Invoke("[어비스] 터치 문구 대기 중 실제 결과 화면 확인 -> 추가 터치 없이 결과 단계 진행");
                return DetectionResult.NotFound;
            }

            var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
            if (touch.Found)
            {
                Log?.Invoke($"[어비스] 화면 터치 문구 확인 -> 해당 위치 클릭 준비 @ {touch.Bounds}");
                return touch;
            }

            var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
            if (clearTitle.Found)
            {
                clearTitleConsecutive++;
                if (clearTitleConsecutive >= 2 && frame.Width == 800 && frame.Height == 1000)
                {
                    var safeTouch = new Rectangle(360, 915, 80, 60);
                    Log?.Invoke($"[어비스] 클리어 타이틀 2회 확인 + 터치 문구 미검출 -> 안전 터치 위치 사용 @ {safeTouch}");
                    return new DetectionResult(true, safeTouch, clearTitle.Score, "clear_touch_safe_fallback");
                }
            }
            else
            {
                clearTitleConsecutive = 0;
            }

            // Important: missing clear/touch templates is NOT treated as a successful
            // transition anymore. Keep waiting until the result screen is actually seen.
            await Task.Delay(Math.Max(200, _settings.PollIntervalMs), ct);
        }

        throw new TimeoutException("어비스 클리어 화면 이후 실제 결과 화면 또는 '화면을 터치해 주세요'를 20초 안에 확정하지 못했습니다.");
    }
'''
if old_wait_touch not in s:
    raise SystemExit("old WaitForAbyssTouchPromptAsync block not found")
s = s.replace(old_wait_touch, new_wait_touch, 1)

old_wait_gone = '''    private async Task WaitForAbyssClearScreenGoneAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        int goneConsecutive = 0;
        int retryClicks = 0;

        while (sw.Elapsed < TimeSpan.FromSeconds(20))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var clear = await DetectAbyssClearVisualAsync(frame, ct);

            if (!clear.Found)
            {
                goneConsecutive++;
                Log?.Invoke($"[어비스] 클리어 화면 사라짐 확인 {goneConsecutive}/3");
                if (goneConsecutive >= 3)
                {
                    Log?.Invoke("[어비스] 클리어 화면 3회 연속 사라짐 확인 -> 보물상자 단계 진행");
                    return;
                }
            }
            else
            {
                goneConsecutive = 0;

                // If the result screen stayed up, retry once, but still click only the
                // actual touch-prompt image. Never click the clear-title match.
                if (retryClicks < 1 && sw.Elapsed >= TimeSpan.FromSeconds(2))
                {
                    var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
                    if (touch.Found)
                    {
                        _hwnd = await ResolveRequiredGameWindowAsync(ct);
                        NativeMethods.SetForegroundWindow(_hwnd);
                        Log?.Invoke($"[어비스] 클리어 화면 유지 -> 터치 문구 위치 1회 재클릭 @ {touch.Bounds}");
                        _input.ClickClientPoint(_hwnd, touch.Center);
                        retryClicks++;
                        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);
                        continue;
                    }
                }
            }

            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }

        throw new TimeoutException("어비스 클리어 화면 클릭 후 화면 전환을 20초 안에 확정하지 못했습니다. 보물상자 단계로 넘어가지 않습니다.");
    }
'''
new_wait_gone = '''    private async Task WaitForAbyssClearScreenGoneAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        int retryClicks = 0;
        int clearTitleConsecutive = 0;

        while (sw.Elapsed < TimeSpan.FromSeconds(30))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            // Do not advance merely because the clear templates disappeared for a few
            // frames. The next state must be the actual Abyss result screen.
            var result = await DetectAbyssResultRetryAsync(frame, ct);
            if (result.Found)
            {
                Log?.Invoke($"[어비스] 실제 결과 화면 확인 -> 다시 하기 단계 진행 @ {result.Bounds}");
                return;
            }

            var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
            var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);

            if (clearTitle.Found)
                clearTitleConsecutive++;
            else
                clearTitleConsecutive = 0;

            if (retryClicks < 1 && sw.Elapsed >= TimeSpan.FromSeconds(2))
            {
                DetectionResult retryTouch = DetectionResult.NotFound;

                if (touch.Found)
                {
                    retryTouch = touch;
                }
                else if (clearTitleConsecutive >= 2 && frame.Width == 800 && frame.Height == 1000)
                {
                    retryTouch = new DetectionResult(
                        true,
                        new Rectangle(360, 915, 80, 60),
                        clearTitle.Score,
                        "clear_touch_safe_retry");
                }

                if (retryTouch.Found)
                {
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    Log?.Invoke($"[어비스] 클리어 화면 유지 -> 안전 터치 1회 재시도 @ {retryTouch.Bounds} source={retryTouch.ReadText}");
                    _input.ClickClientPoint(_hwnd, retryTouch.Center);
                    retryClicks++;
                    await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);
                    continue;
                }
            }

            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }

        throw new TimeoutException("어비스 클리어 화면 클릭 후 실제 결과 화면을 30초 안에 확인하지 못했습니다. 다시 하기 단계로 넘어가지 않습니다.");
    }
'''
if old_wait_gone not in s:
    raise SystemExit("old WaitForAbyssClearScreenGoneAsync block not found")
s = s.replace(old_wait_gone, new_wait_gone, 1)

old_advance = '''    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)
    {
        _ = firstDetection; // Recognition proves clear; it is never used as a click position in v67.
        Log?.Invoke("[어비스] 클리어 이미지 2회 확인 완료 -> 터치 문구 이미지를 별도로 찾음");

        var touch = await WaitForAbyssTouchPromptAsync(ct);
        if (!touch.Found)
            return; // The clear screen already disappeared stably while waiting.

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[어비스] '화면을 터치해 주세요' 위치 클릭 @ {touch.Bounds}");
        _input.ClickClientPoint(_hwnd, touch.Center);
        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);

        // Do not start the 120-second treasure timer after a single missed frame.
        // The result screen must be absent in three consecutive captures first.
        await WaitForAbyssClearScreenGoneAsync(ct);
    }
'''
new_advance = '''    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)
    {
        // DetectAbyssConfirmedClearAsync returns the touch-prompt detection itself after
        // clear-title + touch are simultaneously confirmed. Use that confirmed point
        // immediately instead of throwing it away and trying to detect the prompt again.
        var touch = firstDetection.Found ? firstDetection : await WaitForAbyssTouchPromptAsync(ct);

        if (!touch.Found)
        {
            // NotFound is allowed only when WaitForAbyssTouchPromptAsync already proved
            // that the real result screen is visible.
            Log?.Invoke("[어비스] 실제 결과 화면이 이미 확인됨 -> 클리어 터치 생략");
            return;
        }

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[어비스] 확인된 '화면을 터치해 주세요' 위치 클릭 @ {touch.Bounds} source={touch.ReadText}");
        _input.ClickClientPoint(_hwnd, touch.Center);
        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);

        // Step 5 is not complete until the actual result screen is confirmed.
        await WaitForAbyssClearScreenGoneAsync(ct);
    }
'''
if old_advance not in s:
    raise SystemExit("old AdvanceAbyssClearScreenAsync block not found")
s = s.replace(old_advance, new_advance, 1)

write(engine, s)

project = app / "FishingAutomation.csproj"
p = read(project)
for old, new in (
    ("<Version>0.1.53</Version>", "<Version>0.1.54</Version>"),
    ("<AssemblyVersion>0.1.53.0</AssemblyVersion>", "<AssemblyVersion>0.1.54.0</AssemblyVersion>"),
    ("<FileVersion>0.1.53.0</FileVersion>", "<FileVersion>0.1.54.0</FileVersion>"),
):
    if old in p:
        p = p.replace(old, new, 1)
write(project, p)

update = app / "UpdateManager.cs"
u = read(update)
if 'CurrentVersion = "V0.1.53"' not in u:
    raise SystemExit("UpdateManager V0.1.53 marker missing")
u = u.replace('CurrentVersion = "V0.1.53"', 'CurrentVersion = "V0.1.54"', 1)
write(update, u)

t = read(engine)
required = (
    'missing clear/touch templates is NOT treated as a successful',
    'var result = await DetectAbyssResultRetryAsync(frame, ct);',
    'new Rectangle(360, 915, 80, 60)',
    'Step 5 is not complete until the actual result screen is confirmed.',
    '어비스 클리어 화면 클릭 후 실제 결과 화면을 30초 안에 확인하지 못했습니다.',
)
for marker in required:
    if marker not in t:
        raise SystemExit(f"required V0.1.54 marker missing: {marker}")

for forbidden in (
    '클리어 화면이 이미 3회 연속 사라짐 -> 전환 완료로 처리',
    'return; // The clear screen already disappeared stably while waiting.',
):
    if forbidden in t:
        raise SystemExit(f"old premature clear-transition success remains: {forbidden}")

if "<Version>0.1.54</Version>" not in read(project):
    raise SystemExit("project version not V0.1.54")
if 'CurrentVersion = "V0.1.54"' not in read(update):
    raise SystemExit("UpdateManager version not V0.1.54")

print("V0.1.54 applied: clear step cannot finish before actual Abyss result screen")
