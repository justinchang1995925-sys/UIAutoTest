param(
    [string]$ServerUrl = "http://127.0.0.1:4723",
    [switch]$NoInstall,
    [switch]$NoAutoSession,
    [switch]$NoOpenInspector
)

$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Add-NpmGlobalPath {
    if (-not (Test-CommandExists "npm")) {
        return
    }

    try {
        $npmPrefix = (& npm config get prefix) | Select-Object -First 1
        if ($npmPrefix -and (Test-Path $npmPrefix) -and ($env:Path -notlike "*$npmPrefix*")) {
            $env:Path = "$npmPrefix;$env:Path"
        }
    } catch {
        Write-Host "Could not resolve npm global prefix: $($_.Exception.Message)"
    }
}

function Test-TcpPort {
    param([string]$HostName, [int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $asyncResult = $client.BeginConnect($HostName, $Port, $null, $null)
        $connected = $asyncResult.AsyncWaitHandle.WaitOne(1000, $false)
        if ($connected) {
            $client.EndConnect($asyncResult)
        }
        $client.Close()
        return $connected
    } catch {
        return $false
    }
}

function Test-AdbDeviceReady {
    param([string]$AdbPath)

    try {
        $output = & $AdbPath devices 2>&1 | Out-String
        return $output -match "\sdevice\s*(\r?\n|$)"
    } catch {
        return $false
    }
}

function Ensure-PlatformToolsLayout {
    param([string]$SdkRoot)

    $platformToolsDir = Join-Path $SdkRoot "platform-tools"
    $adbInRoot = Join-Path $SdkRoot "adb.exe"
    if (-not (Test-Path $adbInRoot)) {
        return $platformToolsDir
    }

    $adbInPlatformTools = Join-Path $platformToolsDir "adb.exe"
    if (Test-Path $adbInPlatformTools) {
        return $platformToolsDir
    }

    New-Item -ItemType Directory -Force -Path $platformToolsDir | Out-Null
    foreach ($fileName in @("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll")) {
        $source = Join-Path $SdkRoot $fileName
        $dest = Join-Path $platformToolsDir $fileName
        if (-not (Test-Path $source)) {
            continue
        }
        if (Test-Path $dest) {
            continue
        }
        try {
            Copy-Item -Force $source $dest -ErrorAction Stop
        } catch {
            Write-Host (
                "Could not copy $fileName to platform-tools (file may be in use by adb). " +
                "Using adb from SDK root: $adbInRoot"
            )
            return $SdkRoot
        }
    }

    if (Test-Path $adbInPlatformTools) {
        return $platformToolsDir
    }
    return $SdkRoot
}

function Resolve-AuthorizedAdbPath {
    $candidates = @()
    if (Test-CommandExists "adb") {
        $candidates += (Get-Command "adb" -ErrorAction SilentlyContinue).Source
    }
    foreach ($root in @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, "D:\adb_new_for_android12", "D:\platform-tools", "D:\")) {
        if (-not $root) { continue }
        $candidates += (Join-Path $root "platform-tools\adb.exe")
        $candidates += (Join-Path $root "adb.exe")
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not $candidate -or -not (Test-Path $candidate)) {
            continue
        }
        if (Test-AdbDeviceReady -AdbPath $candidate) {
            return $candidate
        }
    }
    return $null
}

