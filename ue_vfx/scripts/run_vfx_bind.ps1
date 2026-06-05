# WorldFlex VFX auto-binding batch runner.
#
# Usage examples (PowerShell):
#   # 1. Detect only + speed curves (calibration pass, does NOT modify animations):
#   ./run_vfx_bind.ps1 -DetectOnly -Curves
#
#   # 2. Apply notifies after reviewing bind_report.json:
#   ./run_vfx_bind.ps1
#
#   # 3. Custom rules file / report path:
#   ./run_vfx_bind.ps1 -Rules D:/somewhere/my_rules.json -Report D:/somewhere/my_report.json

param(
    [string]$UeCmd   = "D:/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe",
    [string]$Project = "D:/document/Unreal Projects/特效探索/特效探索.uproject",
    [string]$Rules   = "D:/document/4D-avatar/samples/luffi_vfx_test/vfx_rules.json",
    [string]$Report  = "",   # default: bind_report.json next to the rules file
    [switch]$DetectOnly,     # -Apply=false
    [switch]$Curves          # include per-frame speed curves in the report
)

if (-not (Test-Path $UeCmd))   { Write-Error "UnrealEditor-Cmd.exe not found: $UeCmd"; exit 1 }
if (-not (Test-Path $Project)) { Write-Error "Project not found: $Project"; exit 1 }
if (-not (Test-Path $Rules))   { Write-Error "Rules file not found: $Rules"; exit 1 }

$applyValue = if ($DetectOnly) { "false" } else { "true" }
$curvesValue = if ($Curves) { "true" } else { "false" }

$ueArgs = @(
    "`"$Project`"",
    "-run=WorldFlexVFXBind",
    "-Rules=`"$Rules`"",
    "-Apply=$applyValue",
    "-Curves=$curvesValue",
    "-unattended",
    "-nopause",
    "-nosplash"
)
if ($Report -ne "") { $ueArgs += "-Report=`"$Report`"" }

Write-Host "== WorldFlexVFXBind =="
Write-Host "  Rules : $Rules"
Write-Host "  Apply : $applyValue  Curves: $curvesValue"

$process = Start-Process -FilePath $UeCmd -ArgumentList $ueArgs -NoNewWindow -PassThru -Wait
$code = $process.ExitCode

if ($Report -eq "") { $Report = Join-Path (Split-Path $Rules) "bind_report.json" }

switch ($code) {
    0 { Write-Host "OK: events detected$(if (-not $DetectOnly) { ' and applied' }). Report: $Report" }
    5 { Write-Warning "Finished but NO events detected. Open $Report and compare 'max_speed' / 'suggested_threshold' with your 'speed_threshold' values." }
    default { Write-Error "Failed with exit code $code. Check the UE log and $Report (rule_errors / status fields)." }
}
exit $code
