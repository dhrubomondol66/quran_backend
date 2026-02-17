# COMPLETE NOTIFICATION TEST - WORKING VERSION
$BASE_URL = "http://localhost:8000"

Write-Host "`n=== NOTIFICATION TESTING ===" -ForegroundColor Cyan

# Create users with proper names
$users = @(
    @{ email = "ahmed_test_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Ahmed"; last_name = "TestUser" },
    @{ email = "fatima_test_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Fatima"; last_name = "TestUser" },
    @{ email = "omar_test_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Omar"; last_name = "TestUser" }
)

Write-Host "`n--- Creating Users ---" -ForegroundColor Yellow
foreach ($user in $users) {
    $body = @{
        email = $user.email
        password = $user.password
        first_name = $user.first_name
        last_name = $user.last_name
    } | ConvertTo-Json
    
    Invoke-RestMethod -Uri "$BASE_URL/auth/register" -Method Post -Body $body -ContentType "application/json" | Out-Null
    Write-Host "Created: $($user.first_name)" -ForegroundColor Green
}

Write-Host "`n!!! RUN THIS SQL NOW !!!" -ForegroundColor Red
Write-Host "UPDATE users SET is_email_verified = true WHERE email LIKE '%@test.com';" -ForegroundColor Cyan
Read-Host "`nPress Enter after running SQL"

# Login all users
Write-Host "`n--- Logging In ---" -ForegroundColor Yellow
$tokens = @()
foreach ($user in $users) {
    $loginBody = @{ email = $user.email; password = $user.password } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
    $tokens += $response.access_token
    Write-Host "Logged in: $($user.first_name)" -ForegroundColor Green
}

$token1 = $tokens[0]
$token2 = $tokens[1]
$token3 = $tokens[2]

# TEST 1: Create Community
Write-Host "`n━━━ TEST 1: Community Created ━━━" -ForegroundColor Yellow

$commBody = @{
    name = "Test Notifications $(Get-Random)"
    description = "Testing"
    is_private = $false
    max_members = 50
} | ConvertTo-Json

$community = Invoke-RestMethod -Uri "$BASE_URL/community/communities" -Method Post -Headers @{
    "Authorization" = "Bearer $token1"
    "Content-Type" = "application/json"
} -Body $commBody

Write-Host "Community: $($community.name)" -ForegroundColor Cyan
Start-Sleep -Seconds 1

$notifs = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $token2" }
if ($notifs.Count -gt 0 -and $notifs[0].type -eq "community_created") {
    Write-Host "✅ PASS - Fatima got notification" -ForegroundColor Green
} else {
    Write-Host "❌ FAIL" -ForegroundColor Red
}

# TEST 2: Invite & Accept
Write-Host "`n━━━ TEST 2: Invite Accepted ━━━" -ForegroundColor Yellow

$inviteBody = @{
    first_name = "Fatima"
    last_name = "TestUser"
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/invite" -Method Post -Headers @{
        "Authorization" = "Bearer $token1"
        "Content-Type" = "application/json"
    } -Body $inviteBody | Out-Null
    
    Write-Host "Invitation sent" -ForegroundColor Cyan
    
    # Accept
    $pending = Invoke-RestMethod -Uri "$BASE_URL/community/invitations/pending" -Headers @{ "Authorization" = "Bearer $token2" }
    
    if ($pending.Count -gt 0) {
        Invoke-RestMethod -Uri "$BASE_URL/community/invitations/$($pending[0].id)/accept" -Method Post -Headers @{
            "Authorization" = "Bearer $token2"
        } | Out-Null
        
        Start-Sleep -Seconds 1
        
        $notifs1 = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $token1" }
        $accepted = $notifs1 | Where-Object { $_.type -eq "invite_accepted" }
        
        if ($accepted) {
            Write-Host "✅ PASS - Ahmed got accept notification" -ForegroundColor Green
            Write-Host "   $($accepted.message)" -ForegroundColor White
        } else {
            Write-Host "❌ FAIL - No notification" -ForegroundColor Red
        }
    } else {
        Write-Host "❌ FAIL - No pending invites" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ FAIL - $($_.Exception.Message)" -ForegroundColor Red
}

# TEST 3: Invite & Decline  
Write-Host "`n━━━ TEST 3: Invite Declined ━━━" -ForegroundColor Yellow

$inviteBody3 = @{
    first_name = "Omar"
    last_name = "TestUser"
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/invite" -Method Post -Headers @{
        "Authorization" = "Bearer $token1"
        "Content-Type" = "application/json"
    } -Body $inviteBody3 | Out-Null
    
    # Decline
    $pending3 = Invoke-RestMethod -Uri "$BASE_URL/community/invitations/pending" -Headers @{ "Authorization" = "Bearer $token3" }
    
    if ($pending3.Count -gt 0) {
        Invoke-RestMethod -Uri "$BASE_URL/community/invitations/$($pending3[0].id)/decline" -Method Post -Headers @{
            "Authorization" = "Bearer $token3"
        } | Out-Null
        
        Start-Sleep -Seconds 1
        
        $notifs1 = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $token1" }
        $declined = $notifs1 | Where-Object { $_.type -eq "invite_declined" }
        
        if ($declined) {
            Write-Host "✅ PASS - Ahmed got decline notification" -ForegroundColor Green
            Write-Host "   $($declined.message)" -ForegroundColor White
        } else {
            Write-Host "❌ FAIL - No notification" -ForegroundColor Red
        }
    }
} catch {
    Write-Host "❌ FAIL - $($_.Exception.Message)" -ForegroundColor Red
}

# TEST 4: Join Request
Write-Host "`n━━━ TEST 4: Join Request ━━━" -ForegroundColor Yellow

Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/join-request" -Method Post -Headers @{
    "Authorization" = "Bearer $token3"
} | Out-Null

Start-Sleep -Seconds 1

$notifs1 = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $token1" }
$joinReq = $notifs1 | Where-Object { $_.type -eq "join_request" }

if ($joinReq) {
    Write-Host "✅ PASS - Ahmed got join request" -ForegroundColor Green
    Write-Host "   $($joinReq.message)" -ForegroundColor White
} else {
    Write-Host "❌ FAIL" -ForegroundColor Red
}

# Summary
Write-Host "`n=== RESULTS ===" -ForegroundColor Cyan
$count = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications/unread-count" -Headers @{ "Authorization" = "Bearer $token1" }
Write-Host "Ahmed's unread: $($count.unread_count)" -ForegroundColor White

Write-Host "`nCleanup:" -ForegroundColor Yellow
Write-Host "DELETE FROM users WHERE email LIKE '%@test.com';" -ForegroundColor White
Write-Host ""