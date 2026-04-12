# SVMKART | ULTRA-FAST SYSTEM RESET UTILITY
import os
import sys
import time
import io
from sqlalchemy import text
from werkzeug.security import generate_password_hash

# Force UTF-8 encoding for Windows consoles to prevent UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Try to import from app, if fails, print error and exit
try:
    from app import app, db
    from models import User, Settings
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import app or models. {e}")
    sys.exit(1)

def super_reset():
    print("\n" + "="*50)
    print(f"🚀 SVMKART SYSTEM RESET ENGINE")
    print("="*50)

    # Allow interactive input for Online MySQL URL
    current_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(f"Current DB: {current_uri.split('@')[-1] if '@' in current_uri else 'Local'}")
    
    user_url = input("\n👉 Paste Online MySQL URL (or press Enter to keep current): ").strip()
    if user_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = user_url
        print(f"✅ Switched to Online Target.")

    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    is_online = "localhost" not in db_uri and "127.0.0.1" not in db_uri
    env_name = "🌐 ONLINE DATABASE" if is_online else "💻 LOCAL DATABASE"

    print(f"\n📍 Target: {env_name}")
    print(f"🔗 URI: {db_uri.split('@')[-1] if '@' in db_uri else 'Local'}")
    print("="*50 + "\n")

    if is_online:
        print("⚠️  WARNING: You are about to wipe an ONLINE database!")
        confirm = input("Are you absolutely sure? Type 'YES' to proceed: ")
        if confirm != "YES":
            print("❌ Reset aborted by user.")
            return

    start_time = time.time()
    
    with app.app_context():
        try:
            print("🛡️  Disabling Foreign Key Constraints...")
            db.session.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
            
            # Use raw SQL to drop tables for maximum compatibility
            print("🗑️  Purging all existing data and tables...")
            db.reflect()
            db.drop_all()
            
            print("🏗️  Reconstructing database schema...")
            db.create_all()
            
            print("👤 Initializing Master Administrative account...")
            admin_pass = generate_password_hash('admin123')
            default_admin = User(
                username='admin', 
                password=admin_pass, 
                role='admin',
                phone='9360000000'
            )
            db.session.add(default_admin)
            
            print("⚙️  Configuring default System Settings...")
            default_settings = Settings(
                store_name='SVMKART',
                store_address='123 Main St, City',
                store_contact='+91 936XXXXXXX',
                store_email='support@svmcart.com',
                store_website='www.svmcart.com',
                gstin='',
                upi_id='yourname@upi',
                default_tax_rate=18.0,
                currency_symbol='₹',
                invoice_prefix='SVM',
                terms_conditions='1. Goods once sold cannot be returned.\n2. Warranty terms as per manufacturer.',
                footer_note='Thank you for shopping with SVMKART!'
            )
            db.session.add(default_settings)
            
            print("💾 Committing changes to database...")
            db.session.commit()
            
            print("🔗 Re-enabling safety checks...")
            db.session.execute(text('SET FOREIGN_KEY_CHECKS = 1'))
            
            duration = round(time.time() - start_time, 2)
            print("\n" + "✨"*20)
            print(f"✅ SUCCESS: SYSTEM RESET COMPLETE! ({duration}s)")
            print(f"👉 Default Username: admin")
            print(f"👉 Default Password: admin123")
            print("✨"*20)
            print("\n🚀 System is now ready for a fresh start.")
            
        except Exception as e:
            print(f"\n❌ CRITICAL SYSTEM ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            print("⚠️  Rollback initiated. System state might be inconsistent.")

    input("\nPress Enter to Exit...")

if __name__ == "__main__":
    super_reset()


