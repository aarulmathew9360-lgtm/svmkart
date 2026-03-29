import mysql.connector

# Use the credentials from your app.py
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "Arul936%25", # Percent-encoded password needs to be decoded for mysql-connector
    "database": "svmkart"
}

def fix():
    print("Connecting to MySQL...")
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        print("Fixing tables...")
        
        # 1. Product Barcode
        try:
            cursor.execute("ALTER TABLE product ADD COLUMN barcode VARCHAR(50) UNIQUE")
            print("- Added 'barcode' to product")
        except Exception as e:
            print("- 'barcode' status:", e)

        # 2. Settings Default Printer
        try:
            cursor.execute("ALTER TABLE settings ADD COLUMN default_printer VARCHAR(20) DEFAULT 'A4'")
            print("- Added 'default_printer' to settings")
        except Exception as e:
            print("- 'default_printer' status:", e)

        # 3. Settings Store Logo
        try:
            cursor.execute("ALTER TABLE settings ADD COLUMN store_logo VARCHAR(200) DEFAULT ''")
            print("- Added 'store_logo' to settings")
        except Exception as e:
            print("- 'store_logo' status:", e)

        conn.commit()
        cursor.close()
        conn.close()
        print("\n✅ OK! Database is now updated.")
        
    except Exception as e:
        print("❌ Error connecting to database:", e)
        print("Please check your MySQL username and password.")

if __name__ == "__main__":
    fix()
