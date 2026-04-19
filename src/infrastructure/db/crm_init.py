"""
CRM database initialization.

Creates CRM tables via Supabase PostgreSQL schema.
Tables are created by sql/supabase_schema.sql (applied via ``make init-supabase``).
This module provides helpers to verify the schema is present.
"""

from loguru import logger
from sqlalchemy import text
from src.infrastructure.db.sql_client import get_sql_engine


def init_crm_schema():
    """
    Verify CRM schema exists in Supabase PostgreSQL.

    CRM tables are created as part of the full Supabase schema
    (``supabase_schema.sql``).  This function is kept for backward
    compatibility and simply logs a confirmation.
    """
    engine = get_sql_engine()

    if check_crm_schema():
        logger.info("✓ CRM schema already exists in Supabase")
    else:
        logger.warning(
            "⚠️  CRM tables missing — run 'make init-supabase' to create them"
        )


def check_crm_schema() -> bool:
    """
    Check if all required CRM tables exist in PostgreSQL.

    Returns:
        True if all required tables exist
    """
    engine = get_sql_engine()
    required_tables = [
        "departments", "specialties", "doctors", "staff", 
        "patients", "appointments", "admissions", "diagnoses", 
        "lab_orders", "prescriptions", "billing_invoices", "payments"
    ]

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
                  AND tablename IN (
                      'departments', 'specialties', 'doctors', 'staff', 
                      'patients', 'appointments', 'admissions', 'diagnoses', 
                      'lab_orders', 'prescriptions', 'billing_invoices', 'payments'
                  )
            """)
        )
        existing = {row[0] for row in result}

    missing = set(required_tables) - existing

    if missing:
        logger.warning(f"Missing CRM tables: {missing}")
        return False

    logger.info(f"✓ All CRM tables exist: {existing}")
    return True


def get_schema_for_prompt(schema_path: str = "data/schema.sql") -> str:
    """
    Loads the database schema from a SQL file for LLM prompts.
    
    Args:
        schema_path: Path to the .sql file.
        
    Returns:
        The schema definition as a string.
    """
    import os
    if not os.path.exists(schema_path):
        logger.error(f"Schema file not found at {schema_path}")
        return "Error: Schema definition missing."

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Clean up: remove DROP TABLE and comments to save tokens
            lines = [
                l for l in content.splitlines() 
                if not l.strip().upper().startswith("DROP TABLE") 
                and not l.strip().startswith("--")
            ]
            return "\n".join(lines).strip()
    except Exception as e:
        logger.error(f"Failed to load schema: {e}")
        return f"Error loading schema: {e}"


if __name__ == "__main__":
    if check_crm_schema():
        logger.success("✓ CRM schema already exists")
    else:
        logger.warning("⚠️  CRM tables missing — run 'make init-supabase'")
