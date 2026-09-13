# Get-AzureCostSummary.ps1
param(
    [string]$SubscriptionId = "fa7f37c0-b488-4dee-81b1-a00a4e0da4bd",
    [string]$StartDate = (Get-Date -Day 1 -Format "yyyy-MM-dd"),
    [string]$EndDate   = (Get-Date -Format "yyyy-MM-dd")
)

function Sum-Cost($group) {
    ($group | ForEach-Object { [double]$_.properties.costInUSD } | Measure-Object -Sum).Sum
}

$baseUri = "https://management.azure.com/subscriptions/$SubscriptionId/providers/Microsoft.Consumption/usageDetails"
$filter  = "properties/usageStart ge '$StartDate' and properties/usageEnd le '$EndDate'"
$uri     = $baseUri + "?api-version=2023-05-01&" + '$filter' + "=" + $filter

Write-Host "Fetching usage details from $StartDate to $EndDate ..." -ForegroundColor Cyan

$allRecords = [System.Collections.Generic.List[object]]::new()
$page = 0

do {
    $page++
    Write-Host ("  Page " + $page + " - fetched " + $allRecords.Count + " records so far") -ForegroundColor DarkGray
    $response = az rest --method get --uri $uri | ConvertFrom-Json
    if ($response.value) {
        $allRecords.AddRange($response.value)
    }
    $uri = $response.nextLink
} while ($uri)

Write-Host "Total records: $($allRecords.Count)" -ForegroundColor Cyan
Write-Host ""

# By Service Category
$byCategory = $allRecords |
    Group-Object { $_.properties.meterCategory } |
    ForEach-Object {
        [PSCustomObject]@{
            Category = $_.Name
            Cost     = [math]::Round((Sum-Cost $_.Group), 2)
        }
    } |
    Sort-Object Cost -Descending

Write-Host "=== Cost by Service Category ===" -ForegroundColor Yellow
$byCategory | Format-Table -AutoSize

# Top 20 Resources
$byResource = $allRecords |
    Group-Object { $_.properties.instanceName } |
    ForEach-Object {
        $props = $_.Group[0].properties
        [PSCustomObject]@{
            Resource      = ($props.instanceName -split '/')[-1]
            ResourceGroup = $props.resourceGroup
            Category      = $props.meterCategory
            Cost          = [math]::Round((Sum-Cost $_.Group), 2)
        }
    } |
    Sort-Object Cost -Descending |
    Select-Object -First 20

Write-Host "=== Top 20 Resources by Cost ===" -ForegroundColor Yellow
$byResource | Format-Table -AutoSize

# Resources tagged delete:yes
$deleteTagged = $allRecords |
    Where-Object { $_.tags -and $_.tags.delete -eq 'yes' } |
    Group-Object { $_.properties.instanceName } |
    ForEach-Object {
        [PSCustomObject]@{
            Resource = ($_.Group[0].properties.instanceName -split '/')[-1]
            Cost     = [math]::Round((Sum-Cost $_.Group), 2)
        }
    } |
    Sort-Object Cost -Descending

if ($deleteTagged) {
    Write-Host "=== Resources Tagged 'delete:yes' (still running!) ===" -ForegroundColor Red
    $deleteTagged | Format-Table -AutoSize
    $deletedTotal = [math]::Round(($deleteTagged | ForEach-Object { $_.Cost } | Measure-Object -Sum).Sum, 2)
    Write-Host ("  Wasted spend this period: $" + $deletedTotal) -ForegroundColor Red
    Write-Host ""
}

# Daily spend trend
$byDay = $allRecords |
    Group-Object { ($_.properties.date -split 'T')[0] } |
    ForEach-Object {
        [PSCustomObject]@{
            Date = $_.Name
            Cost = [math]::Round((Sum-Cost $_.Group), 2)
        }
    } |
    Sort-Object Date

Write-Host "=== Daily Spend Trend ===" -ForegroundColor Yellow
$byDay | Format-Table -AutoSize

$total       = [math]::Round((Sum-Cost $allRecords), 2)
$daysElapsed = ($byDay | Measure-Object).Count
$projMonthly = if ($daysElapsed -gt 0) { [math]::Round($total / $daysElapsed * 30, 2) } else { 0 }

Write-Host "=== Summary ===" -ForegroundColor Green
Write-Host ("  Period spend        : $" + $total)
Write-Host ("  Days in period      : $daysElapsed")
Write-Host ("  Projected monthly   : $" + $projMonthly)
