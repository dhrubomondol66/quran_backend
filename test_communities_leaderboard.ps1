# COMMUNITY RANKINGS LEADERBOARD TEST
$BASE_URL = "http://localhost:8000"

Write-Host "=== COMMUNITY RANKINGS LEADERBOARD TEST ===" -ForegroundColor Cyan

# Login
$email = Read-Host "Your email"
$password = Read-Host "Your password" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

$loginBody = @{ email = $email; password = $passwordPlain } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$TOKEN = $r.access_token
Write-Host "Logged in" -ForegroundColor Green

# Step 1: Create 3 test communities with different member mixes
Write-Host "`nCreating 3 test communities..." -ForegroundColor Yellow

$comm1 = Invoke-RestMethod -Uri "$BASE_URL/community/communities" -Method Post -Headers @{
    "Authorization" = "Bearer $TOKEN"
    "Content-Type" = "application/json"
} -Body (@{ name = "Elite Reciters"; description = "Top performers"; is_private = $false; max_members = 50 } | ConvertTo-Json)

$comm2 = Invoke-RestMethod -Uri "$BASE_URL/community/communities" -Method Post -Headers @{
    "Authorization" = "Bearer $TOKEN"
    "Content-Type" = "application/json"
} -Body (@{ name = "Beginners Circle"; description = "New learners"; is_private = $false; max_members = 50 } | ConvertTo-Json)

$comm3 = Invoke-RestMethod -Uri "$BASE_URL/community/communities" -Method Post -Headers @{
    "Authorization" = "Bearer $TOKEN"
    "Content-Type" = "application/json"
} -Body (@{ name = "Mixed Group"; description = "Mixed levels"; is_private = $false; max_members = 50 } | ConvertTo-Json)

Write-Host "Created: $($comm1.name) (ID: $($comm1.id))" -ForegroundColor Green
Write-Host "Created: $($comm2.name) (ID: $($comm2.id))" -ForegroundColor Green
Write-Host "Created: $($comm3.name) (ID: $($comm3.id))" -ForegroundColor Green

# Step 2: Add leaderboard users to communities
# Elite: top 4 users (Fatima, Yusuf, Aisha, Omar)
# Beginners: bottom 4 users (Ibrahim, Khadija, Tariq, Maryam)
# Mixed: middle users (Zainab, Bilal)

$eliteEmails = @("fatima_931334@leaderboard.com", "yusuf_999681@leaderboard.com", "aisha_511012@leaderboard.com", "omar_835366@leaderboard.com")
$beginnerEmails = @("ibrahim_766670@leaderboard.com", "khadija_220955@leaderboard.com", "tariq_761781@leaderboard.com", "maryam_824468@leaderboard.com")
$mixedEmails = @("zainab_159082@leaderboard.com", "bilal_37868@leaderboard.com")

function Add-UsersToCommunity($emails, $commId, $commName) {
    Write-Host "`nAdding users to $commName..." -ForegroundColor Yellow
    foreach ($memberEmail in $emails) {
        try {
            $lb = @{ email = $memberEmail; password = "Test123!" } | ConvertTo-Json
            $resp = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $lb -ContentType "application/json"
            $mt = $resp.access_token

            Invoke-RestMethod -Uri "$BASE_URL/community/communities/$commId/join-request" -Method Post -Headers @{
                "Authorization" = "Bearer $mt"
            } | Out-Null
            Write-Host "  Join request: $memberEmail" -ForegroundColor Gray
        } catch {
            Write-Host "  SKIP: $memberEmail" -ForegroundColor Yellow
        }
    }

    # Approve all
    $requests = Invoke-RestMethod -Uri "$BASE_URL/community/communities/$commId/join-requests" -Headers @{
        "Authorization" = "Bearer $TOKEN"
    }
    foreach ($req in $requests) {
        Invoke-RestMethod -Uri "$BASE_URL/community/communities/$commId/join-requests/$($req.id)/approve" -Method Post -Headers @{
            "Authorization" = "Bearer $TOKEN"
        } | Out-Null
    }
    Write-Host "  Approved $($requests.Count) members" -ForegroundColor Green
}

Add-UsersToCommunity $eliteEmails $comm1.id $comm1.name
Add-UsersToCommunity $beginnerEmails $comm2.id $comm2.name
Add-UsersToCommunity $mixedEmails $comm3.id $comm3.name

# Step 3: Test community leaderboard
Write-Host "`n--- Community Rankings Leaderboard ---" -ForegroundColor Yellow

$lb = Invoke-RestMethod -Uri "$BASE_URL/community/communities-leaderboard" -Headers @{
    "Authorization" = "Bearer $TOKEN"
}

Write-Host "Total communities: $($lb.total_communities)" -ForegroundColor White
Write-Host "Scoring: $($lb.scoring)" -ForegroundColor White

Write-Host "`nTop 3 Communities:" -ForegroundColor Yellow
foreach ($c in $lb.top_3) {
    Write-Host "  #$($c.rank) $($c.community_name) | Score: $($c.total_score) | Avg: $($c.avg_member_score) | Members: $($c.active_members)/$($c.total_members)" -ForegroundColor Green
}

Write-Host "`nFull Rankings:" -ForegroundColor Yellow
foreach ($c in $lb.rankings) {
    $yours = if ($c.is_your_community) { " <- YOURS" } else { "" }
    Write-Host "  #$($c.rank) $($c.community_name) | Score: $($c.total_score) | Avg: $($c.avg_member_score) | Members: $($c.active_members)$yours" -ForegroundColor White
}

Write-Host "`nYour community rank: #$($lb.your_community.rank) - $($lb.your_community.community_name)" -ForegroundColor Cyan

Write-Host "`n=== TEST COMPLETE ===" -ForegroundColor Cyan
Write-Host "`nCleanup:" -ForegroundColor Yellow
Write-Host "DELETE FROM communities WHERE name IN ('Elite Reciters', 'Beginners Circle', 'Mixed Group');" -ForegroundColor White
Write-Host ""
