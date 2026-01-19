import requests
import json
import time

BASE_URL = "http://localhost:8080"
EMAIL = "test_refresh@example.com"
PASSWORD = "password123"
NICKNAME = "Tester"

def test_refresh_token_flow():
    print("--- 1. Signup ---")
    signup_data = {
        "email": EMAIL,
        "password": PASSWORD,
        "nickname": NICKNAME
    }
    r = requests.post(f"{BASE_URL}/auth/signup", json=signup_data)
    if r.status_code == 201:
        print("Signup Success")
    elif r.status_code == 409:
        print("User already exists, proceeding to login")
    else:
        print(f"Signup Failed: {r.status_code}, {r.text}")
        return

    print("\n--- 2. Login ---")
    login_data = {
        "email": EMAIL,
        "password": PASSWORD
    }
    r = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if r.status_code != 200:
        print(f"Login Failed: {r.status_code}, {r.text}")
        return
    
    resp_body = r.json()
    access_token = resp_body['data']['accessToken']
    refresh_token = resp_body['data']['refreshToken']
    print(f"Login Success!")
    print(f"Access Token: {access_token[:20]}...")
    print(f"Refresh Token: {refresh_token[:20]}...")

    print("\n--- 3. Verify me endpoint with AT ---")
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    if r.status_code == 200:
        print("Profile Access Success")
    else:
        print(f"Profile Access Failed: {r.status_code}")

    print("\n--- 4. Refresh Token ---")
    refresh_data = {"refreshToken": refresh_token}
    r = requests.post(f"{BASE_URL}/auth/refresh", json=refresh_data)
    if r.status_code != 200:
        print(f"Refresh Failed: {r.status_code}, {r.text}")
        return
        
    new_resp = r.json()
    new_access_token = new_resp['data']['accessToken']
    new_refresh_token = new_resp['data']['refreshToken']
    print("Refresh Success!")
    print(f"New AT: {new_access_token[:20]}...")
    print(f"New RT: {new_refresh_token[:20]}...")

    print("\n--- 5. Wait a second and try old RT (Rotation Test) ---")
    time.sleep(1)
    r = requests.post(f"{BASE_URL}/auth/refresh", json=refresh_data)
    if r.status_code == 401:
        print("Old Refresh Token Rejected as expected (Rotation Blocked)")
    else:
        print(f"Warning: Old RT still working? {r.status_code}")

    print("\n--- 6. Verify new AT ---")
    headers = {"Authorization": f"Bearer {new_access_token}"}
    r = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    if r.status_code == 200:
        print("New Access Token Success")
    else:
        print(f"New AT Failed: {r.status_code}")

if __name__ == "__main__":
    test_refresh_token_flow()
