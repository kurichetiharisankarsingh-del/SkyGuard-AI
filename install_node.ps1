$zipUrl = 'https://nodejs.org/dist/v24.19.0/node-v24.19.0-win-x64.zip'
$zipOut = Join-Path $env:TEMP 'node-v24.19.0-win-x64.zip'
$dest = 'C:\tools\node'
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Invoke-WebRequest -Uri $zipUrl -OutFile $zipOut
Expand-Archive -Path $zipOut -DestinationPath $dest -Force
$nodeDir = Join-Path $dest 'node-v24.19.0-win-x64'
& (Join-Path $nodeDir 'node.exe') --version
