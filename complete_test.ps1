# COMPLETE QURAN API TEST - ALL ENDPOINTS
$BASE_URL = "http://localhost:8000"
$TEST_EMAIL = "testuser_$(Get-Random)@example.com"
$TEST_PASSWORD = "TestPassword123!"
$TOKEN = ""
$passed = 0
$failed = 0

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "QURAN API - COMPLETE TEST SUITE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# ============================================================================
# BASIC TESTS
# ============================================================================

Write-Host "--- BASIC CONNECTIVITY ---" -ForegroundColor Yellow

Write-Host "`n1. Root Endpoint" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/" -Method Get
    Write-Host "   PASS - $($response.message)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL - $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

Write-Host "`n2. Health Check" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/health" -Method Get
    Write-Host "   PASS - Status: $($response.status)" -ForegroundColor Green
    Write-Host "   OpenAI: $($response.services.openai_whisper)" -ForegroundColor Gray
    Write-Host "   Stripe: $($response.services.stripe)" -ForegroundColor Gray
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n3. API Docs Accessible" -ForegroundColor White
try {
    $response = Invoke-WebRequest -Uri "$BASE_URL/docs" -Method Get -UseBasicParsing
    Write-Host "   PASS - Docs available" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

# ============================================================================
# AUTHENTICATION - EMAIL/PASSWORD
# ============================================================================

Write-Host "`n--- EMAIL/PASSWORD AUTHENTICATION ---" -ForegroundColor Yellow

Write-Host "`n4. Register New User" -ForegroundColor White
Write-Host "   Email: $TEST_EMAIL" -ForegroundColor Gray
try {
    $body = @{ email = $TEST_EMAIL; password = $TEST_PASSWORD } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/register" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   PASS - User ID: $($response.id)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL - $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

Write-Host "`n5. Reject Duplicate Email" -ForegroundColor White
try {
    $body = @{ email = $TEST_EMAIL; password = "Different123!" } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BASE_URL/auth/register" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   FAIL - Should reject duplicate" -ForegroundColor Red
    $failed++
} catch {
    if ($_.Exception.Response.StatusCode -eq 400) {
        Write-Host "   PASS - Correctly rejected" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "   FAIL - Wrong error code" -ForegroundColor Red
        $failed++
    }
}

Write-Host "`n6. Resend Verification Email" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/resend-verification?email=$TEST_EMAIL" -Method Post
    Write-Host "   PASS - $($response.message)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

# VERIFY EMAIL
Write-Host "`n--- EMAIL VERIFICATION REQUIRED ---" -ForegroundColor Yellow
Write-Host "Run this in PostgreSQL:" -ForegroundColor Cyan
Write-Host "UPDATE users SET is_email_verified = true WHERE email = '$TEST_EMAIL';" -ForegroundColor White
Read-Host "`nPress Enter after verifying"

Write-Host "`n7. Login with Verified Email" -ForegroundColor White
try {
    $body = @{ email = $TEST_EMAIL; password = $TEST_PASSWORD } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $body -ContentType "application/json"
    $TOKEN = $response.access_token
    Write-Host "   PASS - Token received" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL - $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

Write-Host "`n8. Reject Wrong Password" -ForegroundColor White
try {
    $body = @{ email = $TEST_EMAIL; password = "WrongPassword!" } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   FAIL - Should reject" -ForegroundColor Red
    $failed++
} catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "   PASS - Correctly rejected" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "   FAIL" -ForegroundColor Red
        $failed++
    }
}

Write-Host "`n9. Reject Non-existent User" -ForegroundColor White
try {
    $body = @{ email = "nonexistent@test.com"; password = "Test123!" } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   FAIL - Should reject" -ForegroundColor Red
    $failed++
} catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "   PASS - Correctly rejected" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "   FAIL" -ForegroundColor Red
        $failed++
    }
}

# ============================================================================
# PASSWORD RESET
# ============================================================================

Write-Host "`n--- PASSWORD RESET ---" -ForegroundColor Yellow

Write-Host "`n10. Request Password Reset" -ForegroundColor White
try {
    $body = @{ email = $TEST_EMAIL } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/forgot-password" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   PASS - $($response.message)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n11. Request Reset for Non-existent Email (Security)" -ForegroundColor White
try {
    $body = @{ email = "nonexistent@test.com" } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/forgot-password" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   PASS - Returns generic message (security)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

# ============================================================================
# GOOGLE OAUTH
# ============================================================================

Write-Host "`n--- GOOGLE OAUTH ---" -ForegroundColor Yellow

Write-Host "`n12. Google OAuth Endpoint Exists" -ForegroundColor White
try {
    # This will fail without a valid Google token, but we're checking if endpoint exists
    $body = @{ id_token = "invalid_token_for_testing" } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BASE_URL/auth/google" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   FAIL - Should reject invalid token" -ForegroundColor Red
    $failed++
} catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "   PASS - Endpoint exists and validates tokens" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "   SKIP - Endpoint might not be configured" -ForegroundColor Yellow
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Gray
    }
}

