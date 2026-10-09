param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$Output = ".\dist",
    [switch]$SkipTests
)
$ErrorActionPreference = "Stop"
$a4OriginalPath = $env:PATH
Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force -Path build | Out-Null
    if (-not (Test-Path -LiteralPath $Python)) {
        throw "Python não encontrado. Crie a .venv e instale requirements-dev.txt conforme o README."
    }
    $Python = (Resolve-Path -LiteralPath $Python).Path
    if (-not $SkipTests) {
        & $Python -m pytest -q --basetemp=build/pytest-temp
        if ($LASTEXITCODE -ne 0) { throw "Testes falharam; build cancelado." }
    }
    # Evitar que DLLs de outras ferramentas no PATH (por exemplo, ICU do Poppler)
    # sejam empacotadas no lugar das bibliotecas nativas compatíveis do Windows.
    $env:PATH = "$(Split-Path -Parent $Python);$env:SystemRoot\System32;$env:SystemRoot"
    & $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name EditorA4Livre `
        --distpath $Output --workpath build/pyinstaller --specpath build `
        --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets `
        --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick `
        --exclude-module PySide6.QtPdf --exclude-module PySide6.QtPdfWidgets main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }
    $bundle = Join-Path $Output "EditorA4Livre"
    Copy-Item -LiteralPath README.md -Destination $bundle
    if (Test-Path -LiteralPath RELATORIO.md) { Copy-Item -LiteralPath RELATORIO.md -Destination $bundle }
    & $Python scripts/copy_licenses.py $bundle
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível copiar os avisos das dependências." }
    if (Test-Path -LiteralPath examples) { Copy-Item -LiteralPath examples -Destination $bundle -Recurse -Force }
    if (Test-Path -LiteralPath docs) { Copy-Item -LiteralPath docs -Destination $bundle -Recurse -Force }
    $smokeDir = Join-Path $PSScriptRoot ("build\smoke-" + [guid]::NewGuid().ToString('N'))
    $exe = (Resolve-Path -LiteralPath (Join-Path $bundle "EditorA4Livre.exe")).Path
    $smokeProcess = Start-Process -FilePath $exe -ArgumentList '--smoke-test', ('"{0}"' -f $smokeDir) `
        -WindowStyle Hidden -PassThru
    if (-not $smokeProcess.WaitForExit(30000)) {
        Stop-Process -Id $smokeProcess.Id -ErrorAction SilentlyContinue
        throw "O executável não concluiu o autoteste em 30 segundos."
    }
    $reportFile = Join-Path $smokeDir "smoke-report.json"
    if ($smokeProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $reportFile)) {
        throw "O executável falhou no autoteste. Verifique $smokeDir."
    }
    $report = Get-Content -LiteralPath $reportFile -Raw | ConvertFrom-Json
    if (-not $report.ok) { throw "Autoteste falhou: $($report.error)" }
    Copy-Item -LiteralPath $reportFile -Destination build/smoke-report.json -Force
    Write-Host "Pacote gerado e autoteste aprovado em $bundle. Distribua a pasta inteira, incluindo _internal."
}
finally {
    $env:PATH = $a4OriginalPath
    Pop-Location
}
