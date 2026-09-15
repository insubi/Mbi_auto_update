param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$auditPath = Join-Path $SourceRoot 'V0_1_RELEASE_AUDIT.json'
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.base -ne 'v72' -or $audit.version -ne 'V0.1' -or $audit.technical_bridge_tag -ne 'v73') {
    throw 'Expected audited V0.1 source based on v72 with v73 bridge tag'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Audited file missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "V0.1 source integrity mismatch: $($entry.Name)"
    }
}

$app = Join-Path $SourceRoot 'FishingAutomation'
$update = Get-Content -LiteralPath (Join-Path $app 'UpdateManager.cs') -Raw
foreach ($required in @(
    'public const string CurrentVersion = "V0.1";',
    "bool currentUsesSemanticVersion = CurrentVersion.Contains('.', StringComparison.Ordinal);",
    'if (currentUsesSemanticVersion && !hasDot) return false;')) {
    if (-not $update.Contains($required)) { throw "V0.1 updater invariant missing: $required" }
}

$project = Get-Content -LiteralPath (Join-Path $app 'FishingAutomation.csproj') -Raw
foreach ($required in @('<Version>0.1.0</Version>','<AssemblyVersion>0.1.0.0</AssemblyVersion>','<FileVersion>0.1.0.0</FileVersion>')) {
    if (-not $project.Contains($required)) { throw "V0.1 project version invariant missing: $required" }
}

$ui = Get-Content -LiteralPath (Join-Path $app 'MainForm.ReferenceUI.cs') -Raw
foreach ($required in @(
    'Artwork(g, new(30, 22, 32, 30), new(27, 21, 39, 37))',
    'TextAt(g, "Mabi_Auto", new(78, 14, 170, 43), 25, true, Color.White)',
    'Card(g, new(252, 16, 78, 35))',
    'TextAt(g, UpdateManager.CurrentVersion, new(252, 18, 78, 31), 14, true, _cyan, StringAlignment.Center)',
    'Card(g, new(1054, 151, 312, 54))',
    'var autoStopCheckBounds = new RectangleF(1065, 158, 154, 38)',
    'var autoStopTimeBounds = new RectangleF(1235, 160, 110, 34)',
    'TextAlign = HorizontalAlignment.Center',
    'LoadDungeonPreview("hallucination_anchorage.jpg")',
    'LoadDungeonPreview("madness_cave.jpg")',
    'LoadDungeonPreview("scattered_waterway.jpg")')) {
    if (-not $ui.Contains($required)) { throw "V0.1 HOME UI invariant missing: $required" }
}

foreach ($entry in $audit.preserved_preview_hashes.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Approved preview missing: $($entry.Name)" }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $entry.Value.ToLowerInvariant()) { throw "Approved preview changed: $($entry.Name)" }
}

foreach ($required in @('AddButton("텔레그램"','ShowTelegramSettings')) {
    if (-not $ui.Contains($required)) { throw "Required Telegram behavior missing: $required" }
}
$engine = Get-Content -LiteralPath (Join-Path $app 'dungeon/ScenarioEngine.cs') -Raw
foreach ($required in @('TryAbyssInternalRecoveryAsync','abyss_treasure_chest','abyss_exit','abyss_menu')) {
    if (-not $engine.Contains($required)) { throw "Abyss flow invariant missing: $required" }
}
$manifest = Get-Content -LiteralPath (Join-Path $app 'app.manifest') -Raw
if ($manifest -notmatch 'requestedExecutionLevel\s+level="requireAdministrator"') { throw 'Administrator elevation was lost' }
Write-Host 'V0.1 SOURCE VERIFIED: public semantic version, polished HOME brand/auto-stop, v72 Abyss artwork/runtime preserved.'
