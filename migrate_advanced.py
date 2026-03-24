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
        
        # 1. Add buy_price to product
        cursor.execute("SHOW COLUMNS FROM product LIKE 'buy_price'")
        if not cursor.fetchone():
            print("Adding 'buy_price' column to 'product' table...")
            cursor.execute("ALTER TABLE product ADD COLUMN buy_price FLOAT DEFAULT 0.0 AFTER price")
            conn.commit()
        
        # 2. Create stock_log table
        cursor.execute("SHOW TABLES LIKE 'stock_log'")
        if not cursor.fetchone():
            print("Creating 'stock_log' table...")
            cursor.execute("""
                CREATE TABLE stock_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    product_id INT NOT NULL,
                    user_id INT NOT NULL,
                    change_qty INT NOT NULL,
                    reason VARCHAR(100),
                    date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES product(id),
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )
            """)
            conn.commit()
            print("StockLog table created successfully.")
            
        cursor.close()
        conn.close()
        print("Advanced Operations Migration Complete.")
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    migrate()
