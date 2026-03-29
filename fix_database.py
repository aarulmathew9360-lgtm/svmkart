# MIGRATE START
print("🏁 Starting Database Fix...")
import os
import sys

try:
    from app import app, db
    print("✅ App & DB Imported")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

from sqlalchemy import text

def migrate():
    with app.app_context():
        engine = db.engine
        print(f"🔗 Connected to: {engine.url}")
        
        # List of columns to add
        updates = [
            ("product", "barcode", "VARCHAR(50) UNIQUE"),
            ("settings", "default_printer", "VARCHAR(20) DEFAULT 'A4'"),
            ("settings", "store_logo", "VARCHAR(200) DEFAULT ''")
        ]
        
        for table, column, dtype in updates:
            print(f"🛠️ Checking '{column}' in '{table}'...")
            try:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {dtype}"))
                    conn.commit()
                print(f"✅ Added {column}")
            except Exception as e:
                err = str(e).lower()
                if "duplicate column" in err or "already exists" in err:
                    print(f"ℹ️ {column} already exists.")
                else:
                    print(f"❌ Failed to add {column}: {e}")

        print("\n🚀 DONE! Try running 'python app.py' now.")

if __name__ == "__main__":
    migrate()
