# TEST ACTIVITIES
$BASE_URL = "http://localhost:8000"

Write-Host "`n=== ACTIVITY TESTING ===" -ForegroundColor Cyan

# Login
$email = Read-Host "Email"
$password = Read-Host "Password" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

$loginBody = @{ email = $email; password = $passwordPlain } | ConvertTo-Json
$loginResponse = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$TOKEN = $loginResponse.access_token
Write-Host "Logged in`n" -ForegroundColor Green

$headers = @{ "Authorization" = "Bearer $TOKEN" }

# Summary
Write-Host "--- Summary ---" -ForegroundColor Yellow
$summary = Invoke-RestMethod -Uri "$BASE_URL/analytics/activity/summary" -Headers $headers

Write-Host "Today: $($summary.today_minutes) minutes" -ForegroundColor White
Write-Host "Week: $($summary.week_minutes) minutes" -ForegroundColor White
Write-Host "Month: $($summary.month_minutes) minutes" -ForegroundColor White
Write-Host "Streak: $($summary.current_streak) days" -ForegroundColor Yellow

# Daily
Write-Host "`n--- Daily Activity ---" -ForegroundColor Yellow
$daily = Invoke-RestMethod -Uri "$BASE_URL/analytics/activity/daily" -Headers $headers

Write-Host "Date: $($daily.date)" -ForegroundColor Cyan
Write-Host "Total: $($daily.total_minutes) minutes" -ForegroundColor White
Write-Host "Summary: $($daily.summary)" -ForegroundColor Gray

if ($daily.activity_times.Count -gt 0) {
    Write-Host "`nActivity Times:" -ForegroundColor Cyan
    foreach ($activity in $daily.activity_times) {
        Write-Host "  $($activity.time) - $($activity.minutes)m ($($activity.recitations)x)" -ForegroundColor White
    }
}

# Weekly
Write-Host "`n--- Weekly Activity ---" -ForegroundColor Yellow
$weekly = Invoke-RestMethod -Uri "$BASE_URL/analytics/activity/weekly" -Headers $headers

Write-Host "Week: $($weekly.week_start) to $($weekly.week_end)" -ForegroundColor Cyan
Write-Host "Total: $($weekly.total_minutes) minutes" -ForegroundColor White
Write-Host "Summary: $($weekly.summary)" -ForegroundColor Gray

Write-Host "`nDaily Breakdown:" -ForegroundColor Cyan
foreach ($day in $weekly.daily_breakdown) {
    Write-Host "  $($day.day) - $($day.minutes)m ($($day.recitations)x)" -ForegroundColor White
}

# Monthly
Write-Host "`n--- Monthly Activity ---" -ForegroundColor Yellow
$monthly = Invoke-RestMethod -Uri "$BASE_URL/analytics/activity/monthly" -Headers $headers

Write-Host "Month: $($monthly.month)/$($monthly.year)" -ForegroundColor Cyan
Write-Host "Total: $($monthly.total_minutes) minutes" -ForegroundColor White
Write-Host "Summary: $($monthly.summary)" -ForegroundColor Gray

Write-Host "`nWeekly Breakdown:" -ForegroundColor Cyan
foreach ($week in $monthly.weekly_breakdown) {
    Write-Host "  $($week.week_label) - $($week.minutes)m ($($week.recitations)x)" -ForegroundColor White
}

Write-Host "`n=== DONE ===" -ForegroundColor Cyan
Write-Host ""