function Set-AndroidSdkEnvironment {
    $adbPath = Resolve-AuthorizedAdbPath
    if (-not $adbPath) {
        if (Test-CommandExists "adb") {
            $adbPath = (Get-Command "adb" -ErrorAction SilentlyContinue).Source
        } else {
            return
        }
    }

    $platformToolsDir = Split-Path -Parent $adbPath
    if ((Split-Path -Leaf $platformToolsDir) -eq "platform-tools") {
        $sdkRoot = Split-Path -Parent $platformToolsDir
    } else {
        # adb.exe under SDK root (non-standard layout). Use resolved path as-is when adb is
        # already running — copying into platform-tools fails while adb.exe is locked.
        $sdkRoot = $platformToolsDir
        if (Test-AdbDeviceReady -AdbPath $adbPath) {
            Write-Host "Using adb from non-standard SDK layout (skip platform-tools copy)."
        } else {
            $layoutDir = Ensure-PlatformToolsLayout -SdkRoot $sdkRoot
            if ((Split-Path -Leaf $layoutDir) -eq "platform-tools") {
                $adbPath = Join-Path $layoutDir "adb.exe"
            } else {
                $adbPath = Join-Path $sdkRoot "adb.exe"
            }
        }
    }

    $env:ANDROID_HOME = $sdkRoot
    $env:ANDROID_SDK_ROOT = $sdkRoot
    [Environment]::SetEnvironmentVariable("ANDROID_HOME", $sdkRoot, "User")
    [Environment]::SetEnvironmentVariable("ANDROID_SDK_ROOT", $sdkRoot, "User")
    Write-Host "Using authorized Android SDK root: $sdkRoot"
    Write-Host "Using adb: $adbPath"
}

function Stop-AppiumServerOnPort {
    param([int]$Port)

    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($connection in $connections) {
            Write-Host "Stopping existing Appium server process on port $Port ..."
            Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 2
    } catch {
        Write-Host "Could not stop existing server on port ${Port}: $($_.Exception.Message)"
    }
}

function Install-AppiumIfMissing {
    if (Test-CommandExists "appium") {
        return
    }

    if (-not (Test-CommandExists "npm")) {
        Write-Host "npm is not installed or not in PATH."
        Write-Host "Install Node.js LTS first, then run this script again."
        Start-Process "https://nodejs.org/"
        exit 1
    }

    Write-Host "Appium is not installed. Installing Appium globally with npm..."
    npm install -g appium
    Add-NpmGlobalPath

    if (-not (Test-CommandExists "appium")) {
        Write-Host "Appium installation finished, but appium is still not available in this PowerShell PATH."
        Write-Host "Close and reopen the terminal, then run this script again."
        exit 1
    }
}

function Get-AppiumMajorVersion {
    $appiumVersionText = (& appium --version) | Select-Object -First 1
    if ($appiumVersionText -match "^(\d+)") {
        return [int]$Matches[1]
    }
    return 0
}

function Test-InspectorPluginInstalled {
    try {
        $pluginJson = (& appium plugin list --installed --json 2>$null) -join "`n"
        $plugins = $pluginJson | ConvertFrom-Json
        return ($null -ne $plugins.inspector) -or ($pluginJson -match "appium-inspector-plugin")
    } catch {
        return $false
    }
}

function Install-InspectorPluginIfMissing {
    if (Test-InspectorPluginInstalled) {
        Write-Host "Appium Inspector plugin is already installed."
        return
    }

    $majorVersion = Get-AppiumMajorVersion
    if ($majorVersion -ge 3) {
        Write-Host "Installing Appium Inspector plugin for Appium 3..."
        appium plugin install inspector
    } else {
        Write-Host "Installing Appium Inspector plugin for Appium 2..."
        appium plugin install --source=npm appium-inspector-plugin@2025.7.3
    }
}

function Test-AndroidDriverInstalled {
    try {
        $driverJson = (& appium driver list --installed --json 2>$null) -join "`n"
        $drivers = $driverJson | ConvertFrom-Json
        return ($null -ne $drivers.uiautomator2) -or ($driverJson -match "appium-uiautomator2-driver")
    } catch {
        return $false
    }
}

function Install-AndroidDriverIfMissing {
    if (Test-AndroidDriverInstalled) {
        Write-Host "Appium Android driver uiautomator2 is already installed."
        return
    }

    Write-Host "Installing Appium Android driver uiautomator2..."
    appium driver install uiautomator2
}

function Get-AndroidDeviceId {
    if (-not (Test-CommandExists "adb")) {
        return $null
    }

    $devices = adb devices | Select-Object -Skip 1
    foreach ($line in $devices) {
        if ($line -match "^(\S+)\s+device$") {
            return $Matches[1]
        }
    }
    return $null
}

