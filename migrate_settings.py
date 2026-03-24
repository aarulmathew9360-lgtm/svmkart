import mysql.connector

def migrate():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Arul936%",
            database="svmkart"
        )
        cursor = conn.cursor()
        
        # New columns to add to settings table
        new_columns = [
            ("store_website", "VARCHAR(100) DEFAULT 'www.svmcart.com'"),
            ("gstin", "VARCHAR(20) DEFAULT ''"),
            ("invoice_prefix", "VARCHAR(10) DEFAULT 'SVM'"),
            ("terms_conditions", "TEXT"),
            ("footer_note", "VARCHAR(200) DEFAULT 'Thank you for shopping with SVMKART!'")
        ]
        
        for col_name, col_type in new_columns:
            cursor.execute(f"SHOW COLUMNS FROM settings LIKE '{col_name}'")
            if not cursor.fetchone():
                print(f"Adding '{col_name}' to settings table...")
                cursor.execute(f"ALTER TABLE settings ADD COLUMN {col_name} {col_type}")
                conn.commit()
                
                # Special update for terms_conditions to have default content
                if col_name == "terms_conditions":
                    default_terms = "1. Goods once sold cannot be returned.\n2. Warranty as per manufacturer terms."
                    cursor.execute("UPDATE settings SET terms_conditions = %s WHERE terms_conditions IS NULL OR terms_conditions = ''", (default_terms,))
                    conn.commit()
                
                print(f"Migration successful: '{col_name}' added.")
            else:
                print(f"Column '{col_name}' already exists.")
            
        cursor.close()
        conn.close()
        print("Settings Upgrade Migration Complete.")
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    migrate()
