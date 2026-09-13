# Get-ResourceTypeBreakdown.ps1
param([string]$SubscriptionId = "fa7f37c0-b488-4dee-81b1-a00a4e0da4bd")

$body = '{"type":"ActualCost","timeframe":"Custom","timePeriod":{"from":"2026-01-01","to":"2026-06-18"},"dataset":{"granularity":"Monthly","aggregation":{"totalCost":{"name":"Cost","function":"Sum"}},"grouping":[{"type":"Dimension","name":"ResourceId"},{"type":"Dimension","name":"MeterSubCategory"}]}}'
[System.IO.File]::WriteAllText("$env:TEMP\cmquery.json", $body, [System.Text.Encoding]::UTF8)
$r = az rest --method post --uri "https://management.azure.com/subscriptions/$SubscriptionId/providers/Microsoft.CostManagement/query?api-version=2023-11-01" --headers "Content-Type=application/json" --body "@$env:TEMP\cmquery.json" | ConvertFrom-Json

$months = @("01/2026","02/2026","03/2026","04/2026","05/2026","06/2026")
$ml     = @{"01/2026"="Jan";"02/2026"="Feb";"03/2026"="Mar";"04/2026"="Apr";"05/2026"="May";"06/2026"="Jun"}

function Get-CostType($subcat) {
    $m = [string]$subcat
    if ($m -match "Virtual Machine|FSv2|Ddsv4|DSv|FSv|BS Series|Esv|Compute|Pipelines|DevOps|Automation") { return "Compute" }
    if ($m -match "Data Transfer|Bandwidth|Egress|CDN|Rtn Preference|Inter.Continent|Inter.Region")        { return "Egress"   }
    if ($m -match "Managed Disk|Blob|Files|LRS|ZRS|GRS|Storage|Backup|Queue|Table|Premium SSD|Standard SSD|Standard HDD|General Block") { return "Storage" }
    return "Other"
}

$parsed = [System.Collections.Generic.List[object]]::new()
foreach ($row in $r.properties.rows) {
    if ($null -eq $row) { continue }
    $res    = ([string]$row[2] -split '/')[-1]
    $subcat = [string]$row[3]
    $cost   = [double]$row[0]
    $month  = if ([string]$row[1] -match '(\d{4})-(\d{2})') { "$($Matches[2])/$($Matches[1])" } else { [string]$row[1] }
    $type   = Get-CostType $subcat
    $parsed.Add([PSCustomObject]@{ Resource=$res; Subcat=$subcat; Month=$month; Cost=$cost; Type=$type })
}

# Top 30 resources with monthly totals
Write-Host "`n=== Monthly Cost per Resource (Top 30) ===" -ForegroundColor Yellow
$resTable = $parsed | Group-Object Resource | ForEach-Object {
    $grp = $_.Group
    $row = [ordered]@{ Resource = $_.Name }
    $tot = 0
    foreach ($mo in $months) {
        $v = [math]::Round(($grp | Where-Object { $_.Month -eq $mo } | Measure-Object Cost -Sum).Sum, 2)
        $row[$ml[$mo]] = $v
        $tot += $v
    }
    $row["Total"] = [math]::Round($tot, 2)
    [PSCustomObject]$row
}
$resTable | Where-Object { $_.Total -gt 0 } | Sort-Object Total -Descending | Select-Object -First 30 | Format-Table -AutoSize

# Compute / Storage / Egress / Other breakdown per month
Write-Host "`n=== Monthly Totals by Type ===" -ForegroundColor Yellow
$typeTable = foreach ($type in @("Compute","Storage","Egress","Other")) {
    $row = [ordered]@{ Type = $type }
    $tot = 0
    foreach ($mo in $months) {
        $v = [math]::Round(($parsed | Where-Object { $_.Type -eq $type -and $_.Month -eq $mo } | Measure-Object Cost -Sum).Sum, 2)
        $row[$ml[$mo]] = $v
        $tot += $v
    }
    $row["Total"] = [math]::Round($tot, 2)
    [PSCustomObject]$row
}
$typeTable | Format-Table -AutoSize

# Grand total
$grandRow = [ordered]@{ Type = "GRAND TOTAL" }
$grand = 0
foreach ($mo in $months) {
    $v = [math]::Round(($parsed | Where-Object { $_.Month -eq $mo } | Measure-Object Cost -Sum).Sum, 2)
    $grandRow[$ml[$mo]] = $v
    $grand += $v
}
$grandRow["Total"] = [math]::Round($grand, 2)
[PSCustomObject]$grandRow | Format-Table -AutoSize

# Per-resource compute/storage/egress split
Write-Host "`n=== Top 20 Resources: Compute / Storage / Egress Split (YTD) ===" -ForegroundColor Yellow
$splitTable = $parsed | Group-Object Resource | ForEach-Object {
    $grp     = $_.Group
    $compute = [math]::Round(($grp | Where-Object Type -eq "Compute" | Measure-Object Cost -Sum).Sum, 2)
    $storage = [math]::Round(($grp | Where-Object Type -eq "Storage" | Measure-Object Cost -Sum).Sum, 2)
    $egress  = [math]::Round(($grp | Where-Object Type -eq "Egress"  | Measure-Object Cost -Sum).Sum, 2)
    $other   = [math]::Round(($grp | Where-Object Type -eq "Other"   | Measure-Object Cost -Sum).Sum, 2)
    $total   = [math]::Round($compute + $storage + $egress + $other, 2)
    [PSCustomObject]@{ Resource=$_.Name; Compute=$compute; Storage=$storage; Egress=$egress; Other=$other; Total=$total }
}
$splitTable | Where-Object { $_.Total -gt 0 } | Sort-Object Total -Descending | Select-Object -First 20 | Format-Table -AutoSize
