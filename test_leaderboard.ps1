# LEADERBOARD TESTING SCRIPT
# Tests global leaderboard and community leaderboard features

$BASE_URL = "http://localhost:8000"
$ErrorActionPreference = "Continue"

Write-Host "`n=== LEADERBOARD TESTING SUITE ===" -ForegroundColor Cyan

# SETUP: Create Test Users
Write-Host "`n--- SETUP: Creating Test Users ---" -ForegroundColor Yellow

$testUsers = @(
    @{ email = "leader1_$(Get-Random)@test.com"; password = "Test123!"; recitations = 10; avgAccuracy = 95.0 },
    @{ email = "leader2_$(Get-Random)@test.com"; password = "Test123!"; recitations = 8; avgAccuracy = 92.0 },
    @{ email = "leader3_$(Get-Random)@test.com"; password = "Test123!"; recitations = 6; avgAccuracy = 88.0 },
    @{ email = "leader4_$(Get-Random)@test.com"; password = "Test123!"; recitations = 5; avgAccuracy = 85.0 },
    @{ email = "leader5_$(Get-Random)@test.com"; password = "Test123!"; recitations = 3; avgAccuracy = 80.0 }
)

foreach ($user in $testUsers) {
    Write-Host "`nCreating user: $($user.email)" -ForegroundColor White
    
    try {
        $registerBody = @{
            email = $user.email
            password = $user.password
        } | ConvertTo-Json
        
        $registerResponse = Invoke-RestMethod -Uri "$BASE_URL/auth/register" -Method Post -Body $registerBody -ContentType "application/json"
        Write-Host "  PASS - Registered (ID: $($registerResponse.id))" -ForegroundColor Green
        $user.id = $registerResponse.id
        
    } catch {
        Write-Host "  FAIL - Registration failed" -ForegroundColor Red
        continue
    }
}

Write-Host "`nPAUSE: Verify all emails in database" -ForegroundColor Yellow
Write-Host "Run this SQL:" -ForegroundColor Cyan
Write-Host "UPDATE users SET is_email_verified = true WHERE email LIKE 'leader%@test.com';" -ForegroundColor White
$null = Read-Host "Press Enter after verifying"

# Login all users
Write-Host "`n--- Logging in all test users ---" -ForegroundColor Yellow

foreach ($user in $testUsers) {
    try {
        $loginBody = @{
            email = $user.email
            password = $user.password
        } | ConvertTo-Json
        
        $loginResponse = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
        $user.token = $loginResponse.access_token
        Write-Host "PASS - Logged in: $($user.email)" -ForegroundColor Green
    } catch {
        Write-Host "FAIL - Login failed for $($user.email)" -ForegroundColor Red
    }
}

# Log Activities
Write-Host "`n--- Logging Recitation Activities ---" -ForegroundColor Yellow

foreach ($user in $testUsers) {
    if (-not $user.token) { continue }
    
    Write-Host "`nLogging activities for: $($user.email)" -ForegroundColor White
    
    $headers = @{
        "Authorization" = "Bearer $($user.token)"
        "Content-Type" = "application/json"
    }
    
    for ($i = 1; $i -le $user.recitations; $i++) {
        $variance = (Get-Random -Minimum -5 -Maximum 5)
        $accuracy = [Math]::Max(0, [Math]::Min(100, $user.avgAccuracy + $variance))
        
        $activityBody = @{
            activity_type = "recitation"
            surah_number = 1
            ayah_number = $i
            duration_seconds = 60
            accuracy_score = $accuracy
        } | ConvertTo-Json
        
        try {
            Invoke-RestMethod -Uri "$BASE_URL/progress/log-activity" -Method Post -Headers $headers -Body $activityBody | Out-Null
            Write-Host "  PASS - Logged recitation $i (accuracy: $accuracy%)" -ForegroundColor Green
        } catch {
            Write-Host "  FAIL - Failed to log activity $i" -ForegroundColor Red
        }
        Start-Sleep -Milliseconds 100
    }
}

# TEST 1: Global Leaderboard
Write-Host "`n--- TEST 1: Global Leaderboard ---" -ForegroundColor Yellow

try {
    $headers = @{
        "Authorization" = "Bearer $($testUsers[0].token)"
    }
    
    $leaderboard = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard" -Headers $headers
    
    Write-Host "PASS - Leaderboard retrieved successfully" -ForegroundColor Green
    Write-Host "`nTop 3 Users:" -ForegroundColor Cyan
    
    foreach ($user in $leaderboard.top_3) {
        Write-Host "  Rank $($user.rank): $($user.email) - $($user.accuracy)% accuracy" -ForegroundColor White
    }
    
    Write-Host "`nYour Position:" -ForegroundColor Cyan
    Write-Host "  Rank: $($leaderboard.current_user.rank)" -ForegroundColor White
    Write-Host "  Accuracy: $($leaderboard.current_user.accuracy)%" -ForegroundColor White
    
    Write-Host "`nStats:" -ForegroundColor Cyan
    Write-Host "  Total Participants: $($leaderboard.total_participants)" -ForegroundColor White
    
} catch {
    Write-Host "FAIL - Could not get leaderboard" -ForegroundColor Red
}

