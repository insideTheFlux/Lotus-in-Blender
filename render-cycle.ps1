<#
.SYNOPSIS
  Renders the lotus at a range of openness values and joins the frames into a looping MP4 (up, then back down).

.EXAMPLE
  .\render-cycle.ps1 -Blender 'C:\Program Files\Blender Foundation\Blender 5.3\blender.exe' -Out lotus.mp4
  .\render-cycle.ps1 -Blender $blender -Out lotus.mp4 -Step 0.01 -Samples 32 -Scale 1 -Fps 24
#>
param(
    [Parameter(Mandatory)][string]$Blender,
    [Parameter(Mandatory)][string]$Out,
    [double]$Step = 0.025,
    [int]$Samples = 16,
    [double]$Scale = 0.5,
    [int]$Fps = 24,
    [ValidateSet("cpu", "gpu")][string]$Device = "cpu"
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$frames = Join-Path ([System.IO.Path]::GetTempPath()) ('lotus-frames-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $frames | Out-Null
$count = [int][math]::Round(1.0 / $Step)
for ($i = 0; $i -le $count; $i++) {
    $open = [math]::Min(1.0, $i * $Step)
    $png = Join-Path $frames ('frame_{0:000}.png' -f $i)
    & $Blender --background --python (Join-Path $here 'lotus.py') -- $png $open $Samples $Scale $Device | Out-Null
    if (-not (Test-Path $png)) { throw "Frame $i was not rendered." }
}
& $Blender --background --python (Join-Path $here 'frames-to-mp4.py') -- $frames $Out $Fps | Out-Null
if (-not (Test-Path $Out)) { throw 'The video was not written.' }
Remove-Item -Recurse -Force $frames
"wrote $Out"
