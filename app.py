import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Product, Customer, Invoice, InvoiceItem, Settings, Expense, StockLog
from datetime import datetime, timedelta
import json
import csv
import qrcode
import tempfile
from fpdf import FPDF
from functools import wraps
from io import BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'svmkart-secret-key-12345'
# MySQL URI forroot:Arul936%@localhost/svmkart
# Percent sign (%) must be encoded as %25 in the connection string
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:Arul936%25@localhost/svmkart'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

with app.app_context():
    db.create_all()
    # Check if a user exists, if not create default admin
    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('admin123')
        admin = User(username='admin', password=hashed_pw, role='admin')
        db.session.add(admin)
        db.session.commit()
        print("Default admin created: admin / admin123")
    
    # Initialize default settings if none exist
    if not Settings.query.first():
        default_settings = Settings()
        db.session.add(default_settings)
        db.session.commit()

# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Failed. Please check your username and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- User Management ---
@app.route('/users', methods=['GET', 'POST'])
@login_required
@admin_required
def users():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
        else:
            hashed_pw = generate_password_hash(password)
            new_user = User(username=username, password=hashed_pw, role=role)
            db.session.add(new_user)
            db.session.commit()
            flash(f'User {username} created successfully!', 'success')
        return redirect(url_for('users'))
        
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/user/delete/<int:user_id>')
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Cannot delete yourself!', 'danger')
    else:
        user = User.query.get(user_id)
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('users'))

# --- Dashboard & Analytics ---
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    
    # Calculate today's sales
    today_sales = db.session.query(db.func.sum(Invoice.final_amount)).filter(db.func.date(Invoice.date) == today).scalar() or 0.0
    # Calculate total invoices
    total_invoices = Invoice.query.count()
    # Find low stock products
    low_stock = Product.query.filter(Product.stock <= Product.min_stock).all()
    
    # Get last 7 days of sales for Chart.js
    labels = []
    data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime('%a'))
        sales = db.session.query(db.func.sum(Invoice.final_amount)).filter(db.func.date(Invoice.date) == day).scalar() or 0.0
        data.append(sales)
        
    recent_invoices = Invoice.query.order_by(Invoice.date.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                           today_sales=today_sales, 
                           total_invoices=total_invoices, 
                           low_stock_count=len(low_stock),
                           low_stock_items=low_stock[:5], # Send top 5 items for brief
                           labels=json.dumps(labels),
                           sales_data=json.dumps(data),
                           recent_invoices=recent_invoices)

# --- Products Management ---
@app.route('/products')
@login_required
def products():
    search = request.args.get('search', '')
    if search:
        all_products = Product.query.filter(Product.name.like(f"%{search}%")).all()
    else:
        all_products = Product.query.all()
    return render_template('products.html', products=all_products)

@app.route('/products/import', methods=['POST'])
@login_required
def import_products():
    if 'file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('products'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('products'))
    
    if file and file.filename.endswith('.csv'):
        stream = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(stream)
        
        count = 0
        for row in reader:
            try:
                new_product = Product(
                    name=row['name'],
                    category=row.get('category', 'General'),
                    price=float(row['price']),
                    stock=int(row['stock']),
                    unit=row.get('unit', 'pcs')
                )
                db.session.add(new_product)
                count += 1
            except Exception as e:
                print(f"Error importing row: {e}")
                
        db.session.commit()
        flash(f'Successfully imported {count} products!', 'success')
    else:
        flash('Invalid file format. Please upload a CSV.', 'danger')
        
    return redirect(url_for('products'))

@app.route('/product/add', methods=['POST'])
@login_required
def add_product():
    name = request.form.get('name')
    category = request.form.get('category')
    price = request.form.get('price')
    stock = request.form.get('stock')
    unit = request.form.get('unit')
    
    new_product = Product(name=name, category=category, price=float(price), stock=int(stock), unit=unit)
    db.session.add(new_product)
    db.session.flush()
    
    # Log initial stock
    initial_log = StockLog(product_id=new_product.id, user_id=current_user.id, change_qty=int(stock), reason="INITIAL")
    db.session.add(initial_log)
    
    db.session.commit()
    flash(f'Product {name} added successfully!', 'success')
    return redirect(url_for('products'))

