# POPULATE TEST DATA
$BASE_URL = "http://localhost:8000"

Write-Host "`n=== POPULATING TEST DATA ===" -ForegroundColor Cyan

$testUsers = @(
    @{ email = "ahmed_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Ahmed"; last_name = "Ali"; recitations = 50; avgAccuracy = 97.5 },
    @{ email = "fatima_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Fatima"; last_name = "Hassan"; recitations = 45; avgAccuracy = 95.8 },
    @{ email = "omar_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Omar"; last_name = "Khan"; recitations = 40; avgAccuracy = 94.2 },
    @{ email = "aisha_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Aisha"; last_name = "Rahman"; recitations = 35; avgAccuracy = 92.0 },
    @{ email = "ibrahim_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Ibrahim"; last_name = "Malik"; recitations = 30; avgAccuracy = 90.5 },
    @{ email = "maryam_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Maryam"; last_name = "Yusuf"; recitations = 25; avgAccuracy = 88.7 },
    @{ email = "ali_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Ali"; last_name = "Abdullah"; recitations = 20; avgAccuracy = 86.3 },
    @{ email = "zainab_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Zainab"; last_name = "Ahmad"; recitations = 18; avgAccuracy = 84.5 },
    @{ email = "hassan_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Hassan"; last_name = "Ibrahim"; recitations = 15; avgAccuracy = 82.0 },
    @{ email = "sara_$(Get-Random)@test.com"; password = "Test123!"; first_name = "Sara"; last_name = "Mohammed"; recitations = 12; avgAccuracy = 80.2 }
)

$createdUsers = @()

# Create users
Write-Host "`n--- Creating Users ---" -ForegroundColor Yellow
foreach ($user in $testUsers) {
    Write-Host "Creating: $($user.first_name) $($user.last_name)" -ForegroundColor White
    
    try {
        $registerBody = @{
            email = $user.email
            password = $user.password
            first_name = $user.first_name
            last_name = $user.last_name
        } | ConvertTo-Json
        
        $registerResponse = Invoke-RestMethod -Uri "$BASE_URL/auth/register" -Method Post -Body $registerBody -ContentType "application/json"
        $user.id = $registerResponse.id
        $createdUsers += $user
        Write-Host "  PASS - ID: $($user.id)" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL" -ForegroundColor Red
    }
}

Write-Host "`nCreated $($createdUsers.Count) users" -ForegroundColor Cyan

# Verify emails
Write-Host "`n--- VERIFY EMAILS ---" -ForegroundColor Yellow
Write-Host "Run this SQL:" -ForegroundColor Cyan
Write-Host "UPDATE users SET is_email_verified = true WHERE email LIKE '%@test.com';" -ForegroundColor White
Read-Host "`nPress Enter after running SQL"

# Log activities
Write-Host "`n--- Logging Activities ---" -ForegroundColor Yellow

foreach ($user in $createdUsers) {
    Write-Host "`n$($user.first_name) $($user.last_name):" -ForegroundColor White
    
    try {
        $loginBody = @{ email = $user.email; password = $user.password } | ConvertTo-Json
        $loginResponse = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
        $token = $loginResponse.access_token
        
        $headers = @{
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        }
        
        for ($i = 1; $i -le $user.recitations; $i++) {
            $variance = Get-Random -Minimum -5 -Maximum 5
            $accuracy = [Math]::Max(50, [Math]::Min(100, $user.avgAccuracy + $variance))
            $duration = Get-Random -Minimum 30 -Maximum 180
            
            $activityBody = @{
                activity_type = "recitation"
                surah_number = 1
                ayah_number = $i
                duration_seconds = $duration
                accuracy_score = $accuracy
            } | ConvertTo-Json
            
            Invoke-RestMethod -Uri "$BASE_URL/progress/log-activity" -Method Post -Headers $headers -Body $activityBody | Out-Null
            
            if ($i % 10 -eq 0) {
                Write-Host "  Progress: $i/$($user.recitations)" -ForegroundColor Gray
            }
            
            Start-Sleep -Milliseconds 50
        }
        
        Write-Host "  PASS - $($user.recitations) recitations" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL" -ForegroundColor Red
    }
}

Write-Host "`n=== DONE ===" -ForegroundColor Cyan
Write-Host "Created $($createdUsers.Count) users with activities" -ForegroundColor Green
Write-Host "`nCleanup SQL:" -ForegroundColor Yellow
Write-Host "DELETE FROM users WHERE email LIKE '%@test.com';" -ForegroundColor White
Write-Host ""
