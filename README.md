# 🚀 Wilco Backend (FastAPI)

**AI-Powered Data Analytics API**

Multi-tenant backend with Claude AI integration for natural language data queries.

---

## 🏗️ Architecture

```
FastAPI Backend
├── Authentication (JWT)
├── Multi-tenant Database
├── Claude AI Integration
├── Query Execution Engine
└── RESTful API
```

---

## 📁 Structure

```
wilco-backend/
├── app/
│   ├── api/v1/          # API endpoints
│   │   ├── auth.py      # Signup, login
│   │   └── query.py     # Query execution
│   ├── core/            # Core services
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── claude_service.py
│   │   └── data_manager.py
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   └── db/              # Database config
├── alembic/             # DB migrations
├── tests/               # Unit tests
└── requirements.txt
```

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy example
cp .env.example .env

# Edit .env with your credentials:
nano .env
```

**Required variables:**
```bash
DATABASE_URL=postgresql://user:pass@localhost/wilco
ANTHROPIC_API_KEY=sk-ant-api03-your-key
SECRET_KEY=your-secret-key
```

### 3. Run Database Migrations

```bash
# Initialize database
alembic upgrade head
```

### 4. Start Development Server

```bash
# Start with auto-reload
uvicorn app.main:app --reload

# Or run directly
python -m app.main
```

**API available at:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 📚 API Endpoints

### Authentication

```bash
# Signup
POST /api/v1/auth/signup
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "John Doe",
  "company_name": "Alza.cz"
}

# Login
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "password123"
}

# Get current user
GET /api/v1/auth/me
Authorization: Bearer <token>
```

### Query Execution

```bash
# Execute query
POST /api/v1/query/execute
Authorization: Bearer <token>
{
  "query": "Jaké byly tržby v lednu 2024?",
  "context_query_id": null,
  "dataset_ids": ["sales", "documents"]
}

# Get history
GET /api/v1/query/history?limit=50&offset=0
Authorization: Bearer <token>

# Get specific query
GET /api/v1/query/{query_id}
Authorization: Bearer <token>

# AI Analyst
POST /api/v1/query/analyze
Authorization: Bearer <token>
{
  "query": "Analyze sales trends",
  "result_data": {...},
  "format_type": "executive"
}
```

---

## 🗄️ Database Schema

### Tables

**tenants**
- Multi-tenant architecture
- Company/organization data

**users**
- User authentication
- Belongs to tenant

**datasets**
- Uploaded CSV/Excel files
- Per-tenant data storage

**query_history**
- Query execution log
- Results cache

---

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app tests/

# Specific test
pytest tests/test_auth.py -v
```

---

## 🚀 Deployment (Railway)

### 1. Install Railway CLI

```bash
npm i -g @railway/cli
```

### 2. Login & Link Project

```bash
railway login
railway link
```

### 3. Set Environment Variables

```bash
railway variables set ANTHROPIC_API_KEY=sk-ant-...
railway variables set SECRET_KEY=your-secret
```

### 4. Deploy

```bash
railway up
```

---

## 🔐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection | Yes |
| `ANTHROPIC_API_KEY` | Claude API key | Yes |
| `SECRET_KEY` | JWT secret | Yes |
| `ENVIRONMENT` | dev/production | No |
| `DEBUG` | Debug mode | No |

---

## 📖 Documentation

- **Interactive API Docs:** `/docs` (Swagger UI)
- **Alternative Docs:** `/redoc` (ReDoc)
- **Health Check:** `/health`

---

## 🛠️ Development

### Code Style

```bash
# Format code
black app/

# Lint
flake8 app/

# Type check
mypy app/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🔧 Troubleshooting

**Database connection error:**
```bash
# Check DATABASE_URL format
# PostgreSQL: postgresql://user:pass@host:5432/db
# Test connection
psql $DATABASE_URL
```

**Import errors:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Alembic issues:**
```bash
# Reset alembic
alembic stamp head
alembic upgrade head
```

---

## 📞 Support

- GitHub Issues
- Email: lukasjezbera@gmail.com

---

**Built with FastAPI, PostgreSQL, and Claude AI** 🚀
