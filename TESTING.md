# Testing Guide - High School Management System

## Overview

This document describes the testing infrastructure for the High School Management System API.

## Test Structure

```
tests/
├── __init__.py              # Package initialization
├── conftest.py             # Shared fixtures and configuration
├── test_security.py        # Security utilities tests
├── test_api.py            # API endpoint tests
└── test_database.py       # Database interaction tests (future)
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r src/requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Tests with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_security.py
```

### Run Specific Test Class

```bash
pytest tests/test_security.py::TestPasswordValidation
```

### Run Specific Test Function

```bash
pytest tests/test_security.py::TestPasswordValidation::test_valid_password
```

### Run Tests by Marker

```bash
pytest -m unit           # Run only unit tests
pytest -m integration    # Run only integration tests
pytest -m security      # Run only security tests
```

### Run Tests with Coverage

```bash
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Categories

### Unit Tests (`tests/test_security.py`)

Tests for individual utility functions and components:

- **Rate Limiting Tests**
  - `test_get_rate_limit_string_format`: Verify format
  - `test_get_rate_limit_string_values`: Verify values
  - `test_rate_limit_configuration`: Configuration loading

- **Password Validation Tests**
  - `test_valid_password`: Valid passwords pass
  - `test_weak_password_too_short`: Short passwords rejected
  - `test_password_empty_or_none`: Empty passwords rejected
  - `test_password_too_long`: Long passwords rejected
  - `test_password_at_boundaries`: Boundary testing
  - `test_password_non_string_type`: Type validation

- **Client IP Extraction Tests**
  - `test_get_client_ip_direct_connection`: Direct connection IP
  - `test_get_client_ip_with_proxy`: Proxy X-Forwarded-For header
  - `test_get_client_ip_proxy_with_spaces`: Handle extra spaces
  - `test_get_client_ip_no_client`: Handle missing client
  - `test_get_client_ip_single_proxy`: Single proxy IP

- **Error Handling Tests**
  - `test_handle_rate_limit_exceeded`: Rate limit errors
  - `test_rate_limit_error_message`: Error message content

### Integration Tests (`tests/test_api.py`)

Tests for API endpoints and their interactions:

- **Authentication Endpoints**
  - Login endpoint (`POST /auth/login`)
  - Session check endpoint (`GET /auth/check-session`)
  - Credential validation

- **Activity Management**
  - List activities (`GET /activities`)
  - Filter activities by day and time
  - Get available days (`GET /activities/days`)

- **Input Validation**
  - Email validation in signup
  - Activity name length validation
  - Email length validation

- **Security Headers**
  - CORS headers presence
  - Static file serving

- **Error Handling**
  - 404 for nonexistent activities
  - 401 for missing authentication
  - Error response format

- **Rate Limiting**
  - Configuration verification
  - Request throttling

## Test Fixtures

Shared fixtures are defined in `conftest.py`:

### Session Fixtures
- `test_config`: Test configuration settings

### Mock Fixtures
- `mock_mongodb`: MongoDB collection mocks
- `mock_password_hasher`: Password hashing mock

### API Fixtures
- `api_client`: FastAPI test client
- `authenticated_headers`: Authentication headers

### Data Fixtures
- `sample_teacher`: Sample teacher data
- `sample_activity`: Sample activity data
- `sample_student_email`: Sample student email

### Parameterized Fixtures
- `invalid_email`: Various invalid email formats
- `weak_password`: Various weak passwords

## Writing New Tests

### Basic Test Template

```python
def test_feature_description(fixture_name):
    """
    Test description.

    This test verifies that [specific behavior] when [condition].

    Args:
        fixture_name: Description of fixture

    Assertions:
        - Assertion 1
        - Assertion 2
    """
    # Arrange: Set up test data
    test_data = {...}

    # Act: Perform the action being tested
    result = function_under_test(test_data)

    # Assert: Verify the result
    assert result == expected_value
```

### Test Best Practices

1. **Use Descriptive Names**: Test names should describe what is being tested
2. **One Assertion Per Test**: Each test should verify one behavior
3. **Use Fixtures**: Leverage fixtures for common setup
4. **Mock External Dependencies**: Mock database calls in unit tests
5. **Test Edge Cases**: Include boundary and error conditions
6. **Keep Tests Fast**: Unit tests should run quickly
7. **Use Assertions with Messages**: Include helpful assertion messages

### Example Test

```python
def test_validate_password_strength_rejects_short_passwords():
    """Test that short passwords (< 8 chars) are rejected."""
    short_password = "short"
    assert validate_password_strength(short_password) is False
```

## Mocking

### Mock Database

```python
@pytest.fixture
def mock_db(monkeypatch):
    with patch('src.backend.database.teachers_collection') as mock_teachers:
        mock_teachers.find_one.return_value = {...}
        yield mock_teachers
```

### Mock HTTP Requests

```python
def test_api_endpoint(api_client):
    response = api_client.get("/endpoint")
    assert response.status_code == 200
```

## Coverage

### Generate Coverage Report

```bash
pytest --cov=src --cov-report=html --cov-report=term-missing
```

### Coverage Goals

- **Minimum**: 80% overall coverage
- **Critical Code**: 100% coverage for security functions
- **Utils**: 90% coverage for utility functions
- **API**: 85% coverage for endpoints

## Continuous Integration

Tests are automatically run on:
- Push to feature branches
- Pull requests
- Before merge to main

### CI Configuration

See `.github/workflows/` for CI/CD pipeline definitions.

## Troubleshooting

### Tests Can't Find Modules

```bash
# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Database Connection Errors

Tests use mocked databases by default. Ensure `conftest.py` is properly configured.

### AsyncIO Tests Failing

```bash
# Install async testing support
pip install pytest-asyncio
```

## Performance Testing

```bash
# Run tests with timing information
pytest --durations=10  # Show 10 slowest tests
```

## Debug Mode

```bash
# Run tests with debug output
pytest -s              # Show print statements
pytest -vv             # Very verbose
pytest --pdb           # Drop into debugger on failure
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

## Contributing Tests

When contributing new features:
1. Write tests for new functionality
2. Ensure all tests pass locally
3. Maintain or improve code coverage
4. Follow test naming conventions
5. Include docstrings in test functions

## Test Maintenance

- Review tests when code changes
- Update mocks when dependencies change
- Remove duplicate test cases
- Keep fixtures up to date
- Monitor test execution time

---

**Last Updated**: 2026-06-26
**Status**: ✅ Complete
