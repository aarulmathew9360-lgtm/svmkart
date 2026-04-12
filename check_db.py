import os
import pymysql
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

def check():
    url = os.environ.get('DATABASE_URL')
    if not url:
        print("❌ No DATABASE_URL found in .env")
        return

    print(f"🔍 Testing connection to: {urlparse(url).hostname}")
    
    try:
        # Parse manually for raw pymysql test
        p = urlparse(url)
        db_name = p.path.lstrip('/')
        password = p.password
        if password:
            from urllib.parse import unquote
            password = unquote(password)
            
        conn = pymysql.connect(
            host=p.hostname,
            user=p.username,
            password=password,
            database=db_name,
            port=p.port or 3306,
            ssl={'ssl_mode': 'REQUIRED'} if 'aivencloud' in url else None
        )
        print("✅ SUCCESS! Connection established.")
        conn.close()
    except Exception as e:
        print(f"❌ CONNECTION FAILED!")
        print(f"Technical Error: {e}")
        print("\nPossible fixes:")
        print("1. Check if the password in .env matches the one in Aiven console.")
        print("2. Go to Aiven -> Allowed IP Addresses -> Add 0.0.0.0/0")
        print("3. Check if the database 'defaultdb' actually exists.")

if __name__ == "__main__":
    check()
