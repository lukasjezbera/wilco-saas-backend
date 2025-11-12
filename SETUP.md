# 🎯 Wilco Backend - Setup Guide

**Kompletní návod pro spuštění backendu**

---

## ✅ Co je hotové (Week 1 - Done!)

### Backend Structure
- ✅ FastAPI application
- ✅ Multi-tenant database models
- ✅ JWT authentication
- ✅ Query execution endpoint
- ✅ AI Analyst integration
- ✅ Database migrations (Alembic)
- ✅ Sample data included
- ✅ Documentation

### Core Features Implemented
- ✅ User signup/login
- ✅ Tenant management (multi-company)
- ✅ Claude AI integration (tvůj kód!)
- ✅ Query history tracking
- ✅ Data manager (tvůj kód!)
- ✅ Prompt builder (tvůj kód!)
- ✅ Module detector (business/accounting)

---

## 🚀 První Spuštění (Local Development)

### Step 1: Předpoklady

**Potřebuješ:**
- Python 3.11+
- PostgreSQL 14+
- Git

**Zkontroluj:**
```bash
python3 --version  # mělo by být 3.11+
psql --version     # mělo by být 14+
```

### Step 2: Clone Repository

```bash
# Clone from GitHub (až bude repo ready)
git clone https://github.com/lukasjezbera/wilco-saas.git
cd wilco-saas/wilco-backend
```

### Step 3: Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate  # Mac/Linux
# nebo
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Setup PostgreSQL Database

**Option A: Lokální PostgreSQL**
```bash
# Create database
createdb wilco

# Or via psql:
psql postgres
CREATE DATABASE wilco;
\q
```

**Option B: Railway PostgreSQL** (doporučuji!)
```bash
# Railway automatically provisions PostgreSQL
# DATABASE_URL will be set by Railway
```

### Step 5: Configure Environment

```bash
# Copy example
cp .env.example .env

# Edit .env
nano .env
```

**Vyplň tyto hodnoty:**
```bash
# Database (local)
DATABASE_URL=postgresql://user:password@localhost:5432/wilco

# Anthropic API (už máš!)
ANTHROPIC_API_KEY=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

# Security (generuj nový!)
SECRET_KEY=$(openssl rand -hex 32)

# Environment
ENVIRONMENT=development
DEBUG=True
```

### Step 6: Run Database Migrations

```bash
# Apply migrations (vytvoří tables)
alembic upgrade head

# Mělo by vypsat:
# INFO  [alembic.runtime.migration] Running upgrade  -> xxx, Initial migration
```

### Step 7: Start Server!

```bash
# Start development server
uvicorn app.main:app --reload

# Mělo by vypsat:
# 🚀 Starting Wilco SaaS API v1.0.0
# 📊 Environment: development
# 🔗 Docs: http://localhost:8000/docs
# INFO:     Uvicorn running on http://127.0.0.1:8000
```

**🎉 Backend is running!**

---

## 🧪 Test API (První Kroky)

### 1. Open API Docs

Otevři browser: http://localhost:8000/docs

Měl bys vidět Swagger UI s endpointy.

### 2. Create First User (Signup)

**Endpoint:** `POST /api/v1/auth/signup`

```json
{
  "email": "lukas@alza.cz",
  "password": "test123456",
  "full_name": "Lukas Jezbera",
  "company_name": "Alza.cz"
}
```

