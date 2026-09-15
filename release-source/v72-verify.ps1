param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$auditPath = Join-Path $SourceRoot 'V72_SCENIC_PREVIEW_AUDIT.json'
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.base -ne 'v71' -or $audit.version -ne 'v72') { throw 'Expected audited v72 source based on v71' }
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Audited file missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "v72 source integrity mismatch: $($entry.Name)"
    }
}

$app = Join-Path $SourceRoot 'FishingAutomation'
$ui = Get-Content -LiteralPath (Join-Path $app 'MainForm.ReferenceUI.cs') -Raw
foreach ($required in @(
    'TextAt(g, "Mabi_Auto", new(76, 15, 175, 44), 24, true, Color.White)',
    'TextAt(g, "v72", new(257, 20, 64, 34), 14, true, _cyan)',
    'Card(g, new(1048, 145, 342, 66))',
    'Text = "자동 정지"',
    'new MaskedTextBox("00:00")',
    'LoadDungeonPreview("hallucination_anchorage.jpg")',
    'LoadDungeonPreview("madness_cave.jpg")',
    'LoadDungeonPreview("scattered_waterway.jpg")',
    'Path.Combine(AppContext.BaseDirectory, "abyss", "previews", fileName)')) {
    if (-not $ui.Contains($required)) { throw "v72 UI/preview invariant missing: $required" }
}
if ($ui.Contains('Path.Combine(AppContext.BaseDirectory, "abyss", "templates", fileName)')) {
    throw 'HOME preview loader still points at recognition templates'
}

$expectedPreviewHashes = @{
    'FishingAutomation/abyss/previews/hallucination_anchorage.jpg' = '0195c292d2b32cb369d2561ab01227e4b7120e9cade8178cc174d40bf8ceeb9d'
    'FishingAutomation/abyss/previews/madness_cave.jpg' = 'e6af39c665f1126dde46f17054589413b88690a0eaae56fc14e06a6434b4e50e'
    'FishingAutomation/abyss/previews/scattered_waterway.jpg' = 'e554e07e40a3b07def8ef9f6ffe2f659c6a35097e02d14a9007a0a6fab8ccfdd'
}
foreach ($entry in $expectedPreviewHashes.GetEnumerator()) {
    $path = Join-Path $SourceRoot $entry.Key
    if (-not (Test-Path -LiteralPath $path)) { throw "Scenic preview missing: $($entry.Key)" }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $entry.Value) { throw "Unexpected scenic preview hash: $($entry.Key)" }
}

# Detection templates must remain byte-for-byte unchanged from v71.
foreach ($entry in $audit.preserved_recognition_template_hashes.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Recognition template missing: $($entry.Name)" }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $entry.Value.ToLowerInvariant()) { throw "Recognition template changed unexpectedly: $($entry.Name)" }
}

foreach ($required in @('AddButton("텔레그램"','ShowTelegramSettings')) {
    if (-not $ui.Contains($required)) { throw "Required HOME/Telegram behavior missing: $required" }
}
$engine = Get-Content -LiteralPath (Join-Path $app 'dungeon/ScenarioEngine.cs') -Raw
foreach ($required in @('TryAbyssInternalRecoveryAsync','abyss_treasure_chest','abyss_exit','abyss_menu')) {
    if (-not $engine.Contains($required)) { throw "Abyss flow invariant missing: $required" }
}
$manifest = Get-Content -LiteralPath (Join-Path $app 'app.manifest') -Raw
if ($manifest -notmatch 'requestedExecutionLevel\s+level="requireAdministrator"') { throw 'Administrator elevation was lost' }
Write-Host 'V72 SOURCE VERIFIED: scenic HOME preview assets separated from recognition templates; v71 UI and runtime behavior preserved.'
