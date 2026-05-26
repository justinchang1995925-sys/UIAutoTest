param(
    [string]$ServerUrl = "http://127.0.0.1:4723",
    [switch]$NoRecreateSession,
    [switch]$OpenInspector
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..\..")).Path
$repairPy = Join-Path $scriptDir "repair_appium_session.py"

$argsList = @($repairPy, "--server-url", $ServerUrl, "--project-root", $projectRoot)
if ($NoRecreateSession) {
    $argsList += "--no-recreate-session"
}
if ($OpenInspector) {
    $argsList += "--open-inspector"
}

python @argsList
