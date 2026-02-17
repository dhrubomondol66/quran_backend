# POPULATE LEADERBOARD TEST DATA
# Creates 10 users with varied accuracy and recitations to test ranking

$BASE_URL = "http://localhost:8000"

Write-Host "`n=== POPULATING LEADERBOARD TEST DATA ===" -ForegroundColor Cyan

# 10 users with different accuracy/recitation combos to test 70/30 formula
$testUsers = @(
    @{ first_name = "Aisha";   last_name = "Rahman";  accuracy = 97; recitations = 50 },  # High acc, high rec -> #1
    @{ first_name = "Bilal";   last_name = "Hassan";  accuracy = 95; recitations = 45 },  # High acc, high rec -> #2
    @{ first_name = "Fatima";  last_name = "Malik";   accuracy = 92; recitations = 60 },  # High rec, good acc -> #3
    @{ first_name = "Omar";    last_name = "Sheikh";  accuracy = 90; recitations = 55 },  # Good mix -> #4
    @{ first_name = "Zainab";  last_name = "Ali";     accuracy = 88; recitations = 40 },  # Mid acc, mid rec -> #5
    @{ first_name = "Yusuf";   last_name = "Khan";    accuracy = 85; recitations = 70 },  # Low acc, high rec -> #6
    @{ first_name = "Maryam";  last_name = "Idris";   accuracy = 82; recitations = 35 },  # Low acc, low rec -> #7
    @{ first_name = "Ibrahim"; last_name = "Noor";    accuracy = 78; recitations = 30 },  # Low acc, low rec -> #8
    @{ first_name = "Khadija"; last_name = "Osman";   accuracy = 75; recitations = 25 },  # Very low -> #9
    @{ first_name = "Tariq";   last_name = "Siddiq";  accuracy = 70; recitations = 20 }   # Lowest -> #10
)

Write-Host "`nExpected ranking (70% accuracy + 30% recitations):" -ForegroundColor Yellow
Write-Host "  #1  Aisha   - Score: ~97.0  (97% acc, 50 rec)" -ForegroundColor White
Write-Host "  #2  Bilal   - Score: ~95.0  (95% acc, 45 rec)" -ForegroundColor White
Write-Host "  #3  Fatima  - Score: ~82.4  (92% acc, 60 rec)" -ForegroundColor White
Write-Host "  #4  Omar    - Score: ~86.5  (90% acc, 55 rec)" -ForegroundColor White
Write-Host "  #5  Zainab  - Score: ~78.3  (88% acc, 40 rec)" -ForegroundColor White
Write-Host "  ...and so on" -ForegroundColor Gray

# Create users
Write-Host "`nCreating 10 test users..." -ForegroundColor Yellow

$emails = @()
foreach ($user in $testUsers) {
    $rand = Get-Random -Maximum 999999
    $email = "$($user.first_name.ToLower())_$rand@leaderboard.com"
    $emails += $email

    $body = @{
        email = $email
        password = "Test123!"
        first_name = $user.first_name
        last_name = $user.last_name
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "$BASE_URL/auth/register" -Method Post -Body $body -ContentType "application/json" | Out-Null
    Write-Host "  Created: $($user.first_name) $($user.last_name) ($email)" -ForegroundColor Green
}

Write-Host "`nRUN THIS SQL to verify and insert progress data:" -ForegroundColor Red
Write-Host "Step 1 - Verify emails:" -ForegroundColor Yellow
Write-Host "UPDATE users SET is_email_verified = true WHERE email LIKE '%@leaderboard.com';" -ForegroundColor Cyan
Read-Host "`nPress Enter after running SQL"

# Now login each user and insert their progress via SQL
Write-Host "`nRUN THIS SQL to insert progress data:" -ForegroundColor Yellow

# Build the SQL dynamically
$sql = "-- Insert progress for leaderboard test users`n"
$sql += "DO `$`$`n"
$sql += "DECLARE uid INTEGER;`n"
$sql += "BEGIN`n"

for ($i = 0; $i -lt $testUsers.Count; $i++) {
    $user = $testUsers[$i]
    $email = $emails[$i]
    $accuracy = $user.accuracy
    $recitations = $user.recitations
    $timeSpent = $recitations * 120  # 2 minutes per recitation

    $sql += "  SELECT id INTO uid FROM users WHERE email = '$email';`n"
    $sql += "  -- Create UserSettings`n"
    $sql += "  INSERT INTO usersettings (user_id, show_on_leaderboard, daily_reminder, reminder_time)`n"
    $sql += "    VALUES (uid, true, false, '09:00')`n"
    $sql += "    ON CONFLICT (user_id) DO UPDATE SET show_on_leaderboard = true;`n"
    $sql += "  -- Create UserProgress`n"
    $sql += "  INSERT INTO userprogress (user_id, total_recitation_attempts, average_accuracy, total_time_spent_seconds, current_streak, longest_streak)`n"
    $sql += "    VALUES (uid, $recitations, $accuracy, $timeSpent, $(Get-Random -Minimum 1 -Maximum 30), $(Get-Random -Minimum 5 -Maximum 50))`n"
    $sql += "    ON CONFLICT (user_id) DO UPDATE SET`n"
    $sql += "      total_recitation_attempts = $recitations,`n"
    $sql += "      average_accuracy = $accuracy,`n"
    $sql += "      total_time_spent_seconds = $timeSpent;`n"
}

$sql += "END `$`$;"

Write-Host "`n$sql" -ForegroundColor Cyan
$sql | Out-File -FilePath ".\insert_progress.sql" -Encoding UTF8
Write-Host "`nSQL saved to: insert_progress.sql" -ForegroundColor Green
Write-Host "Run it with: psql -U postgres -d quran_app -f insert_progress.sql" -ForegroundColor Yellow

Read-Host "`nPress Enter after running the SQL"

# Test leaderboard with first user
Write-Host "`n--- Testing Leaderboard ---" -ForegroundColor Yellow

$loginBody = @{ email = $emails[0]; password = "Test123!" } | ConvertTo-Json
$response = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$TOKEN = $response.access_token

$leaderboard = Invoke-RestMethod -Uri "$BASE_URL/leaderboard/leaderboard" -Headers @{
    "Authorization" = "Bearer $TOKEN"
}

Write-Host "`nTotal participants: $($leaderboard.total_participants)" -ForegroundColor White
Write-Host "Scoring: $($leaderboard.scoring)" -ForegroundColor White

Write-Host "`nTop 3:" -ForegroundColor Yellow
foreach ($user in $leaderboard.top_3) {
    Write-Host "  #$($user.rank) $($user.name) - Score: $($user.score) | Accuracy: $($user.accuracy)% | Recitations: $($user.total_recitations)" -ForegroundColor Green
}

Write-Host "`nFull Rankings (Top 10):" -ForegroundColor Yellow
foreach ($user in $leaderboard.rankings | Select-Object -First 10) {
    $you = if ($user.is_you) { " <- YOU" } else { "" }
    Write-Host "  #$($user.rank) $($user.name) - Score: $($user.score) | Acc: $($user.accuracy)% | Rec: $($user.total_recitations)$you" -ForegroundColor White
}

Write-Host "`nYour rank: #$($leaderboard.current_user.rank)" -ForegroundColor Cyan

Write-Host "`n=== LEADERBOARD TEST COMPLETE ===" -ForegroundColor Cyan

Write-Host "`nCleanup when done:" -ForegroundColor Yellow
Write-Host "DELETE FROM users WHERE email LIKE '%@leaderboard.com';" -ForegroundColor White
Write-Host ""