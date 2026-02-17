# SUBSCRIPTION EXPIRY NOTIFICATION TEST
$BASE_URL = "http://localhost:8000"

Write-Host "`n=== SUBSCRIPTION EXPIRY NOTIFICATION TEST ===" -ForegroundColor Cyan

# Login with existing account
$email = Read-Host "Your email"
$password = Read-Host "Your password" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

$loginBody = @{ email = $email; password = $passwordPlain } | ConvertTo-Json
$response = Invoke-RestMethod -Uri "$BASE_URL/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$TOKEN = $response.access_token
Write-Host "Logged in" -ForegroundColor Green

# Get user ID from DB
Write-Host "`nRUN THIS SQL to find your user ID:" -ForegroundColor Red
Write-Host "SELECT id, email FROM users WHERE email = '$email';" -ForegroundColor Cyan
$userId = Read-Host "Enter your user ID"
Write-Host "User ID: $userId" -ForegroundColor White

# Check notifications before
$before = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $TOKEN" }
$beforeCount = $before.Count
Write-Host "Notifications before: $beforeCount" -ForegroundColor White

# Step 1: Set subscription to expire in 25 hours
Write-Host "`n--- Step 1: Setting subscription to expire in 25 hours ---" -ForegroundColor Yellow
Write-Host "RUN THIS SQL:" -ForegroundColor Red
Write-Host "UPDATE users SET subscription_end_date = NOW() + INTERVAL '25 hours', subscription_status = 'active' WHERE id = $userId;" -ForegroundColor Cyan
Read-Host "Press Enter after running SQL"

# Step 2: Run the subscription checker
Write-Host "`n--- Step 2: Running subscription checker ---" -ForegroundColor Yellow
try {
    $result = & python -c "
from app.tasks.subscription_checker import check_expiring_subscriptions
import logging
logging.basicConfig(level=logging.INFO)
check_expiring_subscriptions()
print('DONE')
" 2>&1
    Write-Host $result -ForegroundColor White
} catch {
    Write-Host "Error running checker: $_" -ForegroundColor Red
}

# Step 3: Check notifications after
Write-Host "`n--- Step 3: Checking notifications ---" -ForegroundColor Yellow
Start-Sleep -Seconds 1

$after = Invoke-RestMethod -Uri "$BASE_URL/notifications/notifications" -Headers @{ "Authorization" = "Bearer $TOKEN" }
$afterCount = $after.Count

Write-Host "Notifications after: $afterCount" -ForegroundColor White

if ($afterCount -gt $beforeCount) {
    $newNotif = $after | Where-Object { $_.type -eq "subscription_expiring" } | Select-Object -First 1
    if ($newNotif) {
        Write-Host "`nPASS - Subscription expiry notification received!" -ForegroundColor Green
        Write-Host "  Title: $($newNotif.title)" -ForegroundColor White
        Write-Host "  Message: $($newNotif.message)" -ForegroundColor White
        Write-Host "  Type: $($newNotif.type)" -ForegroundColor Gray
        Write-Host "  Read: $($newNotif.is_read)" -ForegroundColor Gray
    } else {
        Write-Host "`nWARN - New notification found but wrong type" -ForegroundColor Yellow
        Write-Host "  Type: $($after[0].type)" -ForegroundColor White
    }
} else {
    Write-Host "`nFAIL - No new notification" -ForegroundColor Red
    Write-Host "Check server logs for errors" -ForegroundColor Yellow
}

# Step 4: Cleanup - reset subscription
Write-Host "`n--- Cleanup ---" -ForegroundColor Yellow
Write-Host "RUN THIS SQL to reset:" -ForegroundColor Red
Write-Host "UPDATE users SET subscription_end_date = NULL, subscription_status = 'free' WHERE id = $userId;" -ForegroundColor Cyan

Write-Host "`n=== TEST COMPLETE ===" -ForegroundColor Cyan
Write-Host ""