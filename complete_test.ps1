Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "        QURAN APP - COMPLETE FEATURE TEST SUITE             " -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

$BASE_URL = "http://127.0.0.1:8000"
$testsPassed = 0
$testsFailed = 0

function Test-Endpoint {
    param(
        [string]$TestName,
        [scriptblock]$TestCode
    )
    
    Write-Host "`n------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "TEST: $TestName" -ForegroundColor Yellow
    Write-Host "------------------------------------------------------------`n" -ForegroundColor Yellow
    
    try {
        & $TestCode
        Write-Host "`nPASSED: $TestName`n" -ForegroundColor Green
        $script:testsPassed++
    }
    catch {
        Write-Host "`nFAILED: $TestName" -ForegroundColor Red
        Write-Host "Error: $_`n" -ForegroundColor Red
        $script:testsFailed++
    }
}

# ============================================================================
# TEST 1: User Registration and Login
# ============================================================================
Test-Endpoint "1. User Registration and Login" {
    Write-Host "Registering new user..."
    
    $email = "testuser_$(Get-Random)@example.com"
    $password = "SecurePass123!"
    
    $registerBody = @{
        email = $email
        password = $password
    } | ConvertTo-Json
    
    $registerResponse = Invoke-RestMethod `
        -Uri "$BASE_URL/auth/register" `
        -Method POST `
        -ContentType "application/json" `
        -Body $registerBody
    
    Write-Host "User registered: $($registerResponse.email)"
    
    Write-Host "`nLogging in..."
    
    $loginBody = @{
        email = $email
        password = $password
    } | ConvertTo-Json
    
    $loginResponse = Invoke-RestMethod `
        -Uri "$BASE_URL/auth/login" `
        -Method POST `
        -ContentType "application/json" `
        -Body $loginBody
    
    $script:token = $loginResponse.access_token
    $script:userEmail = $email
    
    Write-Host "Token received: $($token.Substring(0, 30))..."
    
    if (-not $token) {
        throw "Failed to get access token"
    }
}

# ============================================================================
# TEST 2: Profile Management
# ============================================================================
Test-Endpoint "2. Update User Profile" {
    Write-Host "Updating profile..."
    
    $profileUpdate = @{
        first_name = "Ahmed"
        last_name = "Rahman"
    } | ConvertTo-Json
    
    $updateResult = Invoke-RestMethod `
        -Uri "$BASE_URL/user/profile" `
        -Method PUT `
        -Headers @{Authorization = "Bearer $token"} `
        -ContentType "application/json" `
        -Body $profileUpdate
    
    Write-Host "Profile updated: $($updateResult.message)"
    
    Write-Host "`nGetting profile..."
    $profile = Invoke-RestMethod `
        -Uri "$BASE_URL/user/profile" `
        -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "Name: $($profile.first_name) $($profile.last_name)"
    Write-Host "Email: $($profile.email)"
    Write-Host "Subscription: $($profile.subscription_status)"
    
    if ($profile.first_name -ne "Ahmed") {
        throw "Profile not updated correctly"
    }
}

# ============================================================================
# TEST 3: Initial Progress State
# ============================================================================
Test-Endpoint "3. Check Initial Progress" {
    Write-Host "Fetching initial progress..."
    
    $progress = Invoke-RestMethod `
        -Uri "$BASE_URL/progress/my-progress" `
        -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "Surahs Read: $($progress.surahs_read)/$($progress.total_surahs)"
    Write-Host "Current Streak: $($progress.current_streak) days"
    Write-Host "Time Spent: $($progress.time_spent.total_display)"
    Write-Host "Average Accuracy: $($progress.accuracy.average)%"
    Write-Host "Total Recitations: $($progress.accuracy.total_recitations)"
}

