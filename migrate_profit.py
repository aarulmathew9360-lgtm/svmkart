import mysql.connector

try:
    # Connect to MySQL database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Arul936%",
        database="svmkart"
    )
    cursor = conn.cursor()

    # Add 'buy_price' to 'invoice_item' table
    col_name = "buy_price"
    
    cursor.execute(f"SHOW COLUMNS FROM invoice_item LIKE '{col_name}'")
    if not cursor.fetchone():
        print(f"Adding '{col_name}' to invoice_item table...")
        cursor.execute(f"ALTER TABLE invoice_item ADD COLUMN {col_name} FLOAT DEFAULT 0.0")
        conn.commit()
        print(f"Migration successful: '{col_name}' added.")
    else:
        print(f"Column '{col_name}' already exists.")

except mysql.connector.Error as err:
    print(f"Error: {err}")
finally:
    if 'conn' in locals() and conn.is_connected():
        cursor.close()
        conn.close()
