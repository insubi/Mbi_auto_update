param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$auditPath = Join-Path $SourceRoot 'V0_1_1_ABYSS_CLEAR_GUARD_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.1 audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.1' -or $audit.technical_bridge_tag -ne 'v74' -or $audit.base_public_version -ne 'V0.1') {
    throw 'Expected audited V0.1.1 source based on V0.1 with v74 bridge tag'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Audited file missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "V0.1.1 source integrity mismatch: $($entry.Name)"
    }
}

$app = Join-Path $SourceRoot 'FishingAutomation'
$update = Get-Content -LiteralPath (Join-Path $app 'UpdateManager.cs') -Raw
foreach ($required in @(
    'public const string CurrentVersion = "V0.1.1";',
    "bool currentUsesSemanticVersion = CurrentVersion.Contains('.', StringComparison.Ordinal);",
    'if (currentUsesSemanticVersion && !hasDot) return false;')) {
    if (-not $update.Contains($required)) { throw "V0.1.1 updater invariant missing: $required" }
}

$project = Get-Content -LiteralPath (Join-Path $app 'FishingAutomation.csproj') -Raw
foreach ($required in @('<Version>0.1.1</Version>','<AssemblyVersion>0.1.1.0</AssemblyVersion>','<FileVersion>0.1.1.0</FileVersion>')) {
    if (-not $project.Contains($required)) { throw "V0.1.1 project version invariant missing: $required" }
}

$engine = Get-Content -LiteralPath (Join-Path $app 'dungeon/ScenarioEngine.cs') -Raw
foreach ($required in @(
    'DetectAbyssConfirmedClearAsync',
    'var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);',
    'var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);',
    'found = await DetectAbyssConfirmedClearAsync(frame, ct);',
    '클리어 화면 동시 이미지 연속 확인 {abyssClearConsecutive}/3',
    'if (abyssClearConsecutive < 3)',
    'var clearVisual = await DetectAbyssConfirmedClearAsync(frame, ct);',
    'private async Task<DetectionResult> DetectAbyssClearVisualAsync')) {
    if (-not $engine.Contains($required)) { throw "V0.1.1 Abyss clear guard missing: $required" }
}
if ($engine.Contains('found = await DetectAbyssClearVisualAsync(frame, ct);')) {
    throw 'Initial Abyss completion check still accepts OR clear detection'
}

$targetsPath = Join-Path $app 'abyss/config/targets.json'
$targetsHash = (Get-FileHash -LiteralPath $targetsPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($targetsHash -ne $audit.targets_json_sha256.ToLowerInvariant()) { throw 'Abyss target configuration changed unexpectedly' }
foreach ($entry in $audit.clear_template_hashes.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Clear template missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "Clear template changed unexpectedly: $($entry.Name)"
    }
}
foreach ($entry in $audit.preserved_preview_hashes.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Approved preview missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "Approved preview changed: $($entry.Name)"
    }
}

$ui = Get-Content -LiteralPath (Join-Path $app 'MainForm.ReferenceUI.cs') -Raw
foreach ($required in @('TextAt(g, UpdateManager.CurrentVersion','Text = "자동 정지"','LoadDungeonPreview("hallucination_anchorage.jpg")','LoadDungeonPreview("madness_cave.jpg")','LoadDungeonPreview("scattered_waterway.jpg")')) {
    if (-not $ui.Contains($required)) { throw "Preserved V0.1 HOME UI invariant missing: $required" }
}
$manifest = Get-Content -LiteralPath (Join-Path $app 'app.manifest') -Raw
if ($manifest -notmatch 'requestedExecutionLevel\s+level="requireAdministrator"') { throw 'Administrator elevation was lost' }
Write-Host 'V0.1.1 SOURCE VERIFIED: Abyss completion requires BOTH clear-title and touch-prompt images in 3 consecutive frames; V0.1 UI/runtime otherwise preserved.'
