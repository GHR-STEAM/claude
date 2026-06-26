"""
Tests for Phase 4: JWT authentication, Pydantic models, error handling,
seed data, and configuration.
"""

import pytest
import jwt
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone


@pytest.mark.unit
class TestJWTAuth:
    """Test JWT authentication system."""

    def test_create_access_token(self):
        from src.backend.auth import create_access_token, SECRET_KEY, ALGORITHM
        token = create_access_token("testuser", "teacher")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["username"] == "testuser"
        assert payload["role"] == "teacher"
        assert "exp" in payload

    def test_decode_valid_token(self):
        from src.backend.auth import create_access_token, decode_access_token
        token = create_access_token("testuser", "admin")
        token_data = decode_access_token(token)
        assert token_data.username == "testuser"
        assert token_data.role == "admin"

    def test_decode_expired_token(self):
        from src.backend.auth import decode_access_token, SECRET_KEY, ALGORITHM
        import time
        expired_payload = {
            "username": "test",
            "role": "teacher",
            "exp": int(time.time()) - 3600,
        }
        expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            decode_access_token(expired_token)
        assert exc.value.status_code == 401

    def test_decode_invalid_token(self):
        from src.backend.auth import decode_access_token
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            decode_access_token("invalid.token.here")
        assert exc.value.status_code == 401

    def test_hash_and_verify_password(self):
        from src.backend.auth import hash_password, verify_password
        hashed = hash_password("SecurePass123")
        assert verify_password(hashed, "SecurePass123") is True
        assert verify_password(hashed, "WrongPassword") is False

    def test_authenticate_user_success(self):
        from src.backend.auth import authenticate_user
        with patch("src.backend.auth.teachers_collection") as mock_col:
            mock_col.find_one.return_value = {
                "_id": "teacher1",
                "username": "teacher1",
                "password": "$argon2id$v=19$m=...",
                "display_name": "Test Teacher",
                "role": "teacher",
            }
            with patch("src.backend.auth.verify_password", return_value=True):
                result = authenticate_user("teacher1", "pass")
                assert result is not None
                assert result["username"] == "teacher1"

    def test_authenticate_user_not_found(self):
        from src.backend.auth import authenticate_user
        with patch("src.backend.auth.teachers_collection") as mock_col:
            mock_col.find_one.return_value = None
            result = authenticate_user("nonexistent", "pass")
            assert result is None

    def test_authenticate_user_wrong_password(self):
        from src.backend.auth import authenticate_user
        with patch("src.backend.auth.teachers_collection") as mock_col:
            mock_col.find_one.return_value = {
                "_id": "teacher1",
                "password": "hashed",
            }
            with patch("src.backend.auth.verify_password", return_value=False):
                result = authenticate_user("teacher1", "wrong")
                assert result is None


@pytest.mark.unit
class TestPydanticModels:
    """Test Pydantic models."""

    def test_login_request_valid(self):
        from src.backend.models import LoginRequest
        req = LoginRequest(username="teacher1", password="SecurePass123")
        assert req.username == "teacher1"
        assert req.password == "SecurePass123"

    def test_login_request_empty_username(self):
        from src.backend.models import LoginRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LoginRequest(username="", password="pass")

    def test_token_response(self):
        from src.backend.models import TokenResponse
        resp = TokenResponse(
            access_token="jwt.token.here",
            expires_in=28800,
            username="teacher1",
            display_name="Test",
            role="teacher",
        )
        assert resp.token_type == "bearer"
        assert resp.access_token == "jwt.token.here"

    def test_signup_request_valid_email(self):
        from src.backend.models import SignupRequest
        req = SignupRequest(email="student@mergington.edu")
        assert str(req.email) == "student@mergington.edu"

    def test_signup_request_invalid_email(self):
        from src.backend.models import SignupRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SignupRequest(email="not-an-email")

    def test_message_response(self):
        from src.backend.models import MessageResponse
        resp = MessageResponse(message="Success")
        assert resp.message == "Success"

    def test_error_response(self):
        from src.backend.models import ErrorResponse
        resp = ErrorResponse(detail="Not found", error_code="NOT_FOUND")
        assert resp.detail == "Not found"
        assert resp.error_code == "NOT_FOUND"


