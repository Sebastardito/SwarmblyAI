# Swarmbly AI — installer for Windows (PowerShell).
#   .\install.ps1              asks: quick or custom install
#   .\install.ps1 --quick      everything recommended, no questions
#   .\install.ps1 --custom     step by step
#   .\install.ps1 --doctor | --uninstall | --help
# Finds Python 3.10+ (offers to install it with winget) and runs installer\install.py.
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$es = (Get-Culture).TwoLetterISOLanguageName -eq "es"

function Find-Python {
    $candidates = @()
    if ($env:PYTHON) { $candidates += ,@($env:PYTHON) }
    $candidates += ,@("py", "-3.13"); $candidates += ,@("py", "-3.12"); $candidates += ,@("py", "-3.11")
    $candidates += ,@("py", "-3.10"); $candidates += ,@("python"); $candidates += ,@("python3")
    foreach ($c in $candidates) {
        $exe = $c[0]; $rest = @($c | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            & $exe @rest -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return ,$c }
        } catch { }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    if ($es) { Write-Host "Swarmbly AI necesita Python 3.10 o superior y no se encontró." }
    else { Write-Host "Swarmbly AI needs Python 3.10 or newer, and none was found." }
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $q = if ($es) { "¿Instalar Python 3.12 con winget ahora? [S/n]" } else { "Install Python 3.12 with winget now? [Y/n]" }
        $a = Read-Host $q
        if ($a -eq "" -or $a -match "^[sSyY]") {
            winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
            $py = Find-Python
        }
    }
    if (-not $py) {
        Write-Host "  https://www.python.org/downloads/windows/"
        exit 1
    }
}
$exe = $py[0]; $rest = @($py | Select-Object -Skip 1)
& $exe @rest "installer\install.py" @args
exit $LASTEXITCODE
