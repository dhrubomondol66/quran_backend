# COMMUNITY LEADERBOARD TEST
$BASE_URL = "http://localhost:8000"

Write-Host "=== COMMUNITY LEADERBOARD TEST ===" -ForegroundColor Cyan

# Login as creator (user 1)
$email = Read-Host "Creator email"
$password = Read-Host "Creator password" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

$loginBody = @{ email = $email; password = $passwordPlain } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$creatorToken = $r.access_token
Write-Host "Logged in as creator" -ForegroundColor Green

# Create community
Write-Host "`nCreating community..." -ForegroundColor Yellow
$commBody = @{
    name = "Leaderboard Test Community"
    description = "Testing community leaderboard"
    is_private = $false
    max_members = 50
} | ConvertTo-Json

$community = Invoke-RestMethod -Uri "$BASE_URL/community/communities" -Method Post -Headers @{
    "Authorization" = "Bearer $creatorToken"
    "Content-Type" = "application/json"
} -Body $commBody

$communityId = $community.id
Write-Host "Community created: $($community.name) (ID: $communityId)" -ForegroundColor Green

# Use the 10 leaderboard test users already in DB
$leaderboardEmails = @(
    "aisha_511012@leaderboard.com",
    "bilal_37868@leaderboard.com",
    "fatima_931334@leaderboard.com",
    "omar_835366@leaderboard.com",
    "zainab_159082@leaderboard.com",
    "yusuf_999681@leaderboard.com",
    "maryam_824468@leaderboard.com",
    "ibrahim_766670@leaderboard.com",
    "khadija_220955@leaderboard.com",
    "tariq_761781@leaderboard.com"
)

Write-Host "`nNote: Update emails above if your leaderboard test user emails are different" -ForegroundColor Yellow
Write-Host "Check with: SELECT email FROM users WHERE email LIKE '%@leaderboard.com';" -ForegroundColor Gray

# Login each user and join community
Write-Host "`nAdding 10 users to community..." -ForegroundColor Yellow

$memberTokens = @()
foreach ($memberEmail in $leaderboardEmails) {
    try {
        $loginB = @{ email = $memberEmail; password = "Test123!" } | ConvertTo-Json
        $resp = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginB -ContentType "application/json"
        $memberToken = $resp.access_token
        $memberTokens += $memberToken

        # Send join request
        Invoke-RestMethod -Uri "$BASE_URL/community/communities/$communityId/join-request" -Method Post -Headers @{
            "Authorization" = "Bearer $memberToken"
        } | Out-Null

        Write-Host "  $memberEmail - join request sent" -ForegroundColor Green
    } catch {
        Write-Host "  SKIP $memberEmail - $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# Approve all join requests
Write-Host "`nApproving all join requests..." -ForegroundColor Yellow

$joinRequests = Invoke-RestMethod -Uri "$BASE_URL/community/communities/$communityId/join-requests" -Headers @{
    "Authorization" = "Bearer $creatorToken"
}

Write-Host "Pending requests: $($joinRequests.Count)" -ForegroundColor White

foreach ($req in $joinRequests) {
    try {
        Invoke-RestMethod -Uri "$BASE_URL/community/communities/$communityId/join-requests/$($req.id)/approve" -Method Post -Headers @{
            "Authorization" = "Bearer $creatorToken"
        } | Out-Null
        Write-Host "  Approved: $($req.requester_name)" -ForegroundColor Green
    } catch {
        Write-Host "  SKIP: $($req.requester_name) - $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# Check member count
$members = Invoke-RestMethod -Uri "$BASE_URL/community/communities/$communityId/members" -Headers @{
    "Authorization" = "Bearer $creatorToken"
}
Write-Host "`nTotal members in community: $($members.Count)" -ForegroundColor White

# Test leaderboard
Write-Host "`n--- Community Leaderboard ---" -ForegroundColor Yellow

$lb = Invoke-RestMethod -Uri "$BASE_URL/community/communities/$communityId/leaderboard" -Headers @{
    "Authorization" = "Bearer $creatorToken"
}

Write-Host "Community: $($lb.community_name)" -ForegroundColor White
Write-Host "Total members: $($lb.total_members)" -ForegroundColor White
Write-Host "Participants on leaderboard: $($lb.total_participants)" -ForegroundColor White
Write-Host "Scoring: $($lb.scoring)" -ForegroundColor White

Write-Host "`nTop 3:" -ForegroundColor Yellow
foreach ($u in $lb.top_3) {
    Write-Host "  #$($u.rank) $($u.name) | Score: $($u.score) | Acc: $($u.accuracy)% | Rec: $($u.total_recitations)" -ForegroundColor Green
}

Write-Host "`nFull Rankings:" -ForegroundColor Yellow
foreach ($u in $lb.rankings) {
    $you = if ($u.is_you) { " <- YOU" } else { "" }
    Write-Host "  #$($u.rank) $($u.name) | Score: $($u.score) | Acc: $($u.accuracy)% | Rec: $($u.total_recitations)$you" -ForegroundColor White
}

Write-Host "`nYour rank: #$($lb.current_user.rank)" -ForegroundColor Cyan

Write-Host "`n=== TEST COMPLETE ===" -ForegroundColor Cyan
Write-Host "`nCommunity ID for future tests: $communityId" -ForegroundColor Yellow
Write-Host "`nCleanup:" -ForegroundColor Yellow
Write-Host "DELETE FROM communities WHERE name = 'Leaderboard Test Community';" -ForegroundColor White
Write-Host ""