@pytest.mark.unit
class TestErrorHandlers:
    """Test global error handlers."""

    def test_error_response_model(self):
        from src.backend.models import ErrorResponse
        resp = ErrorResponse(detail="Test error")
        assert resp.detail == "Test error"

    def test_validation_error_formatting(self):
        from src.backend.error_handlers import register_error_handlers
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        register_error_handlers(app)

        @app.get("/test")
        def test_endpoint(param: int):
            return {"param": param}

        client = TestClient(app)
        response = client.get("/test", params={"param": "not-a-number"})
        assert response.status_code == 422

    def test_global_exception_handler(self):
        from src.backend.error_handlers import register_error_handlers
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        register_error_handlers(app)

        @app.get("/error")
        def error_endpoint():
            raise RuntimeError("Unexpected error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/error")
        assert response.status_code == 500
        assert "detail" in response.json()


@pytest.mark.unit
class TestSeedData:
    """Test seed data module."""

    def test_initial_activities_count(self):
        from src.backend.seed_data import initial_activities
        assert len(initial_activities) == 12

    def test_initial_activities_structure(self):
        from src.backend.seed_data import initial_activities
        for name, details in initial_activities.items():
            assert "description" in details
            assert "schedule" in details
            assert "schedule_details" in details
            assert "max_participants" in details
            assert "participants" in details

    def test_get_initial_teachers_dev(self):
        from src.backend.seed_data import get_initial_teachers
        with patch.dict("os.environ", {"ENVIRONMENT": "development"}):
            teachers = get_initial_teachers()
            assert len(teachers) == 3
            assert teachers[0]["username"] == "mrodriguez"
            assert teachers[2]["role"] == "admin"

    def test_get_initial_teachers_production_requires_env(self):
        from src.backend.seed_data import _get_teacher_password
        with patch.dict("os.environ", {"ENVIRONMENT": "production", "TEACHER_PASSWORD_MRODRIGUEZ": ""}):
            with pytest.raises(ValueError, match="must be set"):
                _get_teacher_password("TEACHER_PASSWORD_MRODRIGUEZ", "default")

    def test_get_teacher_password_weak_rejected(self):
        from src.backend.seed_data import _get_teacher_password
        with patch.dict("os.environ", {"ENVIRONMENT": "development", "TEACHER_PASSWORD_TEST": "weak"}):
            with pytest.raises(ValueError, match="strength"):
                _get_teacher_password("TEACHER_PASSWORD_TEST", "fallback")


@pytest.mark.unit
class TestEnvironmentConfig:
    """Test environment configuration."""

    def test_env_example_exists(self):
        from pathlib import Path
        env_example = Path(__file__).parent.parent / ".env.example"
        assert env_example.exists(), ".env.example should exist"

    def test_env_example_has_required_vars(self):
        from pathlib import Path
        env_example = Path(__file__).parent.parent / ".env.example"
        content = env_example.read_text()
        required_vars = [
            "MONGODB_URL",
            "DATABASE_NAME",
            "SECRET_KEY",
            "REDIS_HOST",
            "CORS_ORIGINS",
            "TEACHER_PASSWORD_MRODRIGUEZ",
        ]
        for var in required_vars:
            assert var in content, f"{var} should be in .env.example"


@pytest.mark.unit
class TestDockerFiles:
    """Test Docker configuration files exist."""

    def test_dockerfile_exists(self):
        from pathlib import Path
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        assert dockerfile.exists()

    def test_docker_compose_exists(self):
        from pathlib import Path
        compose = Path(__file__).parent.parent / "docker-compose.yml"
        assert compose.exists()

    def test_dockerfile_has_multistage(self):
        from pathlib import Path
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text()
        assert "AS builder" in content
        assert "python:3.13-slim" in content

    def test_docker_compose_has_services(self):
        from pathlib import Path
        compose = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose.read_text()
        assert "web:" in content
        assert "mongo:" in content
        assert "redis:" in content


@pytest.mark.unit
class TestCIWorkflow:
    """Test CI/CD workflow exists."""

    def test_ci_workflow_exists(self):
        from pathlib import Path
        ci = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        assert ci.exists()

    def test_ci_has_test_step(self):
        from pathlib import Path
        ci = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci.read_text()
        assert "pytest" in content
        assert "mongo" in content
        assert "redis" in content