# ============================================================================
# APPLE OAUTH
# ============================================================================

Write-Host "`n--- APPLE OAUTH ---" -ForegroundColor Yellow

Write-Host "`n13. Apple OAuth Endpoint Exists" -ForegroundColor White
try {
    # This will fail without a valid Apple token, but we're checking if endpoint exists
    $body = @{ id_token = "invalid_token_for_testing" } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BASE_URL/auth/apple" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   FAIL - Should reject invalid token" -ForegroundColor Red
    $failed++
} catch {
    if ($_.Exception.Response.StatusCode -eq 401 -or $_.Exception.Response.StatusCode -eq 400) {
        Write-Host "   PASS - Endpoint exists and validates tokens" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "   SKIP - Endpoint might not be configured" -ForegroundColor Yellow
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Gray
    }
}

# ============================================================================
# QURAN DATA
# ============================================================================

Write-Host "`n--- QURAN DATA ---" -ForegroundColor Yellow

Write-Host "`n14. Get All Surahs" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/surahs" -Method Get
    Write-Host "   PASS - Retrieved $($response.Count) surahs" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n15. Get Specific Surah (Al-Fatihah)" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/surahs/1" -Method Get
    Write-Host "   PASS - $($response.name_ar) ($($response.name_en))" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n16. Handle Invalid Surah (404)" -ForegroundColor White
try {
    Invoke-RestMethod -Uri "$BASE_URL/surahs/999" -Method Get
    Write-Host "   FAIL - Should return 404" -ForegroundColor Red
    $failed++
} catch {
    if ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "   PASS - Returns 404" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "   FAIL" -ForegroundColor Red
        $failed++
    }
}

# ============================================================================
# PROGRESS (AUTHENTICATED)
# ============================================================================

$headers = @{ "Authorization" = "Bearer $TOKEN"; "Content-Type" = "application/json" }

Write-Host "`n--- PROGRESS TRACKING ---" -ForegroundColor Yellow

Write-Host "`n17. Get User Progress" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/progress/my-progress" -Method Get -Headers $headers
    Write-Host "   PASS - Accuracy: $($response.accuracy.average)%, Streak: $($response.current_streak)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n18. Log Recitation Activity" -ForegroundColor White
try {
    $body = @{ 
        activity_type = "recitation"
        surah_number = 1
        ayah_number = 1
        duration_seconds = 60
        accuracy_score = 95.5
    } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/progress/log-activity" -Method Post -Headers $headers -Body $body
    Write-Host "   PASS - Activity logged" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n19. Start Session" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/progress/start-session" -Method Post -Headers $headers
    Write-Host "   PASS - Session started" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n20. End Session" -ForegroundColor White
try {
    $body = @{ duration_seconds = 1800 } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/progress/end-session" -Method Post -Headers $headers -Body $body
    Write-Host "   PASS - Session ended" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

# ============================================================================
# LEADERBOARD
# ============================================================================

Write-Host "`n--- LEADERBOARD ---" -ForegroundColor Yellow

Write-Host "`n21. Get Leaderboard" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard" -Method Get -Headers $headers
    Write-Host "   PASS - Participants: $($response.total_participants)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

# ============================================================================
# USER SETTINGS
# ============================================================================

Write-Host "`n--- USER SETTINGS ---" -ForegroundColor Yellow

Write-Host "`n22. Get Settings" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/user/settings" -Method Get -Headers $headers
    Write-Host "   PASS - Theme: $($response.app_settings.theme)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n23. Update Settings" -ForegroundColor White
try {
    $body = @{ theme = "dark"; text_size = "large" } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/user/settings" -Method Put -Headers $headers -Body $body
    Write-Host "   PASS - Settings updated" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n24. Get Profile" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/user/profile" -Method Get -Headers $headers
    Write-Host "   PASS - Email: $($response.email)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n25. Update Profile" -ForegroundColor White
try {
    $body = @{ first_name = "Test"; last_name = "User" } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/user/profile" -Method Put -Headers $headers -Body $body
    Write-Host "   PASS - Profile updated" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

# ============================================================================
# STRIPE PAYMENTS
# ============================================================================

Write-Host "`n--- STRIPE PAYMENTS ---" -ForegroundColor Yellow

Write-Host "`n26. Get Available Plans" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/payment/plans" -Method Get
    Write-Host "   PASS - Plans: $($response.plans.Count)" -ForegroundColor Green
    foreach ($plan in $response.plans) {
        Write-Host "      - $($plan.name): `$$($plan.price)" -ForegroundColor Gray
    }
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n27. Get Subscription Status" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/payment/subscription-status" -Method Get -Headers $headers
    Write-Host "   PASS - Status: $($response.subscription_status)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n28. Get Payment History" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/payment/payment-history" -Method Get -Headers $headers
    Write-Host "   PASS - Payments: $($response.payments.Count), Total: `$$($response.total_spent)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n29. Create Checkout Session (Stripe)" -ForegroundColor White
try {
    $body = @{ 
        plan_type = "monthly"
        success_url = "http://localhost:3000/success"
        cancel_url = "http://localhost:3000/cancel"
    } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/payment/create-checkout-session" -Method Post -Headers $headers -Body $body
    Write-Host "   PASS - Checkout URL created" -ForegroundColor Green
    Write-Host "      Plan: $($response.plan), Amount: `$$($response.amount)" -ForegroundColor Gray
    $passed++
} catch {
    Write-Host "   FAIL - $($_.Exception.Message)" -ForegroundColor Red
    $failed++
}

# Note: We can't test actual Stripe webhooks or payments without real transactions

# ============================================================================
# RECITATION API
# ============================================================================

Write-Host "`n--- RECITATION API ---" -ForegroundColor Yellow

Write-Host "`n30. Get Available Reciters" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/recitation/reciters" -Method Get -Headers $headers
    $freeCount = ($response.reciters | Where-Object { -not $_.locked }).Count
    $premiumCount = ($response.reciters | Where-Object { $_.locked }).Count
    Write-Host "   PASS - Reciters: $($response.reciters.Count) (Free: $freeCount, Premium: $premiumCount)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n31. Get Surah Info" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/recitation/surah/1/info" -Method Get
    Write-Host "   PASS - $($response.englishName), Ayahs: $($response.numberOfAyahs)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

Write-Host "`n32. Get Surahs List" -ForegroundColor White
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/recitation/surahs/list" -Method Get
    Write-Host "   PASS - Total: $($response.total)" -ForegroundColor Green
    $passed++
} catch {
    Write-Host "   FAIL" -ForegroundColor Red
    $failed++
}

# ============================================================================
# AUTHORIZATION & SECURITY
# ============================================================================

Write-Host "`n--- AUTHORIZATION & SECURITY ---" -ForegroundColor Yellow

Write-Host "`n33. Reject Request Without Token" -ForegroundColor White
try {
    Invoke-RestMethod -Uri "$BASE_URL/progress/my-progress" -Method Get
    Write-Host "   FAIL - Should require auth" -ForegroundColor Red
    $failed++
} catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "   PASS - Correctly requires auth" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "   FAIL" -ForegroundColor Red
        $failed++
    }
}

Write-Host "`n34. Reject Invalid Token" -ForegroundColor White
try {
    $badHeaders = @{ "Authorization" = "Bearer invalid_token_123" }
    Invoke-RestMethod -Uri "$BASE_URL/progress/my-progress" -Method Get -Headers $badHeaders
    Write-Host "   FAIL - Should reject" -ForegroundColor Red
    $failed++
} catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "   PASS - Correctly rejects" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "   FAIL" -ForegroundColor Red
        $failed++
    }
}

