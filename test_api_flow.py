import httpx
import os
import uuid

BACKEND_URL = "http://localhost:8000"

def test_flow():
    # 1. Register a new user
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    password = "Password123!"
    full_name = "E2E Test User"
    
    print(f"Registering user: {email}...")
    reg_response = httpx.post(
        f"{BACKEND_URL}/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name}
    )
    if reg_response.status_code != 201:
        print(f"Registration failed: {reg_response.text}")
        return
    print("Registration successful!")

    # 2. Login
    print("Logging in...")
    login_response = httpx.post(
        f"{BACKEND_URL}/api/auth/login",
        json={"email": email, "password": password}
    )
    if login_response.status_code != 200:
        print(f"Login failed: {login_response.text}")
        return
    token = login_response.json()["access_token"]
    print("Login successful! Token acquired.")
    
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Upload dataset
    file_path = "test_data_small.csv"
    print(f"Uploading dataset {file_path}...")
    with open(file_path, "rb") as f:
        upload_response = httpx.post(
            f"{BACKEND_URL}/api/datasets/upload",
            headers=headers,
            files={"file": (os.path.basename(file_path), f, "text/csv")}
        )
    if upload_response.status_code != 201:
        print(f"Upload failed: {upload_response.text}")
        return
    dataset_id = upload_response.json()["id"]
    print(f"Upload successful! Dataset ID: {dataset_id}")

    # 4. List datasets
    print("Listing datasets...")
    list_response = httpx.get(f"{BACKEND_URL}/api/datasets/", headers=headers)
    print(f"Dataset list: {list_response.json()}")

    # 5. Run forecast
    print("Running forecast...")
    forecast_payload = {
        "dataset_id": dataset_id,
        "forecast_periods": 7,
        "seasonality_period": 7,
        "confidence_level": 0.95
    }
    forecast_response = httpx.post(
        f"{BACKEND_URL}/api/forecast/",
        headers=headers,
        json=forecast_payload,
        timeout=60.0
    )
    if forecast_response.status_code != 200:
        print(f"Forecast failed: {forecast_response.text}")
        return
    forecast_data = forecast_response.json()
    print("Forecast successful! Results summary:")
    print(f"Dates (count: {len(forecast_data['dates'])}): {forecast_data['dates'][:5]} ...")
    print(f"Values (count: {len(forecast_data['values'])}): {forecast_data['values'][:5]} ...")
    print(f"Lower bound: {forecast_data['lower_bound'][:5] if forecast_data['lower_bound'] else None} ...")
    print(f"Upper bound: {forecast_data['upper_bound'][:5] if forecast_data['upper_bound'] else None} ...")

    # 6. Test scenario creation (What-if Analysis)
    print("Creating scenario...")
    scenario_payload = {
        "dataset_id": dataset_id,
        "name": "Price Promo Scenario",
        "parameters": {
            "forecast_periods": 7,
            "seasonality_period": 7,
            "confidence_level": 0.95,
            "additional_params": {
                "price_multiplier": 0.9,
                "promo_multiplier": 1.2
            }
        }
    }
    scenario_response = httpx.post(
        f"{BACKEND_URL}/api/forecast/scenarios",
        headers=headers,
        json=scenario_payload,
        timeout=60.0
    )
    if scenario_response.status_code != 200:
        print(f"Scenario failed: {scenario_response.text}")
        return
    scenario_data = scenario_response.json()
    print(f"Scenario creation successful! Scenario ID: {scenario_data['id']}")
    print(f"Scenario result keys: {scenario_data.keys()}")

if __name__ == "__main__":
    test_flow()
