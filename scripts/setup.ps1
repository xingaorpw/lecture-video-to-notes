# lecture-video-to-notes: one-time setup (no admin required)
#
# Default installs only Python dependencies. ffmpeg/Pandoc are optional:
#   - audio decoding works through PyAV (installed with faster-whisper)
#   - DOCX works through python-docx fallback
# For best DOCX formula fidelity, add -WithPandoc.
# For frame extraction/other ffmpeg workflows, add -WithFfmpeg.
param(
    [switch]$WithFfmpeg,
    [switch]$WithPandoc,
    [string]$IndexUrl = "https://pypi.tuna.tsinghua.edu.cn/simple"
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}

$SkillDir = Split-Path -Parent $PSScriptRoot
$ToolsDir = Join-Path $env:LOCALAPPDATA "lecture-video-to-notes"
$Downloads = Join-Path $ToolsDir "downloads"
$Venv = Join-Path $SkillDir ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"

Write-Host "== lecture-video-to-notes setup ==" -ForegroundColor Cyan
Write-Host "skill: $SkillDir"
Write-Host "tools: $ToolsDir"
New-Item -ItemType Directory -Force -Path $Downloads | Out-Null

# 1) Python venv + dependencies
if (-not (Test-Path $Python)) {
    Write-Host "[1/3] creating venv..." -ForegroundColor Yellow
    python -m venv $Venv
}
Write-Host "[1/3] installing Python dependencies (index: $IndexUrl)..." -ForegroundColor Yellow
& $Python -m pip install -U pip wheel
& $Python -m pip install -r (Join-Path $SkillDir "requirements.txt") -i $IndexUrl --trusted-host pypi.tuna.tsinghua.edu.cn
if ($LASTEXITCODE -ne 0) {
    Write-Host "Mirror failed, retrying official PyPI..." -ForegroundColor Yellow
    & $Python -m pip install -r (Join-Path $SkillDir "requirements.txt")
}
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

function Download-File {
    param([string]$Url, [string]$OutFile)
    if ((Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 1MB)) {
        Write-Host "  already exists: $OutFile"
        return
    }
    if (Test-Path $OutFile) { Remove-Item $OutFile -Force }
    Write-Host "  downloading $Url"
    $ok = $false
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -L --retry 3 --retry-delay 2 -o $OutFile $Url
        $ok = ($LASTEXITCODE -eq 0) -and (Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 1MB)
    }
    if (-not $ok) {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
    }
    if (-not (Test-Path $OutFile)) { throw "download failed: $Url" }
}

function Expand-Tool {
    param([string]$Zip, [string]$Dest)
    if (Test-Path $Dest) {
        $existing = Get-ChildItem $Dest -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($existing) { return }
    }
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    try {
        Expand-Archive -Path $Zip -DestinationPath $Dest -Force
    } catch {
        Remove-Item $Dest -Recurse -Force -ErrorAction SilentlyContinue
        throw "extract failed: $Zip -> $Dest ($($_.Exception.Message))"
    }
}

# 2) ffmpeg (optional; PyAV is the default fallback)
Write-Host "[2/3] ffmpeg..." -ForegroundColor Yellow
$ffmpegDir = Join-Path $ToolsDir "ffmpeg"
$ffmpegExe = Get-ChildItem $ffmpegDir -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $ffmpegExe -and $WithFfmpeg) {
    $ffmpegZip = Join-Path $Downloads "ffmpeg.zip"
    Download-File "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $ffmpegZip
    Expand-Tool $ffmpegZip $ffmpegDir
    $ffmpegExe = Get-ChildItem $ffmpegDir -Recurse -Filter ffmpeg.exe | Select-Object -First 1
}
if ($ffmpegExe) { Write-Host "  ffmpeg: $($ffmpegExe.FullName)" }
else { Write-Host "  skipped (optional; PyAV handles audio decode). Use -WithFfmpeg to install." -ForegroundColor DarkGray }

# 3) Pandoc (optional; improves DOCX math)
Write-Host "[3/3] pandoc..." -ForegroundColor Yellow
$pandocDir = Join-Path $ToolsDir "pandoc"
$pandocExe = Get-ChildItem $pandocDir -Recurse -Filter pandoc.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $pandocExe -and $WithPandoc) {
    $pandocZip = Join-Path $Downloads "pandoc.zip"
    Download-File "https://github.com/jgm/pandoc/releases/download/3.13/pandoc-3.13-windows-x86_64.zip" $pandocZip
    Expand-Tool $pandocZip $pandocDir
    $pandocExe = Get-ChildItem $pandocDir -Recurse -Filter pandoc.exe | Select-Object -First 1
}
if ($pandocExe) { Write-Host "  pandoc: $($pandocExe.FullName)" }
else { Write-Host "  skipped (optional; python-docx fallback). Use -WithPandoc for better math." -ForegroundColor DarkGray }

Write-Host ""
Write-Host "== doctor ==" -ForegroundColor Cyan
& $Python (Join-Path $PSScriptRoot "doctor.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Environment is not fully ready. Fix the MISS items above, then rerun doctor." -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "Setup complete. Example:" -ForegroundColor Green
Write-Host "  & `"$Python`" `"$PSScriptRoot\lecture.py`" init --video `"D:\录播\lecture.mp4`" --workdir `"D:\学习\lecture`" --course `"线性代数`" --lecture `"第03讲`""
Write-Host "  (recommended) & `"$PSScriptRoot\run.cmd`" init --video ... --workdir ..."