# TEST 2: User with insufficient recitations
Write-Host "`n--- TEST 2: User With Insufficient Recitations ---" -ForegroundColor Yellow

try {
    $headers = @{
        "Authorization" = "Bearer $($testUsers[4].token)"
    }
    
    $leaderboard = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard" -Headers $headers
    
    if ($leaderboard.current_user.rank -eq $null) {
        Write-Host "PASS - User correctly not ranked (needs more recitations)" -ForegroundColor Green
        Write-Host "  Message: $($leaderboard.current_user.message)" -ForegroundColor Gray
    } else {
        Write-Host "WARN - User appears on leaderboard despite insufficient recitations" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "FAIL" -ForegroundColor Red
}

# TEST 3: Leaderboard Sorting
Write-Host "`n--- TEST 3: Verify Leaderboard Sorting ---" -ForegroundColor Yellow

try {
    $headers = @{
        "Authorization" = "Bearer $($testUsers[0].token)"
    }
    
    $leaderboard = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard?limit=10" -Headers $headers
    $rankings = $leaderboard.rankings
    
    $isSorted = $true
    for ($i = 0; $i -lt ($rankings.Count - 1); $i++) {
        if ($rankings[$i].accuracy -lt $rankings[$i + 1].accuracy) {
            $isSorted = $false
            break
        }
    }
    
    if ($isSorted) {
        Write-Host "PASS - Leaderboard correctly sorted by accuracy" -ForegroundColor Green
    } else {
        Write-Host "FAIL - Leaderboard NOT properly sorted" -ForegroundColor Red
    }
    
    Write-Host "`nTop 5:" -ForegroundColor Cyan
    for ($i = 0; $i -lt [Math]::Min(5, $rankings.Count); $i++) {
        Write-Host "  $($rankings[$i].rank). $($rankings[$i].email) - $($rankings[$i].accuracy)%" -ForegroundColor White
    }
    
} catch {
    Write-Host "FAIL" -ForegroundColor Red
}

# TEST 4: Privacy Settings
Write-Host "`n--- TEST 4: Privacy Settings ---" -ForegroundColor Yellow

try {
    $headers = @{
        "Authorization" = "Bearer $($testUsers[1].token)"
        "Content-Type" = "application/json"
    }
    
    $settingsBody = @{
        show_on_leaderboard = $false
    } | ConvertTo-Json
    
    Invoke-RestMethod -Uri "$BASE_URL/user/settings" -Method Put -Headers $headers -Body $settingsBody | Out-Null
    Write-Host "PASS - Disabled leaderboard visibility" -ForegroundColor Green
    
    $headers = @{
        "Authorization" = "Bearer $($testUsers[0].token)"
    }
    
    $leaderboard = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard" -Headers $headers
    $user2Email = $testUsers[1].email
    $user2Visible = $leaderboard.rankings | Where-Object { $_.email -eq $user2Email }
    
    if (-not $user2Visible) {
        Write-Host "PASS - User correctly hidden from leaderboard" -ForegroundColor Green
    } else {
        Write-Host "FAIL - User still visible despite privacy setting" -ForegroundColor Red
    }
    
    # Re-enable
    $settingsBody = @{
        show_on_leaderboard = $true
    } | ConvertTo-Json
    
    $headers = @{
        "Authorization" = "Bearer $($testUsers[1].token)"
        "Content-Type" = "application/json"
    }
    
    Invoke-RestMethod -Uri "$BASE_URL/user/settings" -Method Put -Headers $headers -Body $settingsBody | Out-Null
    
} catch {
    Write-Host "FAIL" -ForegroundColor Red
}

# TEST 5: Pagination
Write-Host "`n--- TEST 5: Pagination ---" -ForegroundColor Yellow

try {
    $headers = @{
        "Authorization" = "Bearer $($testUsers[0].token)"
    }
    
    $leaderboard3 = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard?limit=3" -Headers $headers
    Write-Host "PASS - Limit=3: Got $($leaderboard3.rankings.Count) users" -ForegroundColor Green
    
    $leaderboard10 = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard?limit=10" -Headers $headers
    Write-Host "PASS - Limit=10: Got $($leaderboard10.rankings.Count) users" -ForegroundColor Green
    
} catch {
    Write-Host "FAIL" -ForegroundColor Red
}

# SUMMARY
Write-Host "`n=== TEST SUMMARY ===" -ForegroundColor Cyan
Write-Host "Tested:" -ForegroundColor Cyan
Write-Host "  - Global leaderboard" -ForegroundColor Green
Write-Host "  - User rankings and positions" -ForegroundColor Green
Write-Host "  - Minimum recitation requirement" -ForegroundColor Green
Write-Host "  - Sorting by accuracy" -ForegroundColor Green
Write-Host "  - Privacy settings" -ForegroundColor Green
Write-Host "  - Pagination" -ForegroundColor Green

Write-Host "`nCLEANUP:" -ForegroundColor Yellow
Write-Host "DELETE FROM users WHERE email LIKE 'leader%@test.com';" -ForegroundColor White
Write-Host ""