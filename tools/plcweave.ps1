# Repository-local entry; does not require a global install or alter caller state.
$ErrorActionPreference = 'Stop'
$taskRepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskPython = Join-Path $taskRepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = (Get-Command python -ErrorAction Stop).Source }
$taskOldPythonPath = $env:PYTHONPATH
$taskOldUtf8 = $env:PYTHONUTF8
$taskExitCode = 1
Push-Location -LiteralPath $taskRepoRoot
try {
    $env:PYTHONPATH = Join-Path $taskRepoRoot 'src'
    if ($taskOldPythonPath) { $env:PYTHONPATH += [IO.Path]::PathSeparator + $taskOldPythonPath }
    $env:PYTHONUTF8 = '1'
    & $taskPython -X utf8 -m plcweave @args
    $taskExitCode = $LASTEXITCODE
}
finally {
    $env:PYTHONPATH = $taskOldPythonPath
    $env:PYTHONUTF8 = $taskOldUtf8
    Pop-Location
}
exit $taskExitCode
