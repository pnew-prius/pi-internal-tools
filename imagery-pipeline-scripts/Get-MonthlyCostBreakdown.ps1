# Get-MonthlyCostBreakdown.ps1
# Uses CostManagement/query API (requires Cost Management Reader) for real monthly history.

param(
    [string]$SubscriptionId = "fa7f37c0-b488-4dee-81b1-a00a4e0da4bd"
)

$uri = "https://management.azure.com/subscriptions/$SubscriptionId/providers/Microsoft.CostManagement/query?api-version=2023-11-01"

function Invoke-CostQuery($bodyJson) {
    $tmpFile = "$env:TEMP\cmquery_$([System.IO.Path]::GetRandomFileName()).json"
    $bodyJson | Out-File -Encoding utf8 -FilePath $tmpFile
    $result = az rest --method post --uri $uri --headers "Content-Type=application/json" --body "@$tmpFile" | ConvertFrom-Json
    Remove-Item $tmpFile -ErrorAction SilentlyContinue
    return $result
}

# ── By Category, monthly ──────────────────────────────────────────────────────
Write-Host "Querying cost by service category (monthly)..." -ForegroundColor Cyan
$catBody = @'
{
  "type": "ActualCost",
  "timeframe": "Custom",
  "timePeriod": { "from": "2026-01-01", "to": "2026-06-18" },
  "dataset": {
    "granularity": "Monthly",
    "aggregation": { "totalCost": { "name": "Cost", "function": "Sum" } },
    "grouping": [{ "type": "Dimension", "name": "ServiceName" }]
  }
}
'@
$catResult = Invoke-CostQuery $catBody

# ── By Resource, monthly ──────────────────────────────────────────────────────
Write-Host "Querying cost by resource (monthly)..." -ForegroundColor Cyan
$resBody = @'
{
  "type": "ActualCost",
  "timeframe": "Custom",
  "timePeriod": { "from": "2026-01-01", "to": "2026-06-18" },
  "dataset": {
    "granularity": "Monthly",
    "aggregation": { "totalCost": { "name": "Cost", "function": "Sum" } },
    "grouping": [{ "type": "Dimension", "name": "ResourceId" }]
  }
}
'@
$resResult = Invoke-CostQuery $resBody

# ── Parse and display ─────────────────────────────────────────────────────────
function Parse-CostResult($result, $nameColIndex) {
    $cols   = $result.properties.columns | ForEach-Object { $_.name }
    $costIdx = ($cols | Select-String "Cost" | Select-Object -First 1).LineNumber - 1
    $nameIdx = $nameColIndex
    $dateIdx = ($cols | ForEach-Object { $_ } | Select-String "BillingMonth|UsageDate|Month" | Select-Object -First 1).LineNumber - 1

    $rows = @{}
    foreach ($row in $result.properties.rows) {
        $name = $row[$nameIdx]
        $cost = [math]::Round([double]$row[$costIdx], 2)
        $date = $row[$dateIdx]
        $month = if ($date -match '(\d{4})(\d{2})') { "$($Matches[2])/$($Matches[1])" }
                 elseif ($date -match '(\d{4})-(\d{2})') { "$($Matches[2])/$($Matches[1])" }
                 else { $date }
        if (-not $rows.ContainsKey($name)) { $rows[$name] = @{} }
        $rows[$name][$month] = $cost
    }
    return $rows
}

# Detect column indices from actual response
function Get-ColIndex($result, $pattern) {
    $cols = $result.properties.columns | ForEach-Object { $_.name }
    for ($i = 0; $i -lt $cols.Count; $i++) {
        if ($cols[$i] -match $pattern) { return $i }
    }
    return -1
}

Write-Host "`nColumn names returned:" -ForegroundColor DarkGray
$catResult.properties.columns | ForEach-Object { Write-Host "  $($_.name)" -ForegroundColor DarkGray }

$costIdx  = Get-ColIndex $catResult "Cost"
$nameIdx  = Get-ColIndex $catResult "ServiceName"
$monthIdx = Get-ColIndex $catResult "Month|BillingMonth|UsageDate|Date"