@app.route('/product/edit/<int:product_id>', methods=['POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.name = request.form.get('name')
    product.category = request.form.get('category')
    product.price = float(request.form.get('price'))
    product.stock = int(request.form.get('stock'))
    product.unit = request.form.get('unit')
    
    db.session.commit()
    flash(f'Product {product.name} updated successfully!', 'success')
    return redirect(url_for('products'))

@app.route('/product/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('products'))
@app.route('/customers')
@login_required
def customers():
    search = request.args.get('search', '')
    if search:
        all_customers = Customer.query.filter(Customer.name.like(f"%{search}%")).all()
    else:
        all_customers = Customer.query.all()
    return render_template('customers.html', customers=all_customers)

@app.route('/customer/add', methods=['POST'])
@login_required
def add_customer():
    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    
    new_customer = Customer(name=name, phone=phone, email=email, address=address)
    db.session.add(new_customer)
    db.session.commit()
    return redirect(url_for('customers'))

# --- Billing Engine ---
@app.route('/billing', methods=['GET', 'POST'])
@login_required
def billing():
    if request.method == 'POST':
        # Get data from AJAX/form
        data = request.json
        customer_id = data.get('customer_id')
        customer_id = int(customer_id) if customer_id else None  # Walk-in = None
        items = data.get('items') # List of {product_id, quantity, unit_price}
        discount = float(data.get('discount', 0))
        tax_rate = float(data.get('tax_rate', 0))
        payment_method = data.get('payment_method', 'Cash')
        
        # Generate Invoice No (PREFIX-2023-XXXX)
        settings = Settings.query.first()
        prefix = settings.invoice_prefix if settings else "SVM"
        count = Invoice.query.count() + 1
        invoice_no = f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{count:04d}"
        
        total_amount = 0
        invoice_id = None
        
        try:
            # Create Invoice entry
            new_invoice = Invoice(
                invoice_no=invoice_no,
                customer_id=customer_id,
                user_id=current_user.id,
                discount=discount,
                tax_rate=tax_rate,
                payment_method=payment_method
            )
            db.session.add(new_invoice)
            db.session.flush() # To get ID before commit
            
            for item in items:
                prod_id = item.get('product_id')
                qty = int(item.get('quantity'))
                price = float(item.get('unit_price'))
                subtotal = qty * price
                total_amount += subtotal
                
                # Update stock
                prod = Product.query.get(prod_id)
                if prod:
                    prod.stock -= qty
                
                product = Product.query.get(prod_id)
                # Add to Invoice Items
                bill_item = InvoiceItem(
                    invoice_id=new_invoice.id,
                    product_id=prod_id,
                    quantity=qty,
                    unit_price=price,
                    buy_price=product.buy_price, # Store current cost price
                    subtotal=subtotal
                )
                db.session.add(bill_item)
                
                # Log stock deduction
                stock_log = StockLog(product_id=prod_id, user_id=current_user.id, change_qty=-qty, reason="SALE")
                db.session.add(stock_log)
            
            # Calculate final total
            tax_amount = (total_amount - discount) * (tax_rate / 100)
            final_amount = (total_amount - discount) + tax_amount
            
            new_invoice.total_amount = total_amount
            new_invoice.tax_amount = tax_amount
            new_invoice.final_amount = final_amount
            
            db.session.commit()
            return jsonify({'success': True, 'invoice_id': new_invoice.id, 'invoice_no': invoice_no})
        
        except Exception as e:
            db.session.rollback()
            print(f"Billing Error: {e}")
            return jsonify({'success': False, 'message': str(e)})

    # GET: Load billing page
    all_products = Product.query.all()
    all_customers = Customer.query.all()
    settings = Settings.query.first()
    return render_template('billing.html', products=all_products, customers=all_customers, default_tax=settings.default_tax_rate)

# --- Invoices Management ---
@app.route('/invoices')
@login_required
def invoices():
    search = request.args.get('search', '')
    if search:
        all_invoices = Invoice.query.filter(Invoice.invoice_no.like(f"%{search}%")).order_by(Invoice.date.desc()).all()
    else:
        all_invoices = Invoice.query.order_by(Invoice.date.desc()).all()
    return render_template('invoices.html', invoices=all_invoices)

# --- Expenses Management ---
@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        category = request.form.get('category')
        amount = request.form.get('amount')
        description = request.form.get('description')
        
        new_expense = Expense(category=category, amount=float(amount), description=description)
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense added successfully!', 'success')
        return redirect(url_for('expenses'))
    
    all_expenses = Expense.query.order_by(Expense.date.desc()).all()
    return render_template('expenses.html', expenses=all_expenses)

# --- Reports & Analytics ---
@app.route('/reports')
@login_required
def reports():
    range_type = request.args.get('range', '30days')
    today = datetime.now()
    
    if range_type == '7days':
        start_date = today - timedelta(days=7)
        group_by = db.func.date(Invoice.date)
        label_format = '%b %d'
    elif range_type == 'yearly':
        start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0)
        group_by = db.func.strftime('%Y-%m', Invoice.date)
        label_format = '%b %Y'
    else: # 30days
        start_date = today - timedelta(days=30)
        group_by = db.func.date(Invoice.date)
        label_format = '%b %d'

    # Sales Data
    sales_query = db.session.query(
        group_by.label('period'),
        db.func.sum(Invoice.final_amount).label('total')
    ).filter(Invoice.date >= start_date).group_by('period').order_by('period').all()
    
    # Expense Data
    expense_query = db.session.query(
        group_by.label('period'),
        db.func.sum(Expense.amount).label('total')
    ).filter(Expense.date >= start_date).group_by('period').order_by('period').all()

    # Process Labels & Values
    labels = []
    sales_values = []
    expense_map = {d.period: float(d.total) for d in expense_query}
    
    for d in sales_query:
        if range_type == 'yearly':
            label = datetime.strptime(d.period, '%Y-%m').strftime('%b %Y')
        else:
            label = datetime.strptime(str(d.period), '%Y-%m-%d').strftime('%b %d')
        labels.append(label)
        sales_values.append(float(d.total))

    expense_values = []
    for d in sales_query:
        expense_values.append(expense_map.get(d.period, 0.0))
    
    total_sales = sum(sales_values)
    
    # Accurate Profit Calculation based on (sale_price - buy_price)
    profit_data = db.session.query(
        db.func.sum((InvoiceItem.unit_price - InvoiceItem.buy_price) * InvoiceItem.quantity)
    ).join(Invoice).filter(Invoice.date >= start_date).scalar() or 0.0
    
    total_expenses = db.session.query(db.func.sum(Expense.amount)).filter(Expense.date >= start_date).scalar() or 0.0
    net_profit = profit_data - total_expenses
    
    # Top Products
    top_products = db.session.query(
        Product.name,
        db.func.sum(InvoiceItem.quantity).label('qty')
    ).join(InvoiceItem).group_by(Product.id).order_by(db.desc('qty')).limit(5).all()
    
    return render_template('reports.html', 
                           labels=json.dumps(labels), 
                           sales_data=json.dumps(sales_values),
                           expense_data=json.dumps(expense_values),
                           total_sales=total_sales,
                           total_expenses=total_expenses,
                           net_profit=net_profit,
                           top_products=top_products,
                           current_range=range_type)

@app.route('/inventory/logs')
@login_required
def inventory_logs():
    logs = StockLog.query.order_by(StockLog.date.desc()).all()
    return render_template('inventory_logs.html', logs=logs)

# --- Settings ---
@app.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    store_settings = Settings.query.first()
    if request.method == 'POST':
        store_settings.store_name = request.form.get('store_name')
        store_settings.store_address = request.form.get('store_address')
        store_settings.store_contact = request.form.get('store_contact')
        store_settings.store_email = request.form.get('store_email')
        store_settings.store_website = request.form.get('store_website')
        store_settings.gstin = request.form.get('gstin')
        store_settings.default_tax_rate = float(request.form.get('default_tax_rate'))
        store_settings.currency_symbol = request.form.get('currency_symbol')
        store_settings.invoice_prefix = request.form.get('invoice_prefix')
        store_settings.terms_conditions = request.form.get('terms_conditions')
        store_settings.footer_note = request.form.get('footer_note')
        store_settings.upi_id = request.form.get('upi_id') # Save UPI ID
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html', settings=store_settings)

# --- PDF Generation ---
class PDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 20)
        self.cell(0, 10, 'SVMKART BILLING SYSTEM', 0, 1, 'C')
        self.set_font('helvetica', '', 10)
        self.cell(0, 5, 'Contact: +91 936XXXXXXX | Email: support@svmcart.com', 0, 1, 'C')
        self.ln(10)

@app.route('/invoice/pdf/<int:invoice_id>')
@login_required
def generate_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    settings = Settings.query.first()
    
    pdf = PDF()
    pdf.add_page()
    
    # Store Header (Custom from settings)
    pdf.set_font('helvetica', 'B', 20)
    pdf.cell(0, 10, settings.store_name.upper(), 0, 1, 'C')
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 5, f"Contact: {settings.store_contact} | Email: {settings.store_email}", 0, 1, 'C')
    pdf.cell(0, 5, f"Website: {settings.store_website} | GSTIN: {settings.gstin}", 0, 1, 'C')
    pdf.cell(0, 5, f"Address: {settings.store_address}", 0, 1, 'C')
    pdf.ln(10)
    
    # Invoice Header
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(100, 10, f"Invoice No: {invoice.invoice_no}")
    pdf.cell(0, 10, f"Date: {invoice.date.strftime('%Y-%m-%d')}", 0, 1, 'R')
    
    # Customer Info
    pdf.ln(5)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, "Customer Details:", 0, 1)
    pdf.set_font('helvetica', '', 11)
    if invoice.customer:
        pdf.cell(0, 7, f"Name: {invoice.customer.name}", 0, 1)
        pdf.cell(0, 7, f"Phone: {invoice.customer.phone}", 0, 1)
        pdf.cell(0, 7, f"Address: {invoice.customer.address}", 0, 1)
    else:
        pdf.cell(0, 7, "Walk-in Customer", 0, 1)
    
    # Items Table
    pdf.ln(10)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(10, 10, 'S.N', 1, 0, 'C', 1)
    pdf.cell(90, 10, 'Product Name', 1, 0, 'C', 1)
    pdf.cell(30, 10, 'Qty', 1, 0, 'C', 1)
    pdf.cell(30, 10, 'Price', 1, 0, 'C', 1)
    pdf.cell(30, 10, 'Total', 1, 1, 'C', 1)
    
    pdf.set_font('helvetica', '', 11)
    for i, item in enumerate(invoice.items):
        pdf.cell(10, 10, str(i+1), 1, 0, 'C')
        pdf.cell(90, 10, item.product.name, 1, 0, 'L')
        pdf.cell(30, 10, str(item.quantity), 1, 0, 'C')
        pdf.cell(30, 10, f"{item.unit_price:.2f}", 1, 0, 'R')
        pdf.cell(30, 10, f"{item.subtotal:.2f}", 1, 1, 'R')
    
    # Summary
    pdf.ln(5)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(160, 10, "Subtotal:", 0, 0, 'R')
    pdf.cell(30, 10, f"{invoice.total_amount:.2f}", 0, 1, 'R')
    pdf.cell(160, 10, "Discount:", 0, 0, 'R')
    pdf.cell(30, 10, f"-{invoice.discount:.2f}", 0, 1, 'R')
    pdf.cell(160, 10, f"Tax ({invoice.tax_rate}%):", 0, 0, 'R')
    pdf.cell(30, 10, f"+{invoice.tax_amount:.2f}", 0, 1, 'R')
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(160, 15, "Grand Total:", 0, 0, 'R')
    pdf.cell(30, 15, f"{invoice.final_amount:.2f}", 0, 1, 'R')
    
    # Payment Method label
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(160, 6, "Payment Method:", 0, 0, 'R')
    pdf.set_font('helvetica', '', 10)
    pdf.cell(30, 6, invoice.payment_method, 0, 1, 'R')

    # UPI QR Generator (Dynamic)
    if invoice.payment_method == 'UPI' and settings.upi_id:
        upi_string = f"upi://pay?pa={settings.upi_id}&pn={settings.store_name}&am={invoice.final_amount}&cu=INR&tn={invoice.invoice_no}"
        qr = qrcode.QRCode(box_size=10, border=1)
        qr.add_data(upi_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR to temp file, close it first, then embed in PDF (Windows needs file closed before use)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp_path = tmp.name
                img.save(tmp_path)
            # File is now closed; safe to read and delete on Windows
            pdf.image(tmp_path, x=15, y=pdf.get_y()+2, w=30)
            pdf.ln(35)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
        pdf.set_font('helvetica', 'I', 8)
        pdf.set_xy(15, pdf.get_y()-2)
        pdf.cell(30, 5, "Scan to Pay", 0, 1, 'C')
    
    # Terms & Conditions
    pdf.ln(10)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 5, "Terms & Conditions:", 0, 1)
    pdf.set_font('helvetica', '', 9)
    pdf.multi_cell(0, 5, settings.terms_conditions)
    
    # Footer Note
    pdf.ln(5)
    pdf.set_font('helvetica', 'I', 10)
    pdf.cell(0, 10, settings.footer_note, 0, 1, 'C')
    
    # Save PDF to memory and send
    output = BytesIO()
    pdf_bytes = pdf.output(dest='S')
    output.write(pdf_bytes)
    output.seek(0)
    
    return send_file(output, download_name=f"invoice_{invoice.invoice_no}.pdf", mimetype='application/pdf')

