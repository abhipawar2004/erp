import asyncio
from sqlalchemy import text
from src.db_connect import SessionLocal


async def test_database_connection():
    """Test database connection using SQLAlchemy session"""
    try:
        async with SessionLocal() as session:
            # Test connection by executing a simple query
            await session.execute(text("SELECT 1"))
            print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_database_connection())
