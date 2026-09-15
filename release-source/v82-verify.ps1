param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$auditPath = Join-Path $SourceRoot 'V0_1_9_HUD_FALLBACK_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.9 HUD fallback audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.9' -or $audit.technical_bridge_tag -ne 'v82' -or $audit.base_public_version -ne 'V0.1.8') {
    throw 'Expected audited V0.1.9 source based on V0.1.8 with v82 bridge tag'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.9 source file missing: $($entry.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) { throw "V0.1.9 source integrity mismatch: $($entry.Name)" }
}

$bot = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingBot.cs') -Raw
foreach ($marker in @(
    'bool hookHud = LooksLikeFishingCastHud(f.Bgr);',
    'if (hook.Score >= hookThreshold || hookHud)',
    'private static bool LooksLikeFishingCastHud(OpenCvSharp.Mat bgr)',
    'bgr.Width * 0.42',
    'bgr.Width * 0.58',
    'bgr.Height * 0.80',
    'bgr.Height * 0.94',
    'green >= 240 && white >= 35 && red >= 5',
    'if (hookFrames >= 3)',
    'Math.Min(_cfg.HookThreshold, 0.72)',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'stage1_hook_wait_8s',
    'Space 전송 실패 -> 재시도')) {
    if (-not $bot.Contains($marker)) { throw "V0.1.9 fishing invariant missing: $marker" }
}
$hudUseCount = ([regex]::Matches($bot, [regex]::Escape('LooksLikeFishingCastHud(f.Bgr)'))).Count
if ($hudUseCount -lt 3) { throw "V0.1.9 expected HUD fallback in start/end/next-ready paths, found $hudUseCount" }

$matcher = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/TemplateMatcher.cs') -Raw
foreach ($marker in @(
    'if (primary.Score >= 0.72) return primary;',
    'gray.Width * 0.28',
    'gray.Width * 0.72',
    'gray.Height * 0.72',
    'gray.Height * 0.97')) {
    if (-not $matcher.Contains($marker)) { throw "V0.1.8 primary template invariant lost: $marker" }
}

$config = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/config.json') -Raw
if (-not $config.Contains('"HookThreshold": 0.72')) { throw 'V0.1.9 must preserve config HookThreshold 0.72' }

$capture = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/CaptureService.cs') -Raw
foreach ($marker in @(
    'NativeMethods.GetClientRect(window.Handle, out var liveClient)',
    'NativeMethods.ClientToScreen(window.Handle, ref liveOrigin)',
    'FishingFocusGuard.IsForeground(window.Handle)',
    'FishingFocusGuard.Activate(window.Handle);')) {
    if (-not $capture.Contains($marker)) { throw "V0.1.7 capture invariant lost: $marker" }
}

$guard = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingFocusGuard.cs') -Raw
foreach ($marker in @('AttachThreadInput','BringWindowToTop','SetForegroundWindow','SetActiveWindow','SetFocus')) {
    if (-not $guard.Contains($marker)) { throw "V0.1.6 focus guard invariant lost: $marker" }
}

$start = Get-Content -LiteralPath (Join-Path $SourceRoot 'START.cmd') -Raw
$forcedHookCopy = 'copy /y "%ROOT%\FishingAutomation\templates\hook.png" "%ROOT%\release\templates\hook.png"'
if (-not $start.Contains($forcedHookCopy)) { throw 'V0.1.7 runtime hook refresh lost' }

$update = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs') -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.9";')) { throw 'V0.1.9 updater version missing' }
Write-Host 'V0.1.9 SOURCE VERIFIED: primary template recognition plus fixed lower-center HUD color fallback are present across start/end/next-ready paths.'