@app.route('/invoice/thermal/<int:invoice_id>')
@login_required
def download_thermal(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    settings = Settings.query.first()
    
    # 80mm width = 80mm. Standard thermal width.
    # We estimate height based on items to avoid cutting off.
    calc_height = 120 + (len(invoice.items) * 10)
    pdf = FPDF(unit='mm', format=(80, calc_height))
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=5)
    
    # Branding
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 8, settings.store_name.upper(), 0, 1, 'C')
    pdf.set_font('helvetica', '', 8)
    pdf.multi_cell(0, 4, settings.store_address, 0, 'C')
    pdf.cell(0, 4, f"GSTIN: {settings.gstin}", 0, 1, 'C')
    pdf.cell(0, 4, f"Ph: {settings.store_contact}", 0, 1, 'C')
    pdf.ln(2)
    pdf.line(5, pdf.get_y(), 75, pdf.get_y())
    pdf.ln(2)
    
    # Invoice Brief
    pdf.set_font('helvetica', 'B', 9)
    pdf.cell(0, 5, f"INV: {invoice.invoice_no}", 0, 1, 'L')
    pdf.set_font('helvetica', '', 8)
    pdf.cell(0, 4, f"Date: {invoice.date.strftime('%d-%m-%Y %H:%M')}", 0, 1, 'L')
    pdf.cell(0, 4, f"Customer: {invoice.customer.name if invoice.customer else 'Walk-in'}", 0, 1, 'L')
    pdf.cell(0, 4, f"By: {invoice.user.username if invoice.user else 'Staff'}", 0, 1, 'L')
    pdf.ln(2)
    
    # Items
    pdf.set_font('helvetica', 'B', 8)
    pdf.cell(35, 5, "Item", 0, 0)
    pdf.cell(10, 5, "Qty", 0, 0, 'C')
    pdf.cell(25, 5, "Total", 0, 1, 'R')
    pdf.line(5, pdf.get_y(), 75, pdf.get_y())
    pdf.ln(1)
    
    pdf.set_font('helvetica', '', 8)
    for item in invoice.items:
        # Wrap long names
        name = item.product.name[:20]
        pdf.cell(35, 5, name, 0, 0)
        pdf.cell(10, 5, str(item.quantity), 0, 0, 'C')
        pdf.cell(25, 5, f"{item.subtotal:.2f}", 0, 1, 'R')
    
    pdf.ln(1)
    pdf.line(5, pdf.get_y(), 75, pdf.get_y())
    pdf.ln(1)
    
    # Totals
    pdf.cell(45, 5, "Subtotal:", 0, 0, 'R')
    pdf.cell(25, 5, f"{invoice.total_amount:.2f}", 0, 1, 'R')
    pdf.cell(45, 5, "Total Tax:", 0, 0, 'R')
    pdf.cell(25, 5, f"{invoice.tax_amount:.2f}", 0, 1, 'R')
    
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(45, 8, "GRAND TOTAL:", 0, 0, 'R')
    pdf.cell(25, 8, f"Rs.{invoice.final_amount:.2f}", 0, 1, 'R')
    
    pdf.cell(25, 5, invoice.payment_method, 0, 1, 'R')

    # UPI QR for Thermal
    if invoice.payment_method == 'UPI' and settings.upi_id:
        upi_string = f"upi://pay?pa={settings.upi_id}&pn={settings.store_name}&am={invoice.final_amount}&cu=INR&tn={invoice.invoice_no}"
        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(upi_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp_path = tmp.name
                img.save(tmp_path)
            # File closed — safe to read on Windows
            pdf.image(tmp_path, x=25, y=pdf.get_y()+2, w=30)
            pdf.ln(35)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    # Footer
    pdf.ln(4)
    pdf.set_font('helvetica', 'I', 8)
    pdf.multi_cell(0, 4, settings.footer_note, 0, 'C')
    pdf.ln(2)
    pdf.cell(0, 5, "*** Thank You ***", 0, 1, 'C')
    
    output = BytesIO()
    pdf_bytes = pdf.output(dest='S')
    output.write(pdf_bytes)
    output.seek(0)
    
    return send_file(output, download_name=f"receipt_{invoice.invoice_no}.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)
