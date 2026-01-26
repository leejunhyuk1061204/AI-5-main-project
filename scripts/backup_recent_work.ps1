$sourceDir = "C:\Users\admin\Desktop\AI-5-main-project"
$destBase = "C:\Users\admin\Desktop\transfer_temp"
$zipPath = "C:\Users\admin\Desktop\AI-5-project-changes-240124-25.zip"

# Remove existing temp dir and zip if they exist
if (Test-Path $destBase) { Remove-Item -Recurse -Force $destBase }
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

# Create dest base
New-Item -ItemType Directory -Path $destBase | Out-Null

Write-Host "Scanning for files modified since 2026-01-24..."

$files = Get-ChildItem -Path $sourceDir -Recurse -File | Where-Object {
    $_.LastWriteTime -ge '2026-01-24' -and
    $_.FullName -notmatch '\\node_modules\\' -and
    $_.FullName -notmatch '\\build\\' -and
    $_.FullName -notmatch '\\.gradle\\' -and
    $_.FullName -notmatch '\\.git\\' -and
    $_.FullName -notmatch '\\dist\\' -and
    $_.FullName -notmatch '\\frontend\\\.expo\\web\\cache\\'
}

foreach ($file in $files) {
    # Calculate relative path
    $relativePath = $file.FullName.Substring($sourceDir.Length + 1)
    $destPath = Join-Path $destBase $relativePath
    $parentDir = Split-Path $destPath -Parent
    
    if (-not (Test-Path $parentDir)) {
        New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
    }
    
    Copy-Item $file.FullName -Destination $destPath
    Write-Host "Copied: $relativePath"
}

Write-Host "Compressing files..."
Compress-Archive -Path "$destBase\*" -DestinationPath $zipPath

# Cleanup
Remove-Item -Recurse -Force $destBase

Write-Host "Done. Zip created at: $zipPath"
