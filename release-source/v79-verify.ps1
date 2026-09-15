param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$auditPath = Join-Path $SourceRoot 'V0_1_6_FOREGROUND_CAPTURE_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.6 foreground capture audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.6' -or $audit.technical_bridge_tag -ne 'v79' -or $audit.base_public_version -ne 'V0.1.5') {
    throw 'Expected audited V0.1.6 source based on V0.1.5 with v79 bridge tag'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.6 source file missing: $($entry.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) { throw "V0.1.6 source integrity mismatch: $($entry.Name)" }
}

$capture = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/CaptureService.cs') -Raw
foreach ($marker in @(
    'FishingFocusGuard.IsForeground(window.Handle)',
    'FishingFocusGuard.Activate(window.Handle);',
    'Thread.Sleep(70);',
    'g.CopyFromScreen(window.ClientScreenOrigin.X')) {
    if (-not $capture.Contains($marker)) { throw "V0.1.6 capture foreground invariant missing: $marker" }
}

$guard = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingFocusGuard.cs') -Raw
foreach ($marker in @(
    'public static bool IsForeground(IntPtr target)',
    'public static bool Activate(IntPtr target)',
    'AttachThreadInput',
    'BringWindowToTop',
    'SetForegroundWindow',
    'SetActiveWindow',
    'SetFocus')) {
    if (-not $guard.Contains($marker)) { throw "V0.1.6 focus guard invariant missing: $marker" }
}

$native = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/NativeMethods.cs') -Raw
if (-not $native.Contains('FishingFocusGuard.Activate(window.Handle);')) { throw 'V0.1.6 WindowLocator still uses weak foreground activation' }

$bot = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingBot.cs') -Raw
foreach ($marker in @(
    'double hookThreshold = Math.Min(_cfg.HookThreshold, 0.78);',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도')) {
    if (-not $bot.Contains($marker)) { throw "V0.1.5 fishing invariant lost in V0.1.6: $marker" }
}

$main = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/MainForm.cs') -Raw
foreach ($marker in @('private string _lastFishingStatus = "준비";','_lastFishingStatus = s;','현재 상태: {_lastFishingStatus}')) {
    if (-not $main.Contains($marker)) { throw "V0.1.6 stall diagnostics missing: $marker" }
}

$config = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/config.json') -Raw
if (-not $config.Contains('"HookThreshold": 0.78')) { throw 'V0.1.6 must preserve V0.1.5 HookThreshold 0.78' }

$update = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs') -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.6";')) { throw 'V0.1.6 updater version missing' }
Write-Host 'V0.1.6 SOURCE VERIFIED: physical screen capture foregrounds the game when needed, weak WindowLocator activation is replaced, and stall alerts report the live fishing status.'