Write-Host ("Cost col: $costIdx, Name col: $nameIdx, Month col: $monthIdx") -ForegroundColor DarkGray

$months = @("01/2026","02/2026","03/2026","04/2026","05/2026","06/2026")
$mLabels = @{"01/2026"="Jan";"02/2026"="Feb";"03/2026"="Mar";"04/2026"="Apr";"05/2026"="May";"06/2026"="Jun"}

# Category table
$catData = @{}
foreach ($row in $catResult.properties.rows) {
    $name  = $row[$nameIdx]
    $cost  = [math]::Round([double]$row[$costIdx], 2)
    $rawDate = "$($row[$monthIdx])"
    $month = if ($rawDate -match '(\d{4})(\d{2})(\d{2})') { "$($Matches[2])/$($Matches[1])" }
             elseif ($rawDate -match '(\d{4})-(\d{2})') { "$($Matches[2])/$($Matches[1])" }
             else { $rawDate }
    if (-not $catData.ContainsKey($name)) { $catData[$name] = @{} }
    $catData[$name][$month] = $cost
}

Write-Host "`n=== Monthly Cost by Service Category ===" -ForegroundColor Yellow
$catRows = $catData.Keys | ForEach-Object {
    $n = $_
    $row = [ordered]@{ Category = $n }
    $total = 0
    foreach ($m in $months) {
        $v = if ($catData[$n].ContainsKey($m)) { $catData[$n][$m] } else { 0 }
        $row[$mLabels[$m]] = $v
        $total += $v
    }
    $row["Total"] = [math]::Round($total, 2)
    [PSCustomObject]$row
} | Sort-Object Total -Descending
$catRows | Format-Table -AutoSize

# Resource table
$resNameIdx  = Get-ColIndex $resResult "ResourceId"
$resCostIdx  = Get-ColIndex $resResult "Cost"
$resMonthIdx = Get-ColIndex $resResult "Month|BillingMonth|UsageDate|Date"

$resData = @{}
foreach ($row in $resResult.properties.rows) {
    $name  = ($row[$resNameIdx] -split '/')[-1]
    $cost  = [math]::Round([double]$row[$resCostIdx], 2)
    $rawDate = "$($row[$resMonthIdx])"
    $month = if ($rawDate -match '(\d{4})(\d{2})(\d{2})') { "$($Matches[2])/$($Matches[1])" }
             elseif ($rawDate -match '(\d{4})-(\d{2})') { "$($Matches[2])/$($Matches[1])" }
             else { $rawDate }
    if (-not $resData.ContainsKey($name)) { $resData[$name] = @{} }
    if ($resData[$name].ContainsKey($month)) { $resData[$name][$month] += $cost }
    else { $resData[$name][$month] = $cost }
}

Write-Host "=== Monthly Cost - Top 25 Resources ===" -ForegroundColor Yellow
$resRows = $resData.Keys | ForEach-Object {
    $n = $_
    $row = [ordered]@{ Resource = $n }
    $total = 0
    foreach ($m in $months) {
        $v = if ($resData[$n].ContainsKey($m)) { $resData[$n][$m] } else { 0 }
        $row[$mLabels[$m]] = [math]::Round($v, 2)
        $total += $v
    }
    $row["Total"] = [math]::Round($total, 2)
    [PSCustomObject]$row
} | Sort-Object Total -Descending | Select-Object -First 25
$resRows | Format-Table -AutoSize

# Grand totals
Write-Host "=== Monthly Totals ===" -ForegroundColor Green
$totRow = [ordered]@{ Month = "TOTAL" }
$grand = 0
foreach ($m in $months) {
    $v = [math]::Round(($catData.Values | ForEach-Object { if ($_.ContainsKey($m)) { $_[$m] } else { 0 } } | Measure-Object -Sum).Sum, 2)
    $totRow[$mLabels[$m]] = $v
    $grand += $v
}
$totRow["YTD"] = [math]::Round($grand, 2)
[PSCustomObject]$totRow | Format-Table -AutoSize
