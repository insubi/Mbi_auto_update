param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$auditPath = Join-Path $SourceRoot 'V0_1_4_FOCUS_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.4 focus audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.4' -or $audit.technical_bridge_tag -ne 'v77' -or $audit.base_public_version -ne 'V0.1.3') {
    throw 'Expected audited V0.1.4 source based on V0.1.3 with v77 bridge tag'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.4 source file missing: $($entry.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) { throw "V0.1.4 source integrity mismatch: $($entry.Name)" }
}
$guardPath = Join-Path $SourceRoot 'FishingAutomation/FishingFocusGuard.cs'
$guard = Get-Content -LiteralPath $guardPath -Raw
foreach ($marker in @('AttachThreadInput','BringWindowToTop','SetForegroundWindow','SetActiveWindow','SetFocus','마비노기 모바일')) {
    if (-not $guard.Contains($marker)) { throw "V0.1.4 focus guard invariant missing: $marker" }
}
$inputPath = Join-Path $SourceRoot ([string]$audit.keyboard_input_file)
$input = Get-Content -LiteralPath $inputPath -Raw
$guardCount = ([regex]::Matches($input, [regex]::Escape('global::FishingFocusGuard.Activate();'))).Count
if ($guardCount -lt @($audit.guarded_methods).Count) { throw "V0.1.4 keyboard guard count too small: $guardCount" }
if (-not (@($audit.guarded_methods) -contains 'Tap')) { throw 'V0.1.4 low-level Tap method was not guarded' }
$bot = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingBot.cs') -Raw
foreach ($marker in @('double hookThreshold = Math.Min(_cfg.HookThreshold, 0.82);','bool sent = _input.TapSpace();','Space 전송 실패 -> 재시도')) {
    if (-not $bot.Contains($marker)) { throw "V0.1.3 fishing invariant lost in V0.1.4: $marker" }
}
$start = Get-Content -LiteralPath (Join-Path $SourceRoot 'START.cmd') -Raw
foreach ($name in @('hook.png','gauge.png','healthbar.png','compass.png')) {
    $marker = 'if not exist "%ROOT%\release\templates\' + $name + '" copy /y'
    if (-not $start.Contains($marker)) { throw "V0.1.3 guarded template copy lost: $name" }
}
$update = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs') -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.4";')) { throw 'V0.1.4 updater version missing' }
Write-Host "V0.1.4 SOURCE VERIFIED: every fishing low-level Tap activates the game window first; guarded methods=$(@($audit.guarded_methods) -join ',')."