# ============================================================================
# TEST 4: Log Recitation Activities
# ============================================================================
Test-Endpoint "4. Log Recitation Activities with Accuracy" {
    Write-Host "Logging recitations with different accuracy levels...`n"
    
    $recitations = @(
        @{ayah = 1; accuracy = 92.5; surah = 1},
        @{ayah = 2; accuracy = 88.0; surah = 1},
        @{ayah = 3; accuracy = 95.5; surah = 1},
        @{ayah = 4; accuracy = 97.0; surah = 1},
        @{ayah = 5; accuracy = 91.5; surah = 1},
        @{ayah = 6; accuracy = 100.0; surah = 1},
        @{ayah = 7; accuracy = 93.0; surah = 1}
    )
    
    $totalAccuracy = 0
    
    foreach ($rec in $recitations) {
        $recitationBody = @{
            activity_type = "recitation"
            surah_number = $rec.surah
            ayah_number = $rec.ayah
            duration_seconds = 60
            accuracy_score = $rec.accuracy
        } | ConvertTo-Json
        
        $result = Invoke-RestMethod `
            -Uri "$BASE_URL/progress/log-activity" `
            -Method POST `
            -Headers @{Authorization = "Bearer $token"} `
            -ContentType "application/json" `
            -Body $recitationBody
        
        Write-Host "Ayah $($rec.ayah): $($rec.accuracy)% accuracy, Running avg: $($result.average_accuracy)%"
        $totalAccuracy += $rec.accuracy
    }
    
    $expectedAvg = [math]::Round($totalAccuracy / $recitations.Count, 1)
    Write-Host "`nExpected Average: $expectedAvg%"
    Write-Host "Recitations Logged: $($recitations.Count)"
}

# ============================================================================
# TEST 5: Log Listening Time
# ============================================================================
Test-Endpoint "5. Log Listening Time for Daily Tracking" {
    Write-Host "Logging listening activities...`n"
    
    $listeningActivities = @(
        @{surah = 2; duration = 600},
        @{surah = 3; duration = 900},
        @{surah = 36; duration = 1200}
    )
    
    $totalMinutes = 0
    
    foreach ($activity in $listeningActivities) {
        $listeningBody = @{
            activity_type = "listening"
            surah_number = $activity.surah
            duration_seconds = $activity.duration
        } | ConvertTo-Json
        
        $result = Invoke-RestMethod `
            -Uri "$BASE_URL/progress/log-activity" `
            -Method POST `
            -Headers @{Authorization = "Bearer $token"} `
            -ContentType "application/json" `
            -Body $listeningBody
        
        $minutes = $activity.duration / 60
        $totalMinutes += $minutes
        Write-Host "Surah $($activity.surah): $minutes minutes"
    }
    
    Write-Host "`nTotal Listening Time: $totalMinutes minutes"
}

# ============================================================================
# TEST 6: Check Updated Progress
# ============================================================================
Test-Endpoint "6. Verify Progress Updates" {
    Write-Host "Checking updated progress...`n"
    
    $progress = Invoke-RestMethod `
        -Uri "$BASE_URL/progress/my-progress" `
        -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "OVERALL STATS:"
    Write-Host "Surahs Read: $($progress.surahs_read)/114"
    Write-Host "Time Spent: $($progress.time_spent.total_display)"
    Write-Host "Current Streak: $($progress.current_streak) day(s)"
    
    Write-Host "`nACCURACY STATS:"
    $accuracyColor = if ($progress.accuracy.average -ge 90) { "Green" } else { "Yellow" }
    Write-Host "Average Accuracy: $($progress.accuracy.average)%" -ForegroundColor $accuracyColor
    Write-Host "Total Recitations: $($progress.accuracy.total_recitations)"
    Write-Host "Correct Recitations: $($progress.accuracy.correct_recitations)"
    
    Write-Host "`nWEEKLY ACTIVITY (Minutes per Day):"
    $progress.weekly_activity.data | Format-Table
    Write-Host "Total This Week: $($progress.weekly_activity.total_time)"
    
    if ($progress.recent_achievements.Count -gt 0) {
        Write-Host "`nRECENT ACHIEVEMENTS:"
        foreach ($achievement in $progress.recent_achievements) {
            $newBadge = if ($achievement.is_new) { " [NEW!]" } else { "" }
            Write-Host "$($achievement.icon) $($achievement.name)$newBadge"
        }
    }
    
    if ($progress.accuracy.total_recitations -lt 7) {
        throw "Expected 7 recitations, got $($progress.accuracy.total_recitations)"
    }
}

# ============================================================================
# TEST 7: Settings Management
# ============================================================================
Test-Endpoint "7. Get and Update Settings" {
    Write-Host "Getting current settings..."
    
    $settings = Invoke-RestMethod `
        -Uri "$BASE_URL/user/settings" `
        -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "Theme: $($settings.app_settings.theme)"
    Write-Host "Text Size: $($settings.reading_preferences.text_size)"
    Write-Host "Playback Speed: $($settings.audio_settings.playback_speed)x"
    
    Write-Host "`nUpdating settings..."
    
    $settingsUpdate = @{
        theme = "dark"
        text_size = "large"
        playback_speed = 1.25
        show_on_leaderboard = $true
    } | ConvertTo-Json
    
    $updateResult = Invoke-RestMethod `
        -Uri "$BASE_URL/user/settings" `
        -Method PUT `
        -Headers @{Authorization = "Bearer $token"} `
        -ContentType "application/json" `
        -Body $settingsUpdate
    
    Write-Host "$($updateResult.message)"
    
    Write-Host "`nVerifying updates..."
    $updatedSettings = Invoke-RestMethod `
        -Uri "$BASE_URL/user/settings" `
        -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "New Theme: $($updatedSettings.app_settings.theme)"
    Write-Host "New Text Size: $($updatedSettings.reading_preferences.text_size)"
    Write-Host "New Playback Speed: $($updatedSettings.audio_settings.playback_speed)x"
    
    if ($updatedSettings.app_settings.theme -ne "dark") {
        throw "Settings not updated correctly"
    }
}

# ============================================================================
# TEST 8: Leaderboard
# ============================================================================
Test-Endpoint "8. Check Leaderboard Rankings" {
    Write-Host "Fetching leaderboard...`n"
    
    # Use separate variables to avoid parsing issues
    $period = "all_time"
    $limitValue = 10
    $leaderboardUrl = "$BASE_URL/leaderboard/leaderboard?period=$period&limit=$limitValue"
    
    $leaderboard = Invoke-RestMethod `
        -Uri $leaderboardUrl `
        -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "LEADERBOARD INFO:"
    Write-Host "Ranking Criteria: $($leaderboard.ranking_criteria)"
    Write-Host "Total Participants: $($leaderboard.total_participants)"
    
    Write-Host "`nYOUR RANK:"
    if ($leaderboard.current_user.rank) {
        Write-Host "Rank: #$($leaderboard.current_user.rank)" -ForegroundColor Cyan
        Write-Host "Accuracy: $($leaderboard.current_user.accuracy)%"
        Write-Host "Recitations: $($leaderboard.current_user.total_recitations)"
        Write-Host "Time Spent: $($leaderboard.current_user.time_spent_hours)h"
    } else {
        Write-Host "$($leaderboard.current_user.message)" -ForegroundColor Yellow
        Write-Host "Current Accuracy: $($leaderboard.current_user.accuracy)%"
        Write-Host "Current Recitations: $($leaderboard.current_user.total_recitations)"
    }
    
    if ($leaderboard.top_3.Count -gt 0) {
        Write-Host "`nTOP 3 USERS:"
        $leaderboard.top_3 | Format-Table -Property rank, name, accuracy, total_recitations, time_spent_hours
    }
}

# ============================================================================
# TEST 9: Recitation API
# ============================================================================
Test-Endpoint "9. Get Complete Surah Recitation" {
    Write-Host "Fetching Al-Fatiha recitation...`n"
    
    $recitationUrl = "$BASE_URL/recitation/surah/1/complete-recitation?reciter=ar.alafasy"
    
    $recitation = Invoke-RestMethod `
        -Uri $recitationUrl `
        -Method GET `
        -Headers @{Authorization = "Bearer $token"}
    
    Write-Host "SURAH INFO:"
    Write-Host "Surah: $($recitation.surah.name_english) - $($recitation.surah.translation)"
    Write-Host "Number: $($recitation.surah.number)"
    Write-Host "Ayahs: $($recitation.surah.number_of_ayahs)"
    Write-Host "Revelation: $($recitation.surah.revelation_type)"
    
    Write-Host "`nRECITER INFO:"
    Write-Host "Name: $($recitation.reciter.name)"
    Write-Host "Style: $($recitation.reciter.style)"
    
    Write-Host "`nAUDIO INFO:"
    Write-Host "Total Tracks: $($recitation.audio.total_tracks)"
    Write-Host "First Audio URL: $($recitation.audio.playlist[0].url)"
    
    if ($recitation.audio.total_tracks -ne 7) {
        throw "Expected 7 audio tracks for Al-Fatiha"
    }
}

# ============================================================================
# TEST 10: Payment Plans
# ============================================================================
Test-Endpoint "10. Check Payment Plans" {
    Write-Host "Fetching payment plans...`n"
    
    $plans = Invoke-RestMethod `
        -Uri "$BASE_URL/payment/plans" `
        -Method GET
    
    Write-Host "AVAILABLE PLANS:"
    foreach ($plan in $plans.plans) {
        Write-Host "`n$($plan.name)"
        Write-Host "Price: `$$($plan.price)/$($plan.interval)"
        Write-Host "Description: $($plan.description)"
        if ($plan.savings) {
            Write-Host "Savings: `$$($plan.savings) per year!" -ForegroundColor Green
        }
    }
}

# ============================================================================
# SUMMARY
# ============================================================================
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "                    TEST SUMMARY                            " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Total Tests Run: $($testsPassed + $testsFailed)" -ForegroundColor White
Write-Host "Tests Passed: $testsPassed" -ForegroundColor Green

$failColor = if ($testsFailed -eq 0) { "Green" } else { "Red" }
Write-Host "Tests Failed: $testsFailed" -ForegroundColor $failColor
Write-Host ""

if ($testsFailed -eq 0) {
    Write-Host "ALL TESTS PASSED! Your API is working perfectly!" -ForegroundColor Green
} else {
    Write-Host "Some tests failed. Please review the errors above." -ForegroundColor Yellow
}

Write-Host ""