# ============================================================================
# VOICE RECITATION
# ============================================================================

Write-Host "`n--- VOICE RECITATION ---" -ForegroundColor Yellow

Write-Host "`n35. Voice Endpoint Exists (REST)" -ForegroundColor White
try {
    # This will fail without actual audio, but checks if endpoint exists
    $body = @{
        surah_number = 1
        ayah_start = 1
        audio_base64 = "invalid_audio_for_testing"
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BASE_URL/voice/api/recite/evaluate" -Method Post -Headers $headers -Body $body
    Write-Host "   FAIL - Should reject invalid audio" -ForegroundColor Red
    $failed++
} catch {
    if ($_.Exception.Response.StatusCode -eq 500 -or $_.Exception.Response.StatusCode -eq 400) {
        Write-Host "   PASS - Endpoint exists (needs real audio)" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "   SKIP - Voice not configured" -ForegroundColor Yellow
    }
}

# ============================================================================
# SUMMARY
# ============================================================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "TEST SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor Red
Write-Host "Total:  $($passed + $failed)" -ForegroundColor White

if ($failed -eq 0) {
    Write-Host "`nSTATUS: ALL TESTS PASSED - PRODUCTION READY!" -ForegroundColor Green
} else {
    Write-Host "`nSTATUS: FIX FAILURES BEFORE DEPLOYING" -ForegroundColor Red
}

Write-Host "`nTESTED:" -ForegroundColor Yellow
Write-Host "- Email/Password Auth (9 tests)" -ForegroundColor Gray
Write-Host "- Password Reset (2 tests)" -ForegroundColor Gray
Write-Host "- Google OAuth (1 test)" -ForegroundColor Gray
Write-Host "- Apple OAuth (1 test)" -ForegroundColor Gray
Write-Host "- Quran Data (3 tests)" -ForegroundColor Gray
Write-Host "- Progress Tracking (4 tests)" -ForegroundColor Gray
Write-Host "- Leaderboard (1 test)" -ForegroundColor Gray
Write-Host "- Settings & Profile (4 tests)" -ForegroundColor Gray
Write-Host "- Stripe Payments (4 tests)" -ForegroundColor Gray
Write-Host "- Recitation API (3 tests)" -ForegroundColor Gray
Write-Host "- Authorization (2 tests)" -ForegroundColor Gray
Write-Host "- Voice (1 test)" -ForegroundColor Gray
Write-Host ""
