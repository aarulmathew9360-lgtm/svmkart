# SVMKART SUPER FAST FACTORY RESET SCRIPT
print("💣 Initializing Hard Reset...")

import sys
from app import app, db
from models import User, Settings
from werkzeug.security import generate_password_hash
from sqlalchemy import text

def super_reset():
    with app.app_context():
        try:
            print("🛑 Disabling Safety Checks...")
            db.session.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
            
            print("🗑️ Dropping all old tables...")
            db.drop_all()
            
            print("🏗️ Rebuilding fresh database...")
            db.create_all()
            
            print("👤 Creating Master Admin...")
            admin_pass = generate_password_hash('admin123')
            default_admin = User(username='admin', password=admin_pass, role='admin')
            db.session.add(default_admin)
            
            print("⚙️ Initializing Default Settings...")
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
            
            db.session.commit()
            
            print("🔗 Re-enabling Safety Checks...")
            db.session.execute(text('SET FOREIGN_KEY_CHECKS = 1'))
            
            print("\n✅ SUCCESS: SYSTEM RESET COMPLETE!")
            print("👉 Username: admin")
            print("👉 Password: admin123")
            print("\n🚀 You can now run 'python app.py' to start fresh.")
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR: {e}")
            db.session.rollback()

if __name__ == "__main__":
    super_reset()
