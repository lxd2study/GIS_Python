param(
    [Parameter(Mandatory = $true)]
    [string]$SlidesDir,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [Parameter(Mandatory = $false)]
    [string]$AlsoCopyTo
)

$ErrorActionPreference = "Stop"

$resolvedSlidesDir = (Resolve-Path -LiteralPath $SlidesDir).Path
$slideFiles = Get-ChildItem -LiteralPath $resolvedSlidesDir -Filter "slide-*.png" | Sort-Object Name
if ($slideFiles.Count -eq 0) {
    throw "No slide PNG files found in $resolvedSlidesDir"
}

$outputParent = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputParent)) {
    New-Item -ItemType Directory -Path $outputParent | Out-Null
}

$powerPoint = $null
$presentation = $null
$checkPresentation = $null

try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $powerPoint.Visible = -1

    $presentation = $powerPoint.Presentations.Add(-1)
    $presentation.PageSetup.SlideWidth = 960
    $presentation.PageSetup.SlideHeight = 540

    while ($presentation.Slides.Count -gt 0) {
        $presentation.Slides.Item(1).Delete()
    }

    $index = 1
    foreach ($file in $slideFiles) {
        $slide = $presentation.Slides.Add($index, 12)
        $null = $slide.Shapes.AddPicture($file.FullName, 0, -1, 0, 0, 960, 540)
        $index += 1
    }

    if (Test-Path -LiteralPath $OutputPath) {
        Remove-Item -LiteralPath $OutputPath -Force
    }

    $presentation.SaveAs($OutputPath, 24)
    $presentation.Close()
    $presentation = $null

    $checkPresentation = $powerPoint.Presentations.Open($OutputPath, 0, 0, 0)
    $slideCount = $checkPresentation.Slides.Count
    $checkPresentation.Close()
    $checkPresentation = $null

    if ($slideCount -ne $slideFiles.Count) {
        throw "Saved PPTX has $slideCount slides, expected $($slideFiles.Count)"
    }

    if ($AlsoCopyTo) {
        Copy-Item -LiteralPath $OutputPath -Destination $AlsoCopyTo -Force
    }

    Write-Output "Saved: $OutputPath"
    Write-Output "Slides: $slideCount"
    if ($AlsoCopyTo) {
        Write-Output "Copied: $AlsoCopyTo"
    }
}
finally {
    if ($checkPresentation -ne $null) {
        try { $checkPresentation.Close() } catch {}
    }
    if ($presentation -ne $null) {
        try { $presentation.Close() } catch {}
    }
    if ($powerPoint -ne $null) {
        try { $powerPoint.Quit() } catch {}
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
