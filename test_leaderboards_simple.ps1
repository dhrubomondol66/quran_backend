# TEST LEADERBOARDS
$BASE_URL = "http://localhost:8000"

Write-Host "`n=== LEADERBOARD TESTING ===" -ForegroundColor Cyan

# Login
$email = Read-Host "Email"
$password = Read-Host "Password" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

$loginBody = @{ email = $email; password = $passwordPlain } | ConvertTo-Json
$loginResponse = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$TOKEN = $loginResponse.access_token
Write-Host "Logged in`n" -ForegroundColor Green

$headers = @{ "Authorization" = "Bearer $TOKEN" }

# Global Leaderboard
Write-Host "--- Global Leaderboard ---" -ForegroundColor Yellow
$global = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard" -Headers $headers

Write-Host "`nTOP 3:" -ForegroundColor Cyan
foreach ($user in $global.top_3) {
    Write-Host "  #$($user.rank) - $($user.name) - $($user.accuracy)%" -ForegroundColor White
}

Write-Host "`nSTATS:" -ForegroundColor Cyan
Write-Host "  Total: $($global.total_participants)" -ForegroundColor White
Write-Host "  Your rank: #$($global.current_user.rank)" -ForegroundColor Yellow

Write-Host "`nTOP 10:" -ForegroundColor Cyan
$global.rankings | Select-Object -First 10 | ForEach-Object {
    $you = if ($_.is_you) { " (YOU)" } else { "" }
    Write-Host "  #$($_.rank) - $($_.name)$you - $($_.accuracy)%" -ForegroundColor White
}

# Communities
Write-Host "`n--- Communities ---" -ForegroundColor Yellow
$communities = Invoke-RestMethod -Uri "$BASE_URL/community/communities" -Headers $headers

if ($communities.Count -gt 0) {
    foreach ($comm in $communities) {
        Write-Host "`n$($comm.name):" -ForegroundColor Cyan
        
        $commLeaderboard = Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($comm.id)/leaderboard" -Headers $headers
        
        Write-Host "  Participants: $($commLeaderboard.total_participants)" -ForegroundColor White
        Write-Host "  Your rank: #$($commLeaderboard.current_user.rank)" -ForegroundColor Yellow
        
        if ($commLeaderboard.top_3.Count -gt 0) {
            Write-Host "  Top 3:" -ForegroundColor Gray
            foreach ($user in $commLeaderboard.top_3) {
                Write-Host "    #$($user.rank) - $($user.name) - $($user.accuracy)%" -ForegroundColor White
            }
        }
    }
} else {
    Write-Host "No communities" -ForegroundColor Gray
}

Write-Host "`n=== DONE ===" -ForegroundColor Cyan
Write-Host ""
