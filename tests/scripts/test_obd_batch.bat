@echo off
echo Testing OBD Batch Upload via cURL...

curl -X POST http://localhost:8080/api/v1/telemetry/batch ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer test-token" ^
  -d @scripts\test_obd_data.json

echo.
echo.
pause
