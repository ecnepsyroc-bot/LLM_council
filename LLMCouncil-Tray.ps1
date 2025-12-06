# LLM Council - Windows System Tray Application
# Runs the backend and frontend as hidden processes with a system tray icon

param(
    [string]$ProjectRoot = $PSScriptRoot
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Configuration
$script:BackendUrl = "http://localhost:8001"
$script:FrontendUrl = "http://localhost:5173"
$script:BackendProcess = $null
$script:FrontendProcess = $null
$script:NpmProcess = $null

# Create the application context
$script:AppContext = New-Object System.Windows.Forms.ApplicationContext

# Create system tray icon
$script:TrayIcon = New-Object System.Windows.Forms.NotifyIcon
$script:TrayIcon.Text = "LLM Council"
$script:TrayIcon.Visible = $true

# Create icon from text (fallback if no .ico file exists)
function New-TextIcon {
    param([string]$Text = "LC", [string]$BgColor = "#6366f1")

    $bitmap = New-Object System.Drawing.Bitmap(32, 32)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

    # Background
    $bgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($BgColor))
    $graphics.FillEllipse($bgBrush, 0, 0, 31, 31)

    # Text
    $font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
    $textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $rect = New-Object System.Drawing.RectangleF(0, 0, 32, 32)
    $graphics.DrawString($Text, $font, $textBrush, $rect, $format)

    $graphics.Dispose()
    $handle = $bitmap.GetHicon()
    return [System.Drawing.Icon]::FromHandle($handle)
}

# Set the icon
$icoPath = Join-Path $ProjectRoot "council.ico"
if (Test-Path $icoPath) {
    $script:TrayIcon.Icon = New-Object System.Drawing.Icon($icoPath)
} else {
    $script:TrayIcon.Icon = New-TextIcon -Text "LC" -BgColor "#6366f1"
}

# Create context menu
$script:ContextMenu = New-Object System.Windows.Forms.ContextMenuStrip

# Menu: Open LLM Council
$menuOpen = New-Object System.Windows.Forms.ToolStripMenuItem
$menuOpen.Text = "🌐 Open LLM Council"
$menuOpen.Font = New-Object System.Drawing.Font($menuOpen.Font, [System.Drawing.FontStyle]::Bold)
$menuOpen.Add_Click({
    Start-Process $script:FrontendUrl
})
$script:ContextMenu.Items.Add($menuOpen) | Out-Null

# Separator
$script:ContextMenu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

# Menu: Status indicator
$script:MenuStatus = New-Object System.Windows.Forms.ToolStripMenuItem
$script:MenuStatus.Text = "⏳ Starting..."
$script:MenuStatus.Enabled = $false
$script:ContextMenu.Items.Add($script:MenuStatus) | Out-Null

# Menu: Restart Services
$menuRestart = New-Object System.Windows.Forms.ToolStripMenuItem
$menuRestart.Text = "🔄 Restart Services"
$menuRestart.Add_Click({
    $script:MenuStatus.Text = "🔄 Restarting..."
    Stop-Services
    Start-Sleep -Milliseconds 500
    Start-Services
})
$script:ContextMenu.Items.Add($menuRestart) | Out-Null

# Separator
$script:ContextMenu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

# Menu: Exit
$menuExit = New-Object System.Windows.Forms.ToolStripMenuItem
$menuExit.Text = "❌ Exit"
$menuExit.Add_Click({
    Stop-Services
    $script:TrayIcon.Visible = $false
    $script:TrayIcon.Dispose()
    [System.Windows.Forms.Application]::Exit()
})
$script:ContextMenu.Items.Add($menuExit) | Out-Null

$script:TrayIcon.ContextMenuStrip = $script:ContextMenu

# Double-click to open
$script:TrayIcon.Add_DoubleClick({
    Start-Process $script:FrontendUrl
})

function Start-Services {
    # Start backend (Python directly - uv may not be in PATH for hidden processes)
    $backendStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $backendStartInfo.FileName = "cmd.exe"
    $backendStartInfo.Arguments = "/c python -m backend.main"
    $backendStartInfo.WorkingDirectory = $ProjectRoot
    $backendStartInfo.UseShellExecute = $false
    $backendStartInfo.CreateNoWindow = $true
    $backendStartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

    try {
        $script:BackendProcess = [System.Diagnostics.Process]::Start($backendStartInfo)
    } catch {
        # Fallback to python directly
        $backendStartInfo.Arguments = "/c python -m backend.main"
        $script:BackendProcess = [System.Diagnostics.Process]::Start($backendStartInfo)
    }

    Start-Sleep -Seconds 2

    # Start frontend (npm via cmd.exe to resolve PATH)
    $frontendStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $frontendStartInfo.FileName = "cmd.exe"
    $frontendStartInfo.Arguments = "/c npm run dev"
    $frontendStartInfo.WorkingDirectory = Join-Path $ProjectRoot "frontend"
    $frontendStartInfo.UseShellExecute = $false
    $frontendStartInfo.CreateNoWindow = $true
    $frontendStartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

    $script:FrontendProcess = [System.Diagnostics.Process]::Start($frontendStartInfo)

    Start-Sleep -Seconds 3

    # Update status
    $script:MenuStatus.Text = "✅ Running"
    $script:TrayIcon.Text = "LLM Council - Running"

    # Show notification
    $script:TrayIcon.BalloonTipTitle = "LLM Council"
    $script:TrayIcon.BalloonTipText = "Services are running! Double-click to open."
    $script:TrayIcon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
    $script:TrayIcon.ShowBalloonTip(3000)
}

function Stop-Services {
    $script:MenuStatus.Text = "⏳ Stopping..."

    # Kill backend process tree
    if ($script:BackendProcess -and !$script:BackendProcess.HasExited) {
        try {
            # Kill the process tree (including child processes)
            $processId = $script:BackendProcess.Id
            Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $processId } | ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
            $script:BackendProcess.Kill()
        } catch {}
    }

    # Kill frontend process tree
    if ($script:FrontendProcess -and !$script:FrontendProcess.HasExited) {
        try {
            $processId = $script:FrontendProcess.Id
            Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $processId } | ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
            $script:FrontendProcess.Kill()
        } catch {}
    }

    # Also kill any lingering node/python processes on our ports
    Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }

    $script:MenuStatus.Text = "⏹ Stopped"
}

# Start services on launch
Start-Services

# Run the application
[System.Windows.Forms.Application]::Run($script:AppContext)
