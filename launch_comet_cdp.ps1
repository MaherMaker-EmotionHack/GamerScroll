# Launch Comet with the Chrome DevTools Protocol remote-debugging port enabled.
# This is required for GamerScroll to send scroll commands to the browser.

$cometExe = "C:\Users\MaherMaker\AppData\Local\Perplexity\Comet\Application\comet.exe"
$profile = "Default"
$port = 9222

# Close any existing Comet windows first so the flag is picked up.
Stop-Process -Name "comet" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Start-Process -FilePath $cometExe -ArgumentList "--profile-directory=`"$profile`"","--remote-debugging-port=$port"
Write-Host "Comet launched with remote debugging on port $port." -ForegroundColor Green
