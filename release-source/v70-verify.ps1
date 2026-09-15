param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$auditPath = Join-Path $SourceRoot 'V70_AUTOSTOP_UI_AUDIT.json'
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.base -ne 'v69' -or $audit.version -ne 'v70') { throw 'Expected audited v70 source based on v69' }
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Audited file missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "v70 source integrity mismatch: $($entry.Name)"
    }
}
$app = Join-Path $SourceRoot 'FishingAutomation'
$ui = Get-Content -LiteralPath (Join-Path $app 'MainForm.ReferenceUI.cs') -Raw
foreach ($required in @(
    'Text = "자동 정지"',
    'new MaskedTextBox("00:00")',
    'BackColor = Color.FromArgb(3, 29, 51)',
    'ForeColor = Color.White',
    'BorderStyle = BorderStyle.FixedSingle',
    'Font = new Font(_baseFont.FontFamily, 9.5f, FontStyle.Bold, GraphicsUnit.Point)',
    'var autoStopCheckBounds = new RectangleF(1068, 154, 160, 48)',
    'var autoStopTimeBounds = new RectangleF(1240, 154, 132, 48)')) {
    if (-not $ui.Contains($required)) { throw "v70 auto-stop UI invariant missing: $required" }
}
if ($ui.Contains('var autoStopLabel = new Label')) { throw 'Legacy separate auto-stop label remains' }
if ($ui.Contains('var autoStopTime = new DateTimePicker')) { throw 'Legacy white DateTimePicker remains' }
if ($ui -match 'Text\s*=\s*"자동"\s*[,;]') { throw 'Clipped auto-stop caption remains' }

# Preserve v69 UI/features and Abyss behavior.
foreach ($required in @('AddButton("텔레그램"','ShowTelegramSettings','LoadDungeonPreview("hallucination_anchorage.png")','LoadDungeonPreview("madness_cave.png")','LoadDungeonPreview("scattered_waterway.png")')) {
    if (-not $ui.Contains($required)) { throw "Required v69 HOME UI behavior missing: $required" }
}
$engine = Get-Content -LiteralPath (Join-Path $app 'dungeon/ScenarioEngine.cs') -Raw
foreach ($required in @('TryAbyssInternalRecoveryAsync','abyss_treasure_chest','abyss_exit','abyss_menu')) {
    if (-not $engine.Contains($required)) { throw "Abyss flow invariant missing: $required" }
}
$manifest = Get-Content -LiteralPath (Join-Path $app 'app.manifest') -Raw
if ($manifest -notmatch 'requestedExecutionLevel\s+level="requireAdministrator"') { throw 'Administrator elevation was lost' }
Write-Host 'V70 SOURCE VERIFIED: scheduled-stop caption/font/dark time field fixed; v69 HOME/Telegram/Abyss behavior preserved.'
