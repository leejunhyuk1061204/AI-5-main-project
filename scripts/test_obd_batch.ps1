$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer eyJhbGciOiJIUzI1NiJ9.test-token" # Dummy token for now
}

$body = @"
[
    {
        "timestamp": "2024-05-20T10:00:00",
        "vehicleId": "550e8400-e29b-41d4-a716-446655440000",
        "rpm": 2500.5,
        "speed": 80.0,
        "voltage": 13.5,
        "coolantTemp": 90.0
    },
    {
        "timestamp": "2024-05-20T10:00:01",
        "vehicleId": "550e8400-e29b-41d4-a716-446655440000",
        "rpm": 2510.0,
        "speed": 81.0,
        "voltage": 13.4,
        "coolantTemp": 90.5
    }
]
"@

$url = "http://localhost:8080/api/v1/telemetry/batch"

try {
    $response = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $body
    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Error:" -ForegroundColor Red
    $_.Exception.Response
}
