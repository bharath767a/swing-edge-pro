Write-Host "======================================="
Write-Host "  SwingEdge Pro — Starting..."
Write-Host "======================================="
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env created — please add API keys for better accuracy."
}
pip install -r requirements.txt --quiet
Set-Location backend
Write-Host ""
Write-Host "Starting server at http://localhost:8000"
Write-Host "Open your browser to: http://localhost:8000"
Write-Host ""
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
