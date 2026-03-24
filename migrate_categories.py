import mysql.connector

def migrate():
    try:
        # Re-using the known password Arul936%
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Arul936%",
            database="svmkart"
        )
        cursor = conn.cursor()
        
        # Check if category column exists
        cursor.execute("SHOW COLUMNS FROM product LIKE 'category'")
        result = cursor.fetchone()
        
        if not result:
            print("Adding 'category' column to 'product' table...")
            cursor.execute("ALTER TABLE product ADD COLUMN category VARCHAR(50) DEFAULT 'General' AFTER name")
            conn.commit()
            print("Migration successful: 'category' column added.")
        else:
            print("Column 'category' already exists.")
            
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    migrate()
