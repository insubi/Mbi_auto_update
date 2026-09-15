param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$auditPath = Join-Path $SourceRoot 'V0_1_7_FISHING_CAPTURE_RESYNC_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.7 fishing capture resync audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.7' -or $audit.technical_bridge_tag -ne 'v80' -or $audit.base_public_version -ne 'V0.1.6') {
    throw 'Expected audited V0.1.7 source based on V0.1.6 with v80 bridge tag'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.7 source file missing: $($entry.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) { throw "V0.1.7 source integrity mismatch: $($entry.Name)" }
}

$capture = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/CaptureService.cs') -Raw
foreach ($marker in @(
    'NativeMethods.GetClientRect(window.Handle, out var liveClient)',
    'NativeMethods.ClientToScreen(window.Handle, ref liveOrigin)',
    'captureX = liveOrigin.X;',
    'captureY = liveOrigin.Y;',
    'FishingFocusGuard.IsForeground(window.Handle)',
    'FishingFocusGuard.Activate(window.Handle);')) {
    if (-not $capture.Contains($marker)) { throw "V0.1.7 live capture geometry invariant missing: $marker" }
}
if ($capture.Contains('g.CopyFromScreen(window.ClientScreenOrigin.X')) { throw 'V0.1.7 still captures from stale cached client origin' }

$matcher = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/TemplateMatcher.cs') -Raw
foreach ($marker in @(
    'MatchResult primary = MatchVariants(gray, roi, _hookVariants);',
    'if (primary.Score >= 0.78) return primary;',
    'Rectangle recoveryRoi = new(',
    'MatchResult recovery = MatchVariants(gray, recoveryRoi, _hookVariants);')) {
    if (-not $matcher.Contains($marker)) { throw "V0.1.7 adaptive hook search missing: $marker" }
}

$start = Get-Content -LiteralPath (Join-Path $SourceRoot 'START.cmd') -Raw
$forcedHookCopy = 'copy /y "%ROOT%\FishingAutomation\templates\hook.png" "%ROOT%\release\templates\hook.png"'
if (-not $start.Contains($forcedHookCopy)) { throw 'V0.1.7 START.cmd does not force-refresh the current hook template' }
if ($start.Contains('if not exist "%ROOT%\release\templates\hook.png" copy /y')) { throw 'V0.1.7 still preserves a stale runtime hook template' }

$bot = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingBot.cs') -Raw
foreach ($marker in @(
    'double hookThreshold = Math.Min(_cfg.HookThreshold, 0.78);',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'stage1_hook_wait_8s',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도')) {
    if (-not $bot.Contains($marker)) { throw "V0.1.7 fishing invariant missing: $marker" }
}

$guard = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingFocusGuard.cs') -Raw
foreach ($marker in @('AttachThreadInput','BringWindowToTop','SetForegroundWindow','SetActiveWindow','SetFocus')) {
    if (-not $guard.Contains($marker)) { throw "V0.1.6 focus guard invariant lost: $marker" }
}

$config = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/config.json') -Raw
if (-not $config.Contains('"HookThreshold": 0.78')) { throw 'V0.1.7 must preserve HookThreshold 0.78' }

$update = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs') -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.7";')) { throw 'V0.1.7 updater version missing' }
Write-Host 'V0.1.7 SOURCE VERIFIED: live client origin is refreshed every capture, hook matching has lower-screen recovery search, runtime hook is force-refreshed, and 8-second stage1 diagnostics are retained.'
