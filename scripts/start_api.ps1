# Start Chargeback Sentinel (API + notes for UI)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
$env:PYTHONPATH = (Get-Location).Path

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
  Write-Host "Creating venv..."
  python -m venv .venv
  .\.venv\Scripts\pip install -r requirements.txt
}

if (-not (Test-Path .\ml\artifacts\xgb.joblib)) {
  Write-Host "Training model artifacts..."
  .\.venv\Scripts\python -m data.synthetic.generator
  .\.venv\Scripts\python -m ml.training.train --final-test
}

Write-Host "API: http://127.0.0.1:8000/docs"
Write-Host "UI:  cd frontend; npm install; npm run dev  -> http://127.0.0.1:5173"
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
