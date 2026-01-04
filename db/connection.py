import os
from databases import Database

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"
database = Database(DATABASE_URL)