param(
    [string]$SubscriptionId = "fa7f37c0-b488-4dee-81b1-a00a4e0da4bd"
)

$rate           = 0.816
$storagePerGBmo = 0.018
$egressPerGB    = 0.087

$devopsToken = az account get-access-token --resource "499b84ac-1321-427f-aa17-267ca6975798" | ConvertFrom-Json
$headers = @{ Authorization = "Bearer $($devopsToken.accessToken)"; "Content-Type" = "application/json" }

$gdalBuilds   = (Invoke-RestMethod -Uri "https://dev.azure.com/PriusIntelli/5942a494-b65d-4b83-8eb9-ebb6cce89e99/_apis/build/builds?definitions=12&`$top=500&api-version=7.1" -Headers $headers).value
$mosaicBuilds = (Invoke-RestMethod -Uri "https://dev.azure.com/PriusIntelli/0709c1b8-2c78-4a24-81b4-af6ac1645690/_apis/build/builds?definitions=5&`$top=500&api-version=7.1" -Headers $headers).value

function Get-TileKey($name) { $name -replace '^[^-]+-','' }
function Get-DurHrs($build) {
    if ($build.finishTime -and $build.startTime) {
        [math]::Round(([datetime]$build.finishTime - [datetime]$build.startTime).TotalHours, 3)
    } else { 0 }
}

$gdalMap = @{}
foreach ($b in ($gdalBuilds | Where-Object { $_.result -eq "succeeded" })) {
    $gdalMap[(Get-TileKey $b.buildNumber)] = Get-DurHrs $b
}
$mosaicMap = @{}
foreach ($b in ($mosaicBuilds | Where-Object { $_.result -eq "succeeded" })) {
    $mosaicMap[(Get-TileKey $b.buildNumber)] = Get-DurHrs $b
}

$completed  = az storage blob list --account-name pigisstorage4361 --container-name completed --auth-mode login --query "[].{name:name,size:properties.contentLength}" | ConvertFrom-Json
$inputBlobs = az storage blob list --account-name piimageprocessing --container-name gdal-processing --auth-mode login --query "[].{name:name,size:properties.contentLength}" | ConvertFrom-Json

$inputMap = @{}
foreach ($b in $inputBlobs) {
    $key = $b.name -replace '\.zip$','' -replace '-retrim$',''
    $inputMap[$key] = [math]::Round($b.size/1GB, 2)
}

$tileStorage = $completed | Where-Object { $_.name -match '^[^/]+/[^/]+/[^/]+/' } | ForEach-Object {
    $parts = $_.name -split '/'
    [PSCustomObject]@{
        Company = $parts[0]; Project = $parts[1].ToUpper()
        Tile    = $parts[2]; SizeGB  = [math]::Round($_.size/1GB, 3)
    }
} | Group-Object { "$($_.Company)|$($_.Project)|$($_.Tile)" } | ForEach-Object {
    $g = $_.Group
    [PSCustomObject]@{
        Company  = $g[0].Company
        Project  = $g[0].Project
        Tile     = $g[0].Tile
        OutputGB = [math]::Round(($g | Measure-Object SizeGB -Sum).Sum, 2)
    }
}

Write-Host "=== Per-Tile Cost (Compute + Storage) ===" -ForegroundColor Yellow
Write-Host ("{0,-28} {1,-16} {2,-18} {3,8} {4,8} {5,8} {6,10} {7,10} {8,10} {9,10}" -f `
    "Tile","Company","Project","GdalHrs","MosHrs","InGB","OutGB","Compute","Storage","Total")
Write-Host ("{0,-28} {1,-16} {2,-18} {3,8} {4,8} {5,8} {6,10} {7,10} {8,10} {9,10}" -f `
    "----","-------","-------","-------","------","----","-----","-------","-------","-----")

$matchedTiles = foreach ($t in ($tileStorage | Sort-Object Company,Project,Tile)) {
    $tileKey = $t.Tile
    $gHrs    = if ($gdalMap.ContainsKey($tileKey))   { $gdalMap[$tileKey]   } else { $null }
    $mHrs    = if ($mosaicMap.ContainsKey($tileKey)) { $mosaicMap[$tileKey] } else { $null }
    $inGB    = if ($inputMap.ContainsKey($tileKey))  { $inputMap[$tileKey]  } else { $null }
    $matched = ($null -ne $gHrs) -or ($null -ne $mHrs)

    $gHrsVal  = if ($null -ne $gHrs)  { $gHrs }  else { 0 }
    $mHrsVal  = if ($null -ne $mHrs)  { $mHrs }  else { 0 }
    $inGBVal  = if ($null -ne $inGB)  { $inGB }  else { 0 }

    $totalHrs    = [math]::Round($gHrsVal + $mHrsVal, 2)
    $computeCost = [math]::Round($totalHrs * $rate, 2)
    $storageCost = [math]::Round(($inGBVal + $t.OutputGB) * $storagePerGBmo, 2)
    $total       = [math]::Round($computeCost + $storageCost, 2)

    $flag = if ($matched) { "" } else { " *" }
    $gLabel = if ($null -ne $gHrs) { "{0:F2}" -f $gHrs } else { "-" }
    $mLabel = if ($null -ne $mHrs) { "{0:F2}" -f $mHrs } else { "-" }
    $iLabel = if ($null -ne $inGB) { "{0:F1}" -f $inGB } else { "-" }
    Write-Host ("{0,-28} {1,-16} {2,-18} {3,8} {4,8} {5,8} {6,10} {7,10:C2} {8,10:C2} {9,10:C2}{10}" -f `
        $t.Tile, $t.Company, $t.Project,
        $gLabel, $mLabel, $iLabel,
        ("{0:F1}" -f $t.OutputGB),
        $computeCost, $storageCost, $total, $flag)

    [PSCustomObject]@{
        Company=$t.Company; Project=$t.Project; Tile=$t.Tile
        Matched=$matched; GdalHrs=$gHrsVal; MosaicHrs=$mHrsVal
        TotalHrs=$totalHrs; InputGB=$inGBVal; OutputGB=$t.OutputGB
        ComputeCost=$computeCost; StorageCost=$storageCost; Total=$total
    }
}

Write-Host ""
Write-Host "* = no pipeline run matched (history likely deleted)" -ForegroundColor DarkGray

Write-Host "`n=== Project Rollup ===" -ForegroundColor Green
$matchedTiles | Group-Object { "$($_.Company)|$($_.Project)" } | ForEach-Object {
    $g       = $_.Group
    $matched = ($g | Where-Object { $_.Matched }).Count
    $compute = [math]::Round(($g | Measure-Object ComputeCost -Sum).Sum, 2)
    $storage = [math]::Round(($g | Measure-Object StorageCost -Sum).Sum, 2)
    $inGB    = [math]::Round(($g | Measure-Object InputGB  -Sum).Sum, 1)
    $outGB   = [math]::Round(($g | Measure-Object OutputGB -Sum).Sum, 1)
    $hrs     = [math]::Round(($g | Measure-Object TotalHrs -Sum).Sum, 1)
    [PSCustomObject]@{
        Company     = $g[0].Company
        Project     = $g[0].Project
        Tiles       = $g.Count
        PipelineMatch = "$matched/$($g.Count)"
        TotalHrs    = $hrs
        InputGB     = $inGB
        OutputGB    = $outGB
        ComputeCost = "`$$compute"
        StorageCost = "`$$storage"
        TotalCost   = "`$" + [math]::Round($compute + $storage, 2)
    }
} | Sort-Object Company, Project | Out-Host