function Get-ForegroundAndroidApp {
    if (-not (Test-CommandExists "adb")) {
        return $null
    }

    $windowLines = adb shell dumpsys window
    $focusLine = $windowLines |
        Where-Object { $_ -match "mCurrentFocus=.*[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+/[A-Za-z0-9_.$]+" } |
        Select-Object -Last 1

    if (-not $focusLine) {
        $focusLine = $windowLines |
            Where-Object { $_ -match "mFocusedApp=.*[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+/[A-Za-z0-9_.$]+" } |
            Select-Object -Last 1
    }

    if (-not $focusLine) {
        return $null
    }

    $match = [regex]::Match(
        $focusLine,
        "([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)/([A-Za-z0-9_.$]+)"
    )
    if (-not $match.Success) {
        return $null
    }

    $packageName = $match.Groups[1].Value
    $activityName = $match.Groups[2].Value
    if ($activityName.StartsWith(".")) {
        $activityName = "$packageName$activityName"
    }

    return [ordered]@{
        PackageName = $packageName
        ActivityName = $activityName
    }
}

function New-AndroidCapabilities {
    $deviceId = Get-AndroidDeviceId
    if (-not $deviceId) {
        Write-Host "No Android device is connected. Connect a device and enable USB debugging."
        return $null
    }

    $foregroundApp = Get-ForegroundAndroidApp
    $caps = [ordered]@{
        platformName = "Android"
        "appium:automationName" = "UiAutomator2"
        "appium:deviceName" = $deviceId
        "appium:udid" = $deviceId
        "appium:noReset" = $true
        "appium:newCommandTimeout" = 300
        "appium:disableWindowAnimation" = $true
        "appium:ignoreHiddenApiPolicyError" = $true
        "appium:uiautomator2ServerLaunchTimeout" = 120000
        "appium:uiautomator2ServerInstallTimeout" = 120000
        "appium:adbExecTimeout" = 120000
    }

    if ($foregroundApp) {
        $caps["appium:appPackage"] = $foregroundApp.PackageName
        $caps["appium:appActivity"] = $foregroundApp.ActivityName
    } else {
        Write-Host "Could not detect foreground app. Generated device-only capabilities."
    }

    return $caps
}

