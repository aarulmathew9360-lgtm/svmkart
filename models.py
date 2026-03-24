from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='staff') # 'admin' or 'staff'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
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
