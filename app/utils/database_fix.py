"""
Database fixes and migrations
Run on startup to ensure database schema is correct
"""
from sqlalchemy import text
from app.core.database import engine


def apply_database_fixes():
    """Apply database schema fixes on startup"""
    
    fixes = [
        {
            "name": "Make tenant_id nullable in query_history",
            "sql": "ALTER TABLE query_history ALTER COLUMN tenant_id DROP NOT NULL;"
        }
    ]
    
    with engine.connect() as conn:
        for fix in fixes:
            try:
                print(f"🔧 Applying fix: {fix['name']}")
                conn.execute(text(fix['sql']))
                conn.commit()
                print(f"✅ Fix applied successfully")
            except Exception as e:
                # Fix might already be applied or not needed
                print(f"⚠️ Fix skipped (probably already applied): {e}")
                conn.rollback()


if __name__ == "__main__":
    apply_database_fixes()