function Save-Capabilities {
    param([object]$Capabilities)

    $capabilitiesPath = Join-Path (Get-Location) "capabilities.json"
    $json = $Capabilities | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($capabilitiesPath, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Generated capabilities: $capabilitiesPath"
}

function Repair-UiAutomator2OnDevice {
    if (-not (Test-CommandExists "adb")) {
        return
    }

    Write-Host "Resetting UiAutomator2 instrumentation on device..."
    adb shell am force-stop io.appium.uiautomator2.server | Out-Null
    adb shell am force-stop io.appium.uiautomator2.server.test | Out-Null
    Start-Sleep -Seconds 2
}

function Remove-AppiumSessions {
    param([string]$Url)

    foreach ($session in (Get-AppiumSessions -Url $Url)) {
        $sessionId = $session.id
        if (-not $sessionId) {
            continue
        }
        try {
            Write-Host "Deleting stale Appium session: $sessionId"
            Invoke-RestMethod -Method Delete -Uri "$Url/session/$sessionId" -TimeoutSec 15 | Out-Null
        } catch {
            Write-Host "Could not delete session ${sessionId}: $($_.Exception.Message)"
        }
    }
}

function Test-AppiumServerReady {
    param([string]$Url)

    try {
        $status = Invoke-RestMethod -Uri "$Url/status" -TimeoutSec 5
        return [bool]$status.value.ready
    } catch {
        return $false
    }
}


function Wait-AppiumServerReady {
    param(
        [string]$Url,
        [int]$TimeoutSec = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-AppiumServerReady -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Get-AppiumSessions {
    param([string]$Url)

    try {
        $response = Invoke-RestMethod -Uri "$Url/appium/sessions" -TimeoutSec 5
        return $response.value
    } catch {
        return @()
    }
}

function New-AppiumSession {
    param(
        [string]$Url,
        [object]$Capabilities
    )

    $payload = @{
        capabilities = @{
            alwaysMatch = $Capabilities
            firstMatch = @(@{})
        }
    } | ConvertTo-Json -Depth 10

    try {
        $response = Invoke-RestMethod `
            -Method Post `
            -Uri "$Url/session" `
            -ContentType "application/json" `
            -Body $payload `
            -TimeoutSec 60

        $sessionId = $response.value.sessionId
        Write-Host "Created Appium session: $sessionId"
        $sessionInfo = @{
            server_url = $Url
            session_id = $sessionId
            inspector_url = "$Url/inspector"
        } | ConvertTo-Json -Depth 3
        [System.IO.File]::WriteAllText(
            (Join-Path (Get-Location) ".appium-inspector-session.json"),
            $sessionInfo,
            [System.Text.UTF8Encoding]::new($false)
        )
        Write-Host "In Inspector use Attach to Session with id: $sessionId"
        return $sessionId
    } catch {
        $errorDetails = $_.ErrorDetails.Message
        if ($errorDetails) {
            Write-Host "Could not auto-create Appium session: $errorDetails"
        } else {
            Write-Host "Could not auto-create Appium session: $($_.Exception.Message)"
        }
        Write-Host "The generated capabilities.json can still be used by Inspector."
        return $null
    }
}

if (-not $NoInstall) {
    Add-NpmGlobalPath
    Install-AppiumIfMissing
    Install-InspectorPluginIfMissing
    Install-AndroidDriverIfMissing
}

if (-not (Test-CommandExists "appium")) {
    Write-Host "Appium is not installed or not in PATH."
    Write-Host "Install Node.js, then run: npm install -g appium"
    Start-Process "https://appium.io/docs/en/latest/quickstart/"
    exit 1
}

Set-AndroidSdkEnvironment

if (Test-CommandExists "adb") {
    Write-Host "Connected Android devices:"
    adb devices
} else {
    Write-Host "adb was not found in PATH. Install Android Platform Tools if device detection is needed."
}

$uri = [System.Uri]$ServerUrl
$hostName = $uri.Host
$port = $uri.Port
if ($port -lt 0) {
    $port = 4723
}

if ((Test-TcpPort -HostName $hostName -Port $port) -and (-not $NoAutoSession)) {
    $existingSessions = Get-AppiumSessions -Url $ServerUrl
    if (-not $existingSessions -or $existingSessions.Count -eq 0) {
        Stop-AppiumServerOnPort -Port $port
    }
}

if (-not (Test-TcpPort -HostName $hostName -Port $port)) {
    Write-Host "Starting Appium with Inspector plugin at $ServerUrl ..."
    $appiumCommand = "appium --use-plugins=inspector --allow-insecure=*:session_discovery --address $hostName --port $port"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $appiumCommand
} else {
    Write-Host "Appium server appears to be running at $ServerUrl."
}

if (-not (Wait-AppiumServerReady -Url $ServerUrl -TimeoutSec 90)) {
    Write-Host "Appium did not become ready within 90s at $ServerUrl."
    exit 1
}

$sessionId = $null
if (-not $NoAutoSession) {
    $capabilities = New-AndroidCapabilities
    if ($capabilities) {
        Save-Capabilities -Capabilities $capabilities
        Remove-AppiumSessions -Url $ServerUrl
        Repair-UiAutomator2OnDevice
        $sessionId = New-AppiumSession -Url $ServerUrl -Capabilities $capabilities
    }
}

if (-not $NoOpenInspector) {
    if ($sessionId) {
        $inspectorUrl = "$ServerUrl/inspector"
        Write-Host "Opening Appium Inspector: $inspectorUrl"
        Start-Process $inspectorUrl
    } else {
        Write-Host "Skip opening Inspector because no healthy Appium session was created."
        Write-Host "Run: python uiatest.py repair --open-inspector"
    }
}
