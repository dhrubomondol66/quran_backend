# QURAN API TEST - Copy this entire script
$BASE_URL = "http://localhost:8000"
$TEST_EMAIL = "testuser_$(Get-Random)@example.com"
$TEST_PASSWORD = "TestPassword123!"
$TOKEN = ""
$passed = 0
$failed = 0

Write-Host "`n=== QURAN API TESTS ===" -ForegroundColor Cyan

# TEST 1: Health
Write-Host "`nTesting: Health Check" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/health" -Method Get
    Write-Host "PASS - Status: $($response.status)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "FAIL" -ForegroundColor Red
    $failed++
}

# TEST 2: Register
Write-Host "`nTesting: Register User" -ForegroundColor White
Write-Host "Email: $TEST_EMAIL" -ForegroundColor Gray
try {
    $body = @{ email = $TEST_EMAIL; password = $TEST_PASSWORD } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/register" -Method Post -Body $body -ContentType "application/json"
    Write-Host "PASS - User registered" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "FAIL - $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

# VERIFY EMAIL
Write-Host "`nVERIFY EMAIL IN DATABASE:" -ForegroundColor Yellow
Write-Host "UPDATE users SET is_email_verified = true WHERE email = '$TEST_EMAIL';" -ForegroundColor Cyan
Read-Host "Press Enter after running this in PostgreSQL"

# TEST 3: Login
Write-Host "`nTesting: Login" -ForegroundColor White
try {
    $body = @{ email = $TEST_EMAIL; password = $TEST_PASSWORD } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $body -ContentType "application/json"
    $TOKEN = $response.access_token
    Write-Host "PASS - Got token" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "FAIL" -ForegroundColor Red
    $failed++
}

$headers = @{ "Authorization" = "Bearer $TOKEN"; "Content-Type" = "application/json" }

# TEST 4: Get Surahs
Write-Host "`nTesting: Get Surahs" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/surahs" -Method Get
    Write-Host "PASS - Got $($response.Count) surahs" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "FAIL" -ForegroundColor Red
    $failed++
}

# TEST 5: Progress
Write-Host "`nTesting: Get Progress" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/progress/my-progress" -Method Get -Headers $headers
    Write-Host "PASS - Accuracy: $($response.accuracy.average)%" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "FAIL" -ForegroundColor Red
    $failed++
}

# TEST 6: Log Activity
Write-Host "`nTesting: Log Activity" -ForegroundColor White
try {
    $body = @{ activity_type = "recitation"; surah_number = 1; ayah_number = 1; duration_seconds = 60; accuracy_score = 95.5 } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/progress/log-activity" -Method Post -Headers $headers -Body $body
    Write-Host "PASS" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "FAIL" -ForegroundColor Red
    $failed++
}

# TEST 7: Leaderboard
Write-Host "`nTesting: Leaderboard" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard" -Method Get -Headers $headers
    Write-Host "PASS" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "FAIL" -ForegroundColor Red
    $failed++
}

# TEST 8: Settings
Write-Host "`nTesting: Get Settings" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/user/settings" -Method Get -Headers $headers
    Write-Host "PASS" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "FAIL" -ForegroundColor Red
    $failed++
}

# TEST 9: Subscription
Write-Host "`nTesting: Get Plans" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/payment/plans" -Method Get
    Write-Host "PASS - $($response.plans.Count) plans" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "FAIL" -ForegroundColor Red
    $failed++
}

# TEST 10: Auth Check
Write-Host "`nTesting: Auth Required" -ForegroundColor White
try {
    Invoke-RestMethod -Uri "$BASE_URL/progress/my-progress" -Method Get
    Write-Host "FAIL - Should require auth" -ForegroundColor Red
    $failed++
} catch {
    Write-Host "PASS - Correctly blocks" -ForegroundColor Green
    $passed++
}

# SUMMARY
Write-Host "`n=== RESULTS ===" -ForegroundColor Cyan
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor Red

if ($failed -eq 0) {
    Write-Host "`nALL TESTS PASSED - PRODUCTION READY!" -ForegroundColor Green
} else {
    Write-Host "`nFIX FAILURES BEFORE DEPLOYING" -ForegroundColor Red
}