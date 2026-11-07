# UTF-8-safe launcher for lecture.py (Windows PowerShell 5.1 / pwsh)
$ErrorActionPreference = "Stop"
$SkillDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $SkillDir ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "venv not found. Run: powershell -ExecutionPolicy Bypass -File `"$SkillDir\scripts\setup.ps1`"" -ForegroundColor Red
    exit 2
}

$env:PYTHONIOENCODING = "utf-8"
try { chcp 65001 | Out-Null } catch {}
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}

& $Python (Join-Path $SkillDir "scripts\lecture.py") @args
exit $LASTEXITCODE
