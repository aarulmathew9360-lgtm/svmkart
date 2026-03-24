import mysql.connector
import sys

def setup_database(password):
    try:
        # Connect to MySQL Server (without database)
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=password
        )
        cursor = conn.cursor()
        
        # Create database if not exists
        cursor.execute("CREATE DATABASE IF NOT EXISTS svmkart")
        print("Database 'svmkart' created or already exists.")
        
        cursor.close()
        conn.close()
        return True
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        setup_database(sys.argv[1])
    else:
        # Default for internal use (Arul936% provided by user)
        setup_database("Arul936%")
