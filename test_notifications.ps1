# COMPLETE NOTIFICATION TEST - ALL 6 TYPES
$BASE_URL = "http://localhost:8000"

Write-Host "`n=== COMPLETE NOTIFICATION TEST ===" -ForegroundColor Cyan

# Create users
$users = @(
    @{ email = "creator_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Creator"; last_name = "User" },
    @{ email = "joiner_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Joiner"; last_name = "User" },
    @{ email = "requester_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Requester"; last_name = "User" }
)

Write-Host "`nCreating users..." -ForegroundColor Yellow
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

Write-Host "`nRUN THIS SQL:" -ForegroundColor Red
Write-Host "UPDATE users SET is_email_verified = true WHERE email LIKE '%@test.com';" -ForegroundColor White
Read-Host "`nPress Enter after SQL"

# Login
Write-Host "`nLogging in..." -ForegroundColor Yellow
$tokens = @()
foreach ($user in $users) {
    $loginBody = @{ email = $user.email; password = $user.password } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
    $tokens += $response.access_token
}

$creatorToken = $tokens[0]
$joinerToken = $tokens[1]
$requesterToken = $tokens[2]

Write-Host "All logged in`n" -ForegroundColor Green

# TEST 1: Community Created
Write-Host "--- TEST 1: Community Created ---" -ForegroundColor Yellow

$commBody = @{
    name = "Test $(Get-Random)"
    description = "Test"
    is_private = $false
    max_members = 50
} | ConvertTo-Json

$community = Invoke-RestMethod -Uri "$BASE_URL/community/communities" -Method Post -Headers @{
    "Authorization" = "Bearer $creatorToken"
    "Content-Type" = "application/json"
} -Body $commBody

Start-Sleep -Seconds 1

$joinerNotifs = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $joinerToken" }
if ($joinerNotifs[0].type -eq "community_created") {
    Write-Host "PASS - Community created notification" -ForegroundColor Green
} else {
    Write-Host "FAIL" -ForegroundColor Red
}

# TEST 2: Invite Accepted
Write-Host "`n--- TEST 2: Invite Accepted ---" -ForegroundColor Yellow

$inviteBody = @{ first_name = "Joiner"; last_name = "User" } | ConvertTo-Json
Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/invite" -Method Post -Headers @{
    "Authorization" = "Bearer $creatorToken"
    "Content-Type" = "application/json"
} -Body $inviteBody | Out-Null

$pending = Invoke-RestMethod -Uri "$BASE_URL/community/invitations/pending" -Headers @{ "Authorization" = "Bearer $joinerToken" }
Invoke-RestMethod -Uri "$BASE_URL/community/invitations/$($pending[0].id)/accept" -Method Post -Headers @{ "Authorization" = "Bearer $joinerToken" } | Out-Null

Start-Sleep -Seconds 1

$creatorNotifs = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $creatorToken" }
$accepted = $creatorNotifs | Where-Object { $_.type -eq "invite_accepted" }
if ($accepted) {
    Write-Host "PASS - Invite accepted notification" -ForegroundColor Green
} else {
    Write-Host "FAIL" -ForegroundColor Red
}

# TEST 3: Invite Declined
Write-Host "`n--- TEST 3: Invite Declined ---" -ForegroundColor Yellow

$inviteBody2 = @{ first_name = "Requester"; last_name = "User" } | ConvertTo-Json
Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/invite" -Method Post -Headers @{
    "Authorization" = "Bearer $creatorToken"
    "Content-Type" = "application/json"
} -Body $inviteBody2 | Out-Null

$pending2 = Invoke-RestMethod -Uri "$BASE_URL/community/invitations/pending" -Headers @{ "Authorization" = "Bearer $requesterToken" }
Invoke-RestMethod -Uri "$BASE_URL/community/invitations/$($pending2[0].id)/decline" -Method Post -Headers @{ "Authorization" = "Bearer $requesterToken" } | Out-Null

Start-Sleep -Seconds 1