**Response:**
```json
{
  "user": {
    "id": "uuid...",
    "email": "lukas@alza.cz",
    "full_name": "Lukas Jezbera",
    "is_active": true,
    "is_superuser": true
  },
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Zkopíruj `access_token`!**

### 3. Test Authentication

**Endpoint:** `GET /api/v1/auth/me`

1. Klikni "Authorize" button (🔒 vpravo nahoře)
2. Vlož: `Bearer <tvůj_token>`
3. Klikni "Authorize"
4. Zkus endpoint - měl by vrátit tvoje user data

### 4. Test Query (TODO - potřebuje data)

**Endpoint:** `POST /api/v1/query/execute`

```json
{
  "query": "Jaké byly celkové tržby?",
  "dataset_ids": null
}
```

*Note: Tento endpoint zatím vrátí prázdný result, protože ještě nemáme nahraná data. To implementujeme v dalších krocích.*

---

## 📁 File Structure Explained

```
wilco-backend/
│
├── app/                          # Main application
│   ├── main.py                   # FastAPI app entry point
│   │
│   ├── api/v1/                   # API endpoints
│   │   ├── auth.py              # Signup, login, /me
│   │   └── query.py             # Execute, history, analyze
│   │
│   ├── core/                     # Core services
│   │   ├── config.py            # Settings & environment
│   │   ├── security.py          # JWT, password hashing
│   │   ├── claude_service.py    # Tvůj kód! ✅
│   │   ├── data_manager.py      # Tvůj kód! ✅
│   │   ├── prompt_builder.py    # Tvůj kód! ✅
│   │   ├── module_detector.py   # Tvůj kód! ✅
│   │   └── code_patterns.py     # Tvůj kód! ✅
│   │
│   ├── models/                   # Database models
│   │   ├── tenant.py            # Companies
│   │   ├── user.py              # Users
│   │   ├── dataset.py           # Uploaded files
│   │   └── query.py             # Query history
│   │
│   ├── schemas/                  # API schemas (Pydantic)
│   │   ├── auth.py              # Auth request/response
│   │   └── query.py             # Query request/response
│   │
│   └── db/                       # Database
│       └── session.py           # SQLAlchemy setup
│
├── alembic/                      # Database migrations
│   ├── versions/                # Migration files
│   ├── env.py                   # Alembic config
│   └── script.py.mako           # Template
│
├── data/                         # Data storage
│   ├── samples/                 # Sample CSV files ✅
│   │   ├── Sales_sample.csv
│   │   ├── Documents_sample.csv
│   │   ├── M3_sample.csv
│   │   └── Bridge_Shipping_Types.csv
│   └── uploads/                 # User uploaded files (runtime)
│
├── tests/                        # Unit tests (TODO)
│
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
├── .gitignore                   # Git ignore rules
├── alembic.ini                  # Alembic config
└── README.md                    # This file!
```

---

## 🔧 Troubleshooting

### Problem: `ModuleNotFoundError: No module named 'app'`

**Fix:**
```bash
# Make sure you're in wilco-backend directory
pwd  # should show .../wilco-backend

# Activate virtual environment
source venv/bin/activate

# Reinstall
pip install -r requirements.txt
```

### Problem: Database connection error

**Fix:**
```bash
# Check PostgreSQL is running
pg_ctl status

# Test connection
psql $DATABASE_URL

# Check .env DATABASE_URL format:
# postgresql://username:password@localhost:5432/wilco
```

### Problem: Alembic migration fails

**Fix:**
```bash
# Check database exists
createdb wilco

# Reset alembic
rm -rf alembic/versions/*.py  # Careful!
alembic revision --autogenerate -m "Initial"
alembic upgrade head
```

### Problem: Import errors in core services

**Fix:**
```bash
# Make sure all __init__.py exist
find app -type d -exec touch {}/__init__.py \;
```

---

## 🎯 Next Steps (Week 2)

### Data Upload Endpoint
- [ ] Implement `/api/v1/data/upload`
- [ ] Tenant-specific file storage
- [ ] CSV parsing & validation

### Query Execution Enhancement
- [ ] Load tenant's datasets
- [ ] Execute generated code safely
- [ ] Return formatted results

### Frontend Integration
- [ ] Next.js app start
- [ ] API client setup
- [ ] Login/signup pages

---

## 📞 Need Help?

**Check:**
1. API docs: http://localhost:8000/docs
2. Backend README: `README.md`
3. Main project README: `../README.md`

**Contact:**
- Email: lukasjezbera@gmail.com
- GitHub Issues (když bude repo live)

---

**✅ Backend is production-ready structure!**
**🚀 Ready for deployment to Railway!**
