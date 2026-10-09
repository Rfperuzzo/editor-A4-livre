param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$Output = ".\dist",
    [switch]$SkipTests
)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force -Path build | Out-Null
    if (-not (Test-Path -LiteralPath $Python)) {
        throw "Python não encontrado. Crie a .venv e instale requirements-dev.txt conforme o README."
    }
    if (-not $SkipTests) {
        & $Python -m pytest -q --basetemp=build/pytest-temp
        if ($LASTEXITCODE -ne 0) { throw "Testes falharam; build cancelado." }
    }
    & $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name EditorA4Livre `
        --distpath $Output --workpath build/pyinstaller --specpath build `
        --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets `
        --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick `
        --exclude-module PySide6.QtPdf --exclude-module PySide6.QtPdfWidgets main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }
    $bundle = Join-Path $Output "EditorA4Livre"
    Copy-Item -LiteralPath README.md -Destination $bundle
    & $Python scripts/copy_licenses.py $bundle
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível copiar os avisos das dependências." }
    if (Test-Path -LiteralPath examples) { Copy-Item -LiteralPath examples -Destination $bundle -Recurse -Force }
    Write-Host "Pacote gerado em $bundle. Distribua a pasta inteira, incluindo _internal."
}
finally { Pop-Location }
