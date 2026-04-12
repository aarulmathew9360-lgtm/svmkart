from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='staff') # 'admin' or 'staff'
    phone = db.Column(db.String(20), default='') # Used for Whatsapp report
    profile_image = db.Column(db.String(255), default='default.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    invoices = db.relationship('Invoice', backref='user', lazy=True, foreign_keys='Invoice.user_id')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), default='General')
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False) # Selling Price
    buy_price = db.Column(db.Float, default=0.0) # Purchase Price
    stock = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(20), default='pcs') # kg, pcs, box etc.
    min_stock = db.Column(db.Integer, default=5) # for alerts
    barcode = db.Column(db.String(50), unique=True, index=True) # EAN-13, UPC etc.
    image_url = db.Column(db.String(255), default='') # Path to product image

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    points = db.Column(db.Integer, default=0)
    balance = db.Column(db.Float, default=0.0) # Outstanding credit amount
    invoices = db.relationship('Invoice', backref='customer', lazy=True, foreign_keys='Invoice.customer_id')

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(20), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax_rate = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    final_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='paid') # paid, pending, cancelled
    payment_method = db.Column(db.String(50), default='Cash') # Cash, UPI, Card, COD
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade="all, delete-orphan")

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False) # Selling price
    buy_price = db.Column(db.Float, default=0.0) # Cost price
    subtotal = db.Column(db.Float, nullable=False)
    product = db.relationship('Product') # to access product name easily

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(100), default='SVMKART')
    store_address = db.Column(db.Text, default='123 Main St, City')
    store_contact = db.Column(db.String(20), default='+91 936XXXXXXX')
    store_email = db.Column(db.String(100), default='support@svmcart.com')
    store_website = db.Column(db.String(100), default='www.svmcart.com')
    gstin = db.Column(db.String(20), default='')
    upi_id = db.Column(db.String(100), default='yourname@upi') # Store UPI ID for payments
    default_tax_rate = db.Column(db.Float, default=18.0)
    currency_symbol = db.Column(db.String(10), default='₹')
    invoice_prefix = db.Column(db.String(10), default='SVM')
    terms_conditions = db.Column(db.Text, default='1. Goods once sold cannot be returned.\n2. Warranty as per manufacturer terms.')
    footer_note = db.Column(db.String(200), default='Thank you for shopping with SVMKART!')
    default_printer = db.Column(db.String(20), default='A4') # A4 or Thermal
    store_logo = db.Column(db.String(200), default='') # Path or URL to logo
    loyalty_point_value = db.Column(db.Float, default=1.0) # 1 point = 1 rupee
    loyalty_ratio = db.Column(db.Integer, default=100) # 100 Rs = 1 point

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False) # Rent, Salary, Bill, Stock etc.
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class StockLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    change_qty = db.Column(db.Integer, nullable=False) # Positive for addition, negative for deduction
    reason = db.Column(db.String(100)) # e.g. "SALE", "PURCHASE", "ADJUSTMENT"
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', backref=db.backref('logs', lazy=True))
    user = db.relationship('User', backref=db.backref('stock_logs', lazy=True))

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(20))
    purchases = db.relationship('Purchase', backref='supplier', lazy=True)

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_no = db.Column(db.String(20), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='paid') # paid, pending
    items = db.relationship('PurchaseItem', backref='purchase', lazy=True, cascade="all, delete-orphan")

class PurchaseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    buy_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date())
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='present') # present, leave, half-day
    user = db.relationship('User', backref='attendances')

class Payroll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    base_salary = db.Column(db.Float, default=0.0)
    bonus = db.Column(db.Float, default=0.0)
    deductions = db.Column(db.Float, default=0.0)
    final_pay = db.Column(db.Float, default=0.0)
    is_paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.DateTime)
    user = db.relationship('User', backref='payrolls')
