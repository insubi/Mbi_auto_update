param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$auditPath = Join-Path $SourceRoot 'V71_UI_POLISH_AUDIT.json'
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.base -ne 'v70' -or $audit.version -ne 'v71') { throw 'Expected audited v71 source based on v70' }
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Audited file missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "v71 source integrity mismatch: $($entry.Name)"
    }
}
$app = Join-Path $SourceRoot 'FishingAutomation'
$ui = Get-Content -LiteralPath (Join-Path $app 'MainForm.ReferenceUI.cs') -Raw
foreach ($required in @(
    'TextAt(g, "Mabi_Auto", new(76, 15, 175, 44), 24, true, Color.White)',
    'TextAt(g, "v71", new(257, 20, 64, 34), 14, true, _cyan)',
    'Card(g, new(1048, 145, 342, 66))',
    'Text = "자동 정지"',
    'new MaskedTextBox("00:00")',
    'Font = new Font(_baseFont.FontFamily, 9.5f, FontStyle.Regular, GraphicsUnit.Point)',
    'var autoStopCheckBounds = new RectangleF(1063, 154, 166, 48)',
    'var autoStopTimeBounds = new RectangleF(1242, 154, 128, 48)')) {
    if (-not $ui.Contains($required)) { throw "v71 UI invariant missing: $required" }
}
if ($ui.Contains('TextAt(g, "v70"')) { throw 'v70 HOME version text remains' }
if ($ui.Contains('var autoStopTime = new DateTimePicker')) { throw 'Legacy white DateTimePicker remains' }

# Preview artwork must be byte-for-byte unchanged from the v70 base.
foreach ($entry in $audit.preserved_preview_hashes.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Abyss preview missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "Abyss preview changed unexpectedly: $($entry.Name)"
    }
}
foreach ($required in @('AddButton("텔레그램"','ShowTelegramSettings','LoadDungeonPreview("hallucination_anchorage.png")','LoadDungeonPreview("madness_cave.png")','LoadDungeonPreview("scattered_waterway.png")')) {
    if (-not $ui.Contains($required)) { throw "Required v70 HOME/Abyss behavior missing: $required" }
}
$engine = Get-Content -LiteralPath (Join-Path $app 'dungeon/ScenarioEngine.cs') -Raw
foreach ($required in @('TryAbyssInternalRecoveryAsync','abyss_treasure_chest','abyss_exit','abyss_menu')) {
    if (-not $engine.Contains($required)) { throw "Abyss flow invariant missing: $required" }
}
$manifest = Get-Content -LiteralPath (Join-Path $app 'app.manifest') -Raw
if ($manifest -notmatch 'requestedExecutionLevel\s+level="requireAdministrator"') { throw 'Administrator elevation was lost' }
Write-Host 'V71 SOURCE VERIFIED: HOME title/auto-stop polished; v70 Abyss preview artwork and runtime behavior preserved.'
