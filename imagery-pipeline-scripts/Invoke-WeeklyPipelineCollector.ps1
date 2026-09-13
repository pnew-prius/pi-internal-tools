param(
    [int]    $LookbackDays  = 8,
    [string] $DataFile      = "$PSScriptRoot\pipeline_runs.json",
    [string] $CsvFile       = "$PSScriptRoot\pipeline_runs.csv",
    [int]    $PurgeRunId    = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$GDAL_PIPE_ID    = 12
$MOSAIC_PIPE_ID  = 5
$DEVOPS_GDAL     = "https://dev.azure.com/PriusIntelli/5942a494-b65d-4b83-8eb9-ebb6cce89e99"
$DEVOPS_MOSAIC   = "https://dev.azure.com/PriusIntelli/0709c1b8-2c78-4a24-81b4-af6ac1645690"
$COMPUTE_RATE    = 0.816
$STORAGE_RATE    = 0.018
$EARTH_RADIUS_MI = 3958.8

$store = @()
if (Test-Path $DataFile) {
    $store = Get-Content $DataFile -Raw | ConvertFrom-Json
    Write-Host "Loaded $($store.Count) existing records from store." -ForegroundColor Cyan
}

if ($PurgeRunId -ne 0) {
    $target = $store | Where-Object { $_.GdalBuildId -eq $PurgeRunId -or $_.MosaicBuildId -eq $PurgeRunId }
    if (-not $target) { Write-Warning "No record found with build ID $PurgeRunId"; exit 1 }
    foreach ($r in $target) { $r.Excluded = $true; $r.ExcludedNote = "Manually excluded via -PurgeRunId" }
    $store | ConvertTo-Json -Depth 5 | Set-Content $DataFile -Encoding UTF8
    Write-Host "Marked run(s) with build ID $PurgeRunId as Excluded." -ForegroundColor Yellow
    exit 0
}

Write-Host "Acquiring DevOps token..." -ForegroundColor Gray
$tokenResp = az account get-access-token --resource "499b84ac-1321-427f-aa17-267ca6975798" | ConvertFrom-Json
$headers   = @{ Authorization = "Bearer $($tokenResp.accessToken)"; "Content-Type" = "application/json" }

$since = (Get-Date).AddDays(-$LookbackDays).ToString("yyyy-MM-ddT00:00:00Z")
$top   = 200

Write-Host "Fetching GDAL builds since $since..." -ForegroundColor Gray
$gdalBuilds = (Invoke-RestMethod `
    -Uri "$DEVOPS_GDAL/_apis/build/builds?definitions=$GDAL_PIPE_ID&minTime=$since&`$top=$top&api-version=7.1" `
    -Headers $headers).value

Write-Host "Fetching Mosaic builds since $since..." -ForegroundColor Gray
$mosaicBuilds = (Invoke-RestMethod `
    -Uri "$DEVOPS_MOSAIC/_apis/build/builds?definitions=$MOSAIC_PIPE_ID&minTime=$since&`$top=$top&api-version=7.1" `
    -Headers $headers).value

Write-Host "  GDAL: $($gdalBuilds.Count)   Mosaic: $($mosaicBuilds.Count)" -ForegroundColor Gray

function Get-TileKey($buildNumber) { $buildNumber -replace '^[^-]+-','' }

function Get-DurHrs($build) {
    if ($build.finishTime -and $build.startTime) {
        [math]::Round(([datetime]$build.finishTime - [datetime]$build.startTime).TotalHours, 4)
    } else { $null }
}

function Get-CompanyProject($buildNumber) {
    if ($buildNumber -match '^([^-]+)-([a-z]{3}\d+)-') {
        return @{ Company = $Matches[1]; Project = $Matches[2].ToUpper() }
    }
    return @{ Company = "Unknown"; Project = "Unknown" }
}

function Invoke-Haversine($lat1, $lon1, $lat2, $lon2) {
    $dLat = ($lat2 - $lat1) * [math]::PI / 180
    $dLon = ($lon2 - $lon1) * [math]::PI / 180
    $a    = [math]::Sin($dLat/2) * [math]::Sin($dLat/2) +
            [math]::Cos($lat1 * [math]::PI/180) * [math]::Cos($lat2 * [math]::PI/180) *
            [math]::Sin($dLon/2) * [math]::Sin($dLon/2)
    2 * $EARTH_RADIUS_MI * [math]::Asin([math]::Sqrt($a))
}

function Get-LogMetrics($buildId, $orgUrl, $hdrs) {
    $result = @{
        ImageCount  = 0
        MinLat = $null; MaxLat = $null; MinLon = $null; MaxLon = $null
        SqMiles     = 0.0
        LinearMiles = 0.0
        LogError    = $null
    }
    try {
        $logsResp = Invoke-RestMethod -Uri "$orgUrl/_apis/build/builds/$buildId/logs?api-version=7.1" -Headers $hdrs
        foreach ($log in $logsResp.value) {
            $lines = (Invoke-RestMethod -Uri $log.url -Headers $hdrs) -split "`n"
            foreach ($line in $lines) {
                if ($line -match 'Image added:') { $result.ImageCount++ }
                if ($line -match 'lat=([-\d.]+).*lon=([-\d.]+)') {
                    $lat = [double]$Matches[1]; $lon = [double]$Matches[2]
                    if ($null -eq $result.MinLat -or $lat -lt $result.MinLat) { $result.MinLat = $lat }
                    if ($null -eq $result.MaxLat -or $lat -gt $result.MaxLat) { $result.MaxLat = $lat }
                    if ($null -eq $result.MinLon -or $lon -lt $result.MinLon) { $result.MinLon = $lon }
                    if ($null -eq $result.MaxLon -or $lon -gt $result.MaxLon) { $result.MaxLon = $lon }
                }
            }
        }
        if ($null -ne $result.MinLat) {
            $latMi = Invoke-Haversine $result.MinLat $result.MinLon $result.MaxLat $result.MinLon
            $lonMi = Invoke-Haversine $result.MinLat $result.MinLon $result.MinLat $result.MaxLon
            $result.SqMiles     = [math]::Round($latMi * $lonMi, 2)
            $result.LinearMiles = [math]::Round($latMi + $lonMi, 2)
        }
    } catch {
        $result.LogError = $_.Exception.Message
    }
    return $result
}

$gdalByTile   = @{}
foreach ($b in $gdalBuilds)   { $gdalByTile[(Get-TileKey $b.buildNumber)]   = $b }
$mosaicByTile = @{}
foreach ($b in $mosaicBuilds) { $mosaicByTile[(Get-TileKey $b.buildNumber)] = $b }

$allKeys = (@($gdalByTile.Keys) + @($mosaicByTile.Keys)) | Sort-Object -Unique

$storedGdal   = @{}; foreach ($r in $store) { if ($r.GdalBuildId)   { $storedGdal[$r.GdalBuildId]    = $true } }
$storedMosaic = @{}; foreach ($r in $store) { if ($r.MosaicBuildId) { $storedMosaic[$r.MosaicBuildId] = $true } }

$newRecords = [System.Collections.Generic.List[object]]::new()

foreach ($key in $allKeys) {
    $gb = if ($gdalByTile.ContainsKey($key))   { $gdalByTile[$key]   } else { $null }
    $mb = if ($mosaicByTile.ContainsKey($key)) { $mosaicByTile[$key] } else { $null }

    $gbId = if ($gb) { $gb.id } else { $null }
    $mbId = if ($mb) { $mb.id } else { $null }

    $gbNew = $gbId -and -not $storedGdal.ContainsKey($gbId)
    $mbNew = $mbId -and -not $storedMosaic.ContainsKey($mbId)
    if (-not $gbNew -and -not $mbNew) {
        Write-Host "  [skip] $key - already in store" -ForegroundColor DarkGray
        continue
    }

    Write-Host "  [collect] $key" -ForegroundColor White -NoNewline

    $refBuild = if ($gb) { $gb } else { $mb }
    $cp       = Get-CompanyProject $refBuild.buildNumber

    $gHrs = if ($gb) { Get-DurHrs $gb } else { $null }
    $mHrs = if ($mb) { Get-DurHrs $mb } else { $null }
    $gHrsVal  = if ($null -ne $gHrs) { $gHrs } else { 0 }
    $mHrsVal  = if ($null -ne $mHrs) { $mHrs } else { 0 }
    $totalHrs = [math]::Round($gHrsVal + $mHrsVal, 4)

    $gResult  = if ($gb) { $gb.result } else { $null }
    $mResult  = if ($mb) { $mb.result } else { $null }
    $isRetrim = ($key -match '-retrim$')
    $failed   = ($gResult -and $gResult -ne "succeeded") -or ($mResult -and $mResult -ne "succeeded")

    # Log metrics from GDAL build
    $metrics = @{ ImageCount=0; SqMiles=0.0; LinearMiles=0.0; LogError="no gdal build" }
    if ($gb -and $gResult -eq "succeeded") {
        Write-Host " (logs...)" -ForegroundColor DarkGray -NoNewline
        $metrics = Get-LogMetrics $gb.id $DEVOPS_GDAL $headers
    }

    $computeCost = [math]::Round($totalHrs * $COMPUTE_RATE, 2)
    $imgCount    = $metrics.ImageCount

    $gHrsPerImg   = if ($imgCount -gt 0 -and $null -ne $gHrs) { [math]::Round($gHrs  / $imgCount, 6) } else { $null }
    $mHrsPerImg   = if ($imgCount -gt 0 -and $null -ne $mHrs) { [math]::Round($mHrs  / $imgCount, 6) } else { $null }
    $totHrsPerImg = if ($imgCount -gt 0)                       { [math]::Round($totalHrs / $imgCount, 6) } else { $null }
    $costPerImg   = if ($imgCount -gt 0)                       { [math]::Round($computeCost / $imgCount, 4) } else { $null }
    $costPerSqMi  = if ($metrics.SqMiles -gt 0)               { [math]::Round($computeCost / $metrics.SqMiles, 4) } else { $null }
    $imgPerSqMi   = if ($metrics.SqMiles -gt 0 -and $imgCount -gt 0) { [math]::Round($imgCount / $metrics.SqMiles, 2) } else { $null }

    $runDate = $null
    if ($mb -and $mb.finishTime)      { $runDate = $mb.finishTime }
    elseif ($gb -and $gb.finishTime)  { $runDate = $gb.finishTime }

    $record = [PSCustomObject]@{
        CollectedAt       = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
        RunDate           = $runDate
        TileKey           = $key
        Company           = $cp.Company
        Project           = $cp.Project
        IsRetrim          = $isRetrim
        Excluded          = $false
        ExcludedNote      = $null
        GdalBuildId       = $gbId
        MosaicBuildId     = $mbId
        GdalResult        = $gResult
        MosaicResult      = $mResult
        Failed            = $failed
        GdalHrs           = $gHrs
        MosaicHrs         = $mHrs
        TotalHrs          = $totalHrs
        ImageCount        = $imgCount
        SqMiles           = $metrics.SqMiles
        LinearMiles       = $metrics.LinearMiles
        MinLat            = $metrics.MinLat
        MaxLat            = $metrics.MaxLat
        MinLon            = $metrics.MinLon
        MaxLon            = $metrics.MaxLon
        LogError          = $metrics.LogError
        ComputeCost       = $computeCost
        ImagesPerTile     = $imgCount
        GdalHrsPerImage   = $gHrsPerImg
        MosaicHrsPerImage = $mHrsPerImg
        TotalHrsPerImage  = $totHrsPerImg
        CostPerImage      = $costPerImg
        CostPerSqMile     = $costPerSqMi
        ImagesPerSqMile   = $imgPerSqMi
    }

    $newRecords.Add($record)
    Write-Host " => $imgCount images, $($metrics.SqMiles) sq mi, $totalHrs hrs, `$$computeCost" -ForegroundColor Green
}

if ($newRecords.Count -eq 0) {
    Write-Host "`nNo new records this run." -ForegroundColor Yellow
} else {
    $merged = @($store) + @($newRecords)
    $merged | ConvertTo-Json -Depth 5 | Set-Content $DataFile -Encoding UTF8

    $merged | ForEach-Object {
        $row = [ordered]@{}
        $_.PSObject.Properties | ForEach-Object { $row[$_.Name] = if ($null -eq $_.Value) { "" } else { $_.Value } }
        [PSCustomObject]$row
    } | Export-Csv $CsvFile -NoTypeInformation -Encoding UTF8

    Write-Host "`nAppended $($newRecords.Count) new records. Store total: $($merged.Count)" -ForegroundColor Green
    Write-Host "JSON: $DataFile" -ForegroundColor Cyan
    Write-Host "CSV:  $CsvFile"  -ForegroundColor Cyan
}

$eligible = @(@($store) + @($newRecords)) | Where-Object {
    -not $_.Excluded -and -not $_.Failed -and -not $_.IsRetrim -and $_.ImageCount -gt 0
}

if ($eligible.Count -ge 3) {
    Write-Host "`n=== Efficiency Summary ($($eligible.Count) runs) ===" -ForegroundColor Yellow
    $avgImg      = [math]::Round(($eligible | Measure-Object ImageCount        -Average).Average, 0)
    $avgGHrImg   = [math]::Round(($eligible | Measure-Object GdalHrsPerImage   -Average).Average, 6)
    $avgMHrImg   = [math]::Round(($eligible | Measure-Object MosaicHrsPerImage -Average).Average, 6)
    $avgCostImg  = [math]::Round(($eligible | Measure-Object CostPerImage      -Average).Average, 4)
    $avgCostSqMi = [math]::Round(($eligible | Measure-Object CostPerSqMile     -Average).Average, 4)
    $avgImgSqMi  = [math]::Round(($eligible | Measure-Object ImagesPerSqMile   -Average).Average, 2)

    Write-Host "  Avg images/tile:      $avgImg"
    Write-Host "  Avg GDAL hrs/image:   $avgGHrImg"
    Write-Host "  Avg Mosaic hrs/image: $avgMHrImg"
    Write-Host "  Avg cost/image:       $avgCostImg"
    Write-Host "  Avg cost/sq mile:     $avgCostSqMi"
    Write-Host "  Avg images/sq mile:   $avgImgSqMi"
}
