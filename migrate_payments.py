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

    # Add 'payment_method' to 'invoice' table
    col_name = "payment_method"
    
    cursor.execute(f"SHOW COLUMNS FROM invoice LIKE '{col_name}'")
    if not cursor.fetchone():
        print(f"Adding '{col_name}' to invoice table...")
        cursor.execute(f"ALTER TABLE invoice ADD COLUMN {col_name} VARCHAR(50) DEFAULT 'Cash'")
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
