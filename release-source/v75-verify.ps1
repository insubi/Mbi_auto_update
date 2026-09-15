param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$auditPath = Join-Path $SourceRoot 'V0_1_2_STABILITY_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.2 audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.2' -or $audit.technical_bridge_tag -ne 'v75' -or $audit.base_public_version -ne 'V0.1.1') {
    throw 'Expected audited V0.1.2 source based on V0.1.1 with v75 bridge tag'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Audited file missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "V0.1.2 source integrity mismatch: $($entry.Name)"
    }
}

$app = Join-Path $SourceRoot 'FishingAutomation'
$update = Get-Content -LiteralPath (Join-Path $app 'UpdateManager.cs') -Raw
foreach ($required in @(
    'public const string CurrentVersion = "V0.1.2";',
    "bool currentUsesSemanticVersion = CurrentVersion.Contains('.', StringComparison.Ordinal);",
    'if (currentUsesSemanticVersion && !hasDot) return false;')) {
    if (-not $update.Contains($required)) { throw "V0.1.2 updater invariant missing: $required" }
}

$project = Get-Content -LiteralPath (Join-Path $app 'FishingAutomation.csproj') -Raw
foreach ($required in @('<Version>0.1.2</Version>','<AssemblyVersion>0.1.2.0</AssemblyVersion>','<FileVersion>0.1.2.0</FileVersion>')) {
    if (-not $project.Contains($required)) { throw "V0.1.2 project version invariant missing: $required" }
}

$engine = Get-Content -LiteralPath (Join-Path $app 'dungeon/ScenarioEngine.cs') -Raw
foreach ($required in @(
    'DetectAbyssConfirmedClearAsync',
    '클리어 화면 동시 이미지 확인 완료',
    '클리어 후보 점수: title=',
    'TryAbyssInternalRecoveryAsync',
    'DetectAbyssOutsideWorkflowAsync',
    'outsideAbyssIconConsecutive >= 2',
    'Smart Recovery 상태 확인용 메뉴 열기',
    '어비스 메뉴 2회 확인 -> 던전 밖 확정 및 메뉴 닫기 완료',
    'WaitForAbyssHomeAfterNormalExitAsync',
    '나가기 후 어비스 메뉴 확인 {abyssIconConsecutive}/2',
    '던전 밖 어비스 메뉴 2회 확인 + 메뉴 닫기 완료',
    'PruneDebugScreenshots',
    'MaxDebugFiles = 200',
    'MaxDebugBytes = 268435456')) {
    if (-not $engine.Contains($required)) { throw "V0.1.2 Abyss/recovery invariant missing: $required" }
}
if ($engine.Contains('클리어 화면 동시 이미지 연속 확인 {abyssClearConsecutive}/3') -or
    $engine.Contains('if (abyssClearConsecutive < 3)')) {
    throw 'Old BOTH+3 clear gate remains; normal clear could still stall'
}
if ($engine.Contains('outsideMenuConsecutive') -or
    $engine.Contains('[어비스 자동복구] 던전 밖 메뉴 확인 완료 -> 처음부터 재시작')) {
    throw 'Recovery still contains menu-icon-only outside confirmation'
}

$matcher = Get-Content -LiteralPath (Join-Path $app 'dungeon/TemplateMatcher.cs') -Raw
if (-not $matcher.Contains('return new DetectionResult(false, bounds, bestScore, null);')) {
    throw 'Template matcher no longer preserves below-threshold best score for diagnostics'
}

$main = Get-Content -LiteralPath (Join-Path $app 'MainForm.cs') -Raw
foreach ($required in @(
    'private DateTime _autoStopLastCheck = DateTime.Now;',
    'DateTime previous = _autoStopLastCheck;',
    'previous < scheduled && now >= scheduled',
    '_autoStopLastCheck = DateTime.Now;')) {
    if (-not $main.Contains($required)) { throw "Auto-stop missed-minute guard missing: $required" }
}

$abyssTargetsPath = Join-Path $app 'abyss/config/targets.json'
$abyssTargets = Get-Content -LiteralPath $abyssTargetsPath -Raw | ConvertFrom-Json
$scene = @($abyssTargets | Where-Object { $_.Id -eq 'scene_skip' })
if ($scene.Count -ne 1 -or $scene[0].Kind -ne 'template') { throw 'Abyss scene_skip must be template-only' }
if ($scene[0].PSObject.Properties.Name -contains 'Text') { throw 'Abyss scene_skip OCR fallback still present' }
if ($scene[0].Roi.X -lt 400 -or $scene[0].Roi.Y -lt 15 -or $scene[0].Roi.Width -gt 400 -or $scene[0].Roi.Height -gt 220) {
    throw 'Abyss scene_skip ROI is not constrained to the top-right cutscene area'
}
$popup = @($abyssTargets | Where-Object { $_.Id -eq 'abyss_popup_close' })
if ($popup.Count -ne 1 -or $popup[0].Kind -ne 'template') { throw 'Abyss popup-close must remain template-only' }

# Decode every runtime recognition image now so a corrupt PNG/JPEG can never ship silently again.
Add-Type -AssemblyName System.Drawing
$templateRoots = @(
    (Join-Path $app 'abyss/templates'),
    (Join-Path $app 'dungeon/templates')
)
foreach ($root in $templateRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    foreach ($file in Get-ChildItem -LiteralPath $root -File | Where-Object { $_.Extension -match '^\.(png|jpg|jpeg|bmp)$' }) {
        $img = $null
        try {
            $img = [System.Drawing.Image]::FromFile($file.FullName)
            if ($img.Width -lt 2 -or $img.Height -lt 2) { throw "Invalid dimensions: $($img.Width)x$($img.Height)" }
        } catch {
            throw "Template decode failed: $($file.FullName): $($_.Exception.Message)"
        } finally {
            if ($null -ne $img) { $img.Dispose() }
        }
    }
}

foreach ($entry in $audit.repaired_template_hashes.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Repaired template missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "Repaired template changed: $($entry.Name)"
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
    if (-not $ui.Contains($required)) { throw "Preserved HOME UI invariant missing: $required" }
}
$manifest = Get-Content -LiteralPath (Join-Path $app 'app.manifest') -Raw
if ($manifest -notmatch 'requestedExecutionLevel\s+level="requireAdministrator"') { throw 'Administrator elevation was lost' }
Write-Host 'V0.1.2 SOURCE VERIFIED: immediate BOTH-image clear, menu-probe outside confirmation, state-aware recovery, verified exit, repaired template-only monitors, missed-minute auto-stop guard, debug pruning, and image decode validation.'
