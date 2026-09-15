param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$auditPath = Join-Path $SourceRoot 'V0_1_5_FISHING_RESYNC_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.5 fishing resync audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.5' -or $audit.technical_bridge_tag -ne 'v78' -or $audit.base_public_version -ne 'V0.1.4') {
    throw 'Expected audited V0.1.5 source based on V0.1.4 with v78 bridge tag'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.5 source file missing: $($entry.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) { throw "V0.1.5 source integrity mismatch: $($entry.Name)" }
}
$bot = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingBot.cs') -Raw
foreach ($marker in @(
    'double hookThreshold = Math.Min(_cfg.HookThreshold, 0.78);',
    'if (hook.Score >= Math.Min(_cfg.HookThreshold, 0.78))',
    'DateTime lastGaugeResync = DateTime.MinValue;',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    '상태 복구: 시전 대기 중 게이지 감지',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도')) {
    if (-not $bot.Contains($marker)) { throw "V0.1.5 fishing invariant missing: $marker" }
}
$rawOld = ([regex]::Matches($bot, [regex]::Escape('if (hook.Score >= _cfg.HookThreshold)'))).Count
if ($rawOld -ne 0) { throw "V0.1.5 left raw HookThreshold checks behind: $rawOld" }
$config = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/config.json') -Raw
if (-not $config.Contains('"HookThreshold": 0.78')) { throw 'V0.1.5 config HookThreshold is not 0.78' }
$guardPath = Join-Path $SourceRoot 'FishingAutomation/FishingFocusGuard.cs'
$guard = Get-Content -LiteralPath $guardPath -Raw
foreach ($marker in @('AttachThreadInput','BringWindowToTop','SetForegroundWindow','SetActiveWindow','SetFocus','마비노기 모바일')) {
    if (-not $guard.Contains($marker)) { throw "V0.1.4 focus guard invariant lost: $marker" }
}
$inputPath = Join-Path $SourceRoot ([string]$audit.keyboard_input_file)
$input = Get-Content -LiteralPath $inputPath -Raw
if (-not $input.Contains('global::FishingFocusGuard.Activate();')) { throw 'V0.1.4 low-level keyboard focus guard lost' }
$start = Get-Content -LiteralPath (Join-Path $SourceRoot 'START.cmd') -Raw
foreach ($name in @('hook.png','gauge.png','healthbar.png','compass.png')) {
    $marker = 'if not exist "%ROOT%\release\templates\' + $name + '" copy /y'
    if (-not $start.Contains($marker)) { throw "V0.1.3 guarded template copy lost: $name" }
}
$update = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs') -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.5";')) { throw 'V0.1.5 updater version missing' }
Write-Host 'V0.1.5 SOURCE VERIFIED: 0.78 two-frame hook recognition, live-gauge stage resync, and V0.1.4 focus guard are present.'