$creatorNotifs = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $creatorToken" }
$declined = $creatorNotifs | Where-Object { $_.type -eq "invite_declined" }
if ($declined) {
    Write-Host "PASS - Invite declined notification" -ForegroundColor Green
} else {
    Write-Host "FAIL" -ForegroundColor Red
}

# TEST 4: Join Request
Write-Host "`n--- TEST 4: Join Request ---" -ForegroundColor Yellow

Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/join-request" -Method Post -Headers @{ "Authorization" = "Bearer $requesterToken" } | Out-Null

Start-Sleep -Seconds 1

$creatorNotifs = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $creatorToken" }
$joinReq = $creatorNotifs | Where-Object { $_.type -eq "join_request" }
if ($joinReq) {
    Write-Host "PASS - Join request notification" -ForegroundColor Green
} else {
    Write-Host "FAIL" -ForegroundColor Red
}

# TEST 5: Join Request Approved
Write-Host "`n--- TEST 5: Join Request Approved ---" -ForegroundColor Yellow

$joinRequests = Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/join-requests" -Headers @{ "Authorization" = "Bearer $creatorToken" }

if ($joinRequests.Count -gt 0) {
    Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/join-requests/$($joinRequests[0].id)/approve" -Method Post -Headers @{ "Authorization" = "Bearer $creatorToken" } | Out-Null
    
    Start-Sleep -Seconds 1
    
    $requesterNotifs = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $requesterToken" }
    $approved = $requesterNotifs | Where-Object { $_.type -eq "community_joined" }
    if ($approved) {
        Write-Host "PASS - Join approved notification" -ForegroundColor Green
    } else {
        Write-Host "FAIL" -ForegroundColor Red
    }
}

# TEST 6: Join Request Rejected
Write-Host "`n--- TEST 6: Join Request Rejected ---" -ForegroundColor Yellow

$rejectUser = @{
    email = "reject_$(Get-Random)@test.com"
    password = "Test123!"
    first_name = "Reject"
    last_name = "User"
}

$regBody = @{
    email = $rejectUser.email
    password = $rejectUser.password
    first_name = $rejectUser.first_name
    last_name = $rejectUser.last_name
} | ConvertTo-Json

Invoke-RestMethod -Uri "$BASE_URL/auth/register" -Method Post -Body $regBody -ContentType "application/json" | Out-Null

Write-Host "`nRUN THIS SQL AGAIN:" -ForegroundColor Red
Write-Host "UPDATE users SET is_email_verified = true WHERE email LIKE '%reject_%@test.com';" -ForegroundColor White
Read-Host "Press Enter after SQL"

$rejectLogin = @{ email = $rejectUser.email; password = $rejectUser.password } | ConvertTo-Json
$rejectResponse = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $rejectLogin -ContentType "application/json"
$rejectToken = $rejectResponse.access_token

Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/join-request" -Method Post -Headers @{ "Authorization" = "Bearer $rejectToken" } | Out-Null

Start-Sleep -Seconds 1

$joinRequests2 = Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/join-requests" -Headers @{ "Authorization" = "Bearer $creatorToken" }

if ($joinRequests2.Count -gt 0) {
    Invoke-RestMethod -Uri "$BASE_URL/community/communities/$($community.id)/join-requests/$($joinRequests2[0].id)/reject" -Method Post -Headers @{ "Authorization" = "Bearer $creatorToken" } | Out-Null
    
    Start-Sleep -Seconds 1
    
    $rejectNotifs = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $rejectToken" }
    $rejected = $rejectNotifs | Where-Object { $_.type -eq "removed_from_community" }
    if ($rejected) {
        Write-Host "PASS - Join rejected notification" -ForegroundColor Green
    } else {
        Write-Host "FAIL" -ForegroundColor Red
    }
}

Write-Host "`n=== ALL 6 TESTS COMPLETE ===" -ForegroundColor Cyan
Write-Host "`nCleanup:" -ForegroundColor Yellow
Write-Host "DELETE FROM users WHERE email LIKE '%@test.com';" -ForegroundColor White
Write-Host ""