#!/bin/bash
echo "Testing /api/v1/auth/signup..."
curl -v -X POST http://localhost:8080/api/v1/auth/signup   -H "Content-Type: application/json"   -d '{"email": "test_'1768544163'@test.com", "password": "password123", "nickname": "testuser"}'

echo -e "\n\nTesting /auth/signup (without v1)..."
curl -v -X POST http://localhost:8080/auth/signup   -H "Content-Type: application/json"   -d '{"email": "test_'1768544163'_2@test.com", "password": "password123", "nickname": "testuser2"}'
