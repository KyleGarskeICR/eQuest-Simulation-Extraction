$ErrorActionPreference = "Stop"

$RepoPath = "A:\Users\kyleg\PycharmProjects\eQuest-Simulation-Extraction"
$SimPath = "A:\Users\kyleg\PycharmProjects\eQuest-Simulation-Extraction\sample_data\St Anselm Baseline ABS_Rev_0 - Baseline Design.SIM"
$WorkbookPath = "A:\Users\kyleg\PycharmProjects\eQuest-Simulation-Extraction\output_files\Building Performance Assumptions.xlsm"
$MasterRoomOut = "A:\Users\kyleg\PycharmProjects\eQuest-Simulation-Extraction\output_files\Building Performance Assumptions.master_room.updated.xlsm"
$EcmOut = "A:\Users\kyleg\PycharmProjects\eQuest-Simulation-Extraction\output_files\Building Performance Assumptions.ecm.updated.xlsm"

Set-Location $RepoPath

function Invoke-PythonChecked {
    param([string[]]$Args)
    python @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: python $($Args -join ' ')"
    }
}

if (!(Test-Path $SimPath)) { throw "SIM file not found: $SimPath" }
if (!(Test-Path $WorkbookPath)) { throw "Workbook file not found: $WorkbookPath" }

Invoke-PythonChecked @("--version")
Invoke-PythonChecked @("equest_extractor.py", "--help")
python -c "import openpyxl; print('openpyxl available')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "openpyxl is not installed. Workbook writes will use XML fallback mode."
}

$simHasBeps = Select-String -Path $SimPath -Pattern "REPORT-\s*BEPS" -Quiet

# 1) Extract BEPS JSON sanity check
if ($simHasBeps) {
    Invoke-PythonChecked @("equest_extractor.py", $SimPath, "--report", "beps")
} else {
    Write-Warning "BEPS section not found in SIM. Skipping '--report beps' and ECM Data population."
}

# 2) Populate Master Room List (Baseline)
Invoke-PythonChecked @(
    "equest_extractor.py", $SimPath,
    "--populate-master-room-list", $WorkbookPath,
    "--model-run-type", "Baseline",
    "--output-workbook", $MasterRoomOut
)

# 3) Populate ECM Data (ECM-1)
if ($simHasBeps) {
    Invoke-PythonChecked @(
        "equest_extractor.py", $SimPath,
        "--update-ecm-data", $WorkbookPath,
        "--model-run-type", "ECM-1",
        "--output-workbook", $EcmOut
    )
}

Write-Host "Done. Output files:"
Write-Host $MasterRoomOut
if ($simHasBeps) { Write-Host $EcmOut }
