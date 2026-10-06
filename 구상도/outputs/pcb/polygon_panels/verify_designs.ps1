$ErrorActionPreference = 'Stop'
$toolPath = Join-Path $env:LOCALAPPDATA 'Programs\KiCad\bin\kicad-cli.exe'
if (-not (Test-Path -LiteralPath $toolPath)) {
    $found = Get-Command kicad-cli -ErrorAction SilentlyContinue
    if ($found) { $toolPath = $found.Source }
    else { throw 'KiCad CLI not found. Install KiCad 10 or add its bin directory to PATH.' }
}
$failedChecks = 0
foreach ($faceCount in @(6,8)) {
    $designName = "panel_${faceCount}faces_16ch"
    $designDir = Join-Path $PSScriptRoot $designName
    $reportDir = Join-Path $designDir 'recheck'
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    & $toolPath sch erc (Join-Path $designDir "$designName.kicad_sch") --format json --exit-code-violations -o (Join-Path $reportDir 'ERC.json')
    if ($LASTEXITCODE -ne 0) { $failedChecks++ }
    & $toolPath pcb drc (Join-Path $designDir "$designName.kicad_pcb") --format json --schematic-parity --exit-code-violations -o (Join-Path $reportDir 'DRC.json')
    if ($LASTEXITCODE -ne 0) { $failedChecks++ }
}
if ($failedChecks -gt 0) { throw "$failedChecks checks failed. Read the JSON reports in each recheck directory." }
Write-Host 'PASS: ERC, DRC and schematic parity for both prototype panels.'
