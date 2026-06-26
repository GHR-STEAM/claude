# Mergington High School - Activities API

A production-ready FastAPI application for managing extracurricular activities at Mergington High School.

## Features

- **JWT Authentication** - Secure token-based auth with Argon2 password hashing
- **Role-based Access Control** - Teacher and admin roles
- **Activity Management** - Browse, filter, sign up, and unregister students
- **Pagination** - Cursor-based pagination with configurable page sizes
- **Redis Caching** - Distributed caching with graceful fallback
- **Monitoring Dashboard** - Real-time metrics, health checks, and cache status at `/dashboard`
- **Audit Logging** - Track all mutation operations
- **Request Tracing** - X-Request-ID header for every request
- **Rate Limiting** - Configurable per-endpoint rate limits
- **CORS Protection** - Configurable allowed origins
- **Global Error Handling** - Sanitized error responses with structured format
- **Docker Support** - Multi-stage Dockerfile with docker-compose

## Quick Start

### Docker (Recommended)

```bash
cp .env.example .env
# Edit .env with your values
docker-compose up -d
```

The API will be available at `http://localhost:8000`
Dashboard at `http://localhost:8000/dashboard`
Docs at `http://localhost:8000/api/docs`

### Local Development

```bash
pip install -r src/requirements.txt
# Start MongoDB and Redis locally
cd src && uvicorn app:app --reload --port 8000
```

## API Endpoints (v1)

### Authentication
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/auth/login` | Login and receive JWT | No |
| GET | `/api/v1/auth/check-session` | Validate JWT token | JWT |
| GET | `/api/v1/auth/me` | Get current user info | JWT |

### Activities
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/activities` | List activities (with filters + pagination) | No |
| GET | `/api/v1/activities/days` | Get available days | No |
| POST | `/api/v1/activities/{name}/signup` | Sign up student | JWT |
| POST | `/api/v1/activities/{name}/unregister` | Unregister student | JWT |

### Dashboard
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/dashboard/health` | Health check | No |
| GET | `/api/v1/dashboard/stats` | Activity statistics | No |
| GET | `/api/v1/dashboard/metrics` | Performance metrics | No |
| GET | `/api/v1/dashboard/metrics-advanced` | Latency percentiles + status codes | No |
| GET | `/api/v1/dashboard/cache-status` | Cache status | No |
| POST | `/api/v1/dashboard/cache/clear` | Clear all caches | No |
| GET | `/api/v1/dashboard/indexes` | Database index status | No |
| GET | `/api/v1/dashboard/backups` | List database backups | No |

## Environment Variables

See [`.env.example`](.env.example) for all configuration options.

Key variables:
- `SECRET_KEY` - JWT signing key (required in production)
- `MONGODB_URL` - MongoDB connection string
- `REDIS_ENABLED` - Enable/disable Redis caching
- `ENVIRONMENT` - `development` or `production`
- `TEACHER_PASSWORD_*` - Teacher passwords (required in production)

## Tech Stack

- **Framework:** FastAPI 0.115
- **Database:** MongoDB 7
- **Cache:** Redis 7
- **Auth:** JWT (PyJWT) + Argon2
- **Validation:** Pydantic v2
- **Container:** Docker + docker-compose
- **CI/CD:** GitHub Actions

## Project Structure

```
src/
  app.py                 # FastAPI app factory + middleware setup
  requirements.txt       # Python dependencies
  static/                # Frontend (HTML/CSS/JS + dashboard)
  backend/
    auth.py              # JWT authentication system
    models.py            # Pydantic request/response models
    database.py          # MongoDB connection + init
    seed_data.py         # Initial activity/teacher data
    security.py          # Rate limiting + validation
    logging_config.py    # Centralized logging
    performance.py       # Cache + connection pool
    pagination.py        # Pagination utilities
    caching_redis.py     # Redis cache manager
    metrics.py           # Request metrics middleware
    cache_invalidation.py # Automatic cache invalidation
    query_optimization.py # Index management + EXPLAIN
    backup.py            # Database backup/restore
    error_handlers.py    # Global error handling
    request_id.py        # X-Request-ID middleware
    audit.py             # Audit logging
    routers/
      activities.py      # Activity endpoints
      auth.py            # Auth endpoints
      dashboard.py       # Monitoring dashboard endpoints
tests/
  test_api.py            # API integration tests
  test_security.py       # Security tests
  test_dashboard.py      # Dashboard endpoint tests
  test_caching_redis.py  # Redis caching tests
  test_phase3.py         # Phase 3 component tests
  test_phase4.py         # Phase 4 security tests
```

## License

MIT

