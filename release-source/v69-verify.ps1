param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$auditPath = Join-Path $SourceRoot 'V69_UI_ABYSS_AUDIT.json'
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.base -ne 'v68' -or $audit.version -ne 'v69') { throw 'Expected audited v69 source based on v68' }
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Audited file missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "v69 source integrity mismatch: $($entry.Name)"
    }
}
$app = Join-Path $SourceRoot 'FishingAutomation'
$ui = Get-Content -LiteralPath (Join-Path $app 'MainForm.ReferenceUI.cs') -Raw
if ($ui -match 'AddButton\("생활"' -or $ui -match 'AddButton\("설정"') { throw 'Removed HOME navigation remains' }
foreach ($required in @('AddButton("텔레그램"','ShowTelegramSettings','LoadDungeonPreview("hallucination_anchorage.png")','LoadDungeonPreview("madness_cave.png")','LoadDungeonPreview("scattered_waterway.png")')) {
    if (-not $ui.Contains($required)) { throw "Required HOME UI behavior missing: $required" }
}
$dialog = Get-Content -LiteralPath (Join-Path $app 'TelegramSettingsDialog.cs') -Raw
foreach ($required in @('봇 토큰','채팅 ID','저장','취소','notification.json')) {
    if (-not $dialog.Contains($required)) { throw "Telegram dialog behavior missing: $required" }
}
$targets = Get-Content -LiteralPath (Join-Path $app 'abyss/config/targets.json') -Raw | ConvertFrom-Json
$byId = @{}; foreach ($target in $targets) { $byId[$target.Id] = $target }
foreach ($id in @('abyss_dungeon_clear_visual','abyss_touch_screen')) {
    if (-not $byId.ContainsKey($id) -or $byId[$id].Kind -ne 'template') { throw "Clear target must be template-only: $id" }
    if (-not $byId[$id].TemplatePath) { throw "Clear image path missing: $id" }
}
if ($byId.ContainsKey('abyss_clear_grade_s')) { throw 'S-rank clear target must not exist' }
$engine = Get-Content -LiteralPath (Join-Path $app 'dungeon/ScenarioEngine.cs') -Raw
foreach ($required in @('abyssClearConsecutive < 2','clearDetectedConsecutive < 2','clearGoneConsecutive < 3','TryAbyssInternalRecoveryAsync','abyss_treasure_chest','abyss_exit','abyss_menu')) {
    if (-not $engine.Contains($required)) { throw "Abyss flow invariant missing: $required" }
}
if ($engine -match 'DetectAsync\("abyss_clear_grade_s"') { throw 'S-rank detection remains in executable flow' }
$manifest = Get-Content -LiteralPath (Join-Path $app 'app.manifest') -Raw
if ($manifest -notmatch 'requestedExecutionLevel\s+level="requireAdministrator"') { throw 'Administrator elevation was lost' }
Write-Host 'V69 SOURCE VERIFIED: HOME UI, Telegram persistence, preview paths, image-only clear flow and recovery invariants OK.'
