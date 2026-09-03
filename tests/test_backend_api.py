import os
import sys

# Set environment variables for testing before importing the app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-1234567890-test-secret-key"

try:
    import pytest
except ImportError:
    class MockPytest:
        class Mark:
            @staticmethod
            def asyncio(func):
                return func
        mark = Mark()
    pytest = MockPytest()

from httpx import AsyncClient, ASGITransport

# Add backend folder to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

# Explicitly import models to ensure they are registered with Base.metadata
from app.models.user import User
from app.models.dataset import Dataset
from app.models.forecast import ForecastResult, ForecastScenario

from app.main import app
from app.database import init_db


@pytest.mark.asyncio
async def test_backend_flow():
    # Manually initialize the test database to ensure tables are created
    await init_db()

    # Use a single AsyncClient to ensure the in-memory SQLite database connection pool stays alive
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        
        # 1. Health check test
        health_response = await ac.get("/api/health")
        assert health_response.status_code == 200
        assert health_response.json() == {"status": "ok"}

        # 2. Register a new user
        reg_payload = {
            "email": "testuser@example.com",
            "password": "Password123!",
            "full_name": "Test Suite User"
        }
        reg_response = await ac.post("/api/auth/register", json=reg_payload)
        assert reg_response.status_code == 201
        user_data = reg_response.json()
        assert user_data["email"] == "testuser@example.com"
        assert "id" in user_data

        # 3. Try to register same email again (should fail)
        dup_response = await ac.post("/api/auth/register", json=reg_payload)
        assert dup_response.status_code == 400
        assert dup_response.json()["detail"] == "Email already registered"

        # 4. Login with credentials
        login_payload = {
            "email": "testuser@example.com",
            "password": "Password123!"
        }
        login_response = await ac.post("/api/auth/login", json=login_payload)
        assert login_response.status_code == 200
        token_data = login_response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"


if __name__ == "__main__":
    import asyncio
    
    async def run_all():
        print("Running test_backend_flow...")
        await test_backend_flow()
        print("✅ All backend API tests passed successfully!")

    asyncio.run(run_all())
