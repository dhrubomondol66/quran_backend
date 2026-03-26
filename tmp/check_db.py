from sqlalchemy import create_engine, inspect
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

columns = inspector.get_columns('ayahs')
for column in columns:
    print(f"Column: {column['name']}, Type: {column['type']}")
