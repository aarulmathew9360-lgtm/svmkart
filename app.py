import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Product, Customer, Invoice, InvoiceItem, Settings, Expense, StockLog, Supplier, Purchase, PurchaseItem, Attendance, Payroll
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
# Database Configuration (Environment Aware)
LOCAL_DB = 'mysql+pymysql://root:Arul936%25@localhost/svmkart'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', LOCAL_DB)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Dynamic DB Auto-Upgrade & Initialization
with app.app_context():
    try:
        # Create tables safely if they don't exist
        db.create_all()
        
        # Initialize default admin if no users exist
        if not User.query.filter_by(username='admin').first():
            admin_pass = generate_password_hash('admin123')
            default_admin = User(username='admin', password=admin_pass, role='admin')
            db.session.add(default_admin)
            
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
                terms_conditions='1. Goods once sold cannot be returned.\n2. Warranty as per manufacturer.',
                footer_note='Thank you for shopping with SVMKART!'
            )
            db.session.add(default_settings)
            db.session.commit()
            print("Successfully initialized fresh database with default Admin.")
    except Exception as e:
        db.session.rollback()
        print(f"Db Initialization skipped/error: {e}")

    try:
        db.session.execute(db.text('ALTER TABLE user ADD COLUMN phone VARCHAR(20) DEFAULT ""'))
        db.session.commit()
    except Exception:
        db.session.rollback()
        
    try:
        db.session.execute(db.text('ALTER TABLE user ADD COLUMN profile_image VARCHAR(255) DEFAULT "default.png"'))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(db.text('ALTER TABLE invoice_item ADD COLUMN buy_price FLOAT DEFAULT 0.0'))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(db.text('ALTER TABLE customer ADD COLUMN balance FLOAT DEFAULT 0.0'))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(db.text('ALTER TABLE product ADD COLUMN image_url VARCHAR(255) DEFAULT ""'))
        db.session.commit()
    except Exception:
        db.session.rollback()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_globals():
    return {
        'db': db,
        'User': User,
        'Settings': Settings,
        'Supplier': Supplier,
        'Purchase': Purchase,
        'datetime': datetime
    }

def wa_format(phone):
    if not phone:
        return ""
    # Strip all non-numeric characters
    clean = "".join(filter(str.isdigit, str(phone)))
    # If it's a 10 digit number, prepend 91.
    if len(clean) == 10:
        return f"91{clean}"
    elif clean.startswith("91") and len(clean) >= 12:
        return clean
    elif clean.startswith("0"):
        return f"91{clean[1:]}"
    return f"91{clean}"  # Fallback prepend 91

@app.template_filter('wa_format')
def wa_format_filter(phone):
    return wa_format(phone)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Database initialization moved to main block for safety

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

@app.route('/profile')
@login_required
def profile():
    today = datetime.now().date()
    
    # Yesterday for comparison or other stats if needed
    
    # 1. Today's Performance
    today_invoices = Invoice.query.filter(
        db.func.date(Invoice.date) == today,
        Invoice.user_id == current_user.id
    ).all()
    today_bills_count = len(today_invoices)
    today_sales = sum(inv.final_amount for inv in today_invoices)
    
    # 2. All-Time Stats
    all_time_invoices = Invoice.query.filter_by(user_id=current_user.id).all()
    total_life_bills = len(all_time_invoices)
    total_life_revenue = sum(inv.final_amount for inv in all_time_invoices)
    
    # 3. Attendance Stats (This month)
    this_month = datetime.now().month
    this_year = datetime.now().year
    month_attendance = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        db.extract('month', Attendance.date) == this_month,
        db.extract('year', Attendance.date) == this_year,
        Attendance.status == 'present'
    ).count()
    
    # 4. Recent Activities (Last 5 Invoices)
    recent_activities = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.date.desc()).limit(5).all()
    
    # 5. User Rank/Level based on sales (Mock Logic)
    rank = "Bronze Seller"
    if total_life_revenue > 50000: rank = "Gold Seller"
    elif total_life_revenue > 10000: rank = "Silver Seller"

    return render_template('profile.html', 
                           today_bills_count=today_bills_count, 
                           today_sales=today_sales,
                           total_life_bills=total_life_bills,
                           total_life_revenue=total_life_revenue,
                           month_attendance=month_attendance,
                           recent_activities=recent_activities,
                           rank=rank,
                           today_date=today.strftime('%B %d, %Y'))

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    new_phone = request.form.get('phone', '').strip()
    new_pass = request.form.get('password', '').strip()
    
    # Fetch user explicitly to ensure session tracks the changes
    user = db.session.get(User, current_user.id)
    
    # Handle optional image upload
    chosen_avatar = request.form.get('chosen_avatar')
    if chosen_avatar:
        user.profile_image = chosen_avatar
        
    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and file.filename != '':
            filename = secure_filename(f"user_{user.id}_{file.filename}")
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'profiles')
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, filename))
            user.profile_image = filename
            
    if new_phone:
        user.phone = new_phone
    if new_pass:
        user.password = generate_password_hash(new_pass)
        
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))

# --- User Management ---
@app.route('/users', methods=['GET', 'POST'])
@login_required
@admin_required
def users():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        phone = request.form.get('phone', '').strip()
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
        else:
            hashed_pw = generate_password_hash(password)
            new_user = User(username=username, password=hashed_pw, role=role, phone=phone)
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
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    thirty_days_ago = today - timedelta(days=30)
    settings = Settings.query.first()
    
    # 1. Sales & Growth
    today_sales = float(db.session.query(db.func.sum(Invoice.final_amount)).filter(db.func.date(Invoice.date) == today).scalar() or 0.0)
    total_invoices = Invoice.query.count()
    
    yesterday_sales = float(db.session.query(db.func.sum(Invoice.final_amount)).filter(db.func.date(Invoice.date) == yesterday).scalar() or 0.0)
    growth_pct = 0.0
    if yesterday_sales > 0:
        growth_pct = ((today_sales - yesterday_sales) / yesterday_sales) * 100
        
    # 2. Monthly Stats
    first_day_of_month = today.replace(day=1)
    monthly_profit = float(db.session.query(db.func.sum((InvoiceItem.unit_price - InvoiceItem.buy_price) * InvoiceItem.quantity))\
        .join(Invoice).filter(db.func.date(Invoice.date) >= first_day_of_month).scalar() or 0.0)
    
    # 3. Inventory Checks
    low_stock_items = Product.query.filter(Product.stock <= Product.min_stock).all()
    low_stock_count = len(low_stock_items)
    
    # 4. Chart Data (7 Days)
    labels = []
    sales_data = []
    profit_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime('%b %d'))
        s = float(db.session.query(db.func.sum(Invoice.final_amount)).filter(db.func.date(Invoice.date) == day).scalar() or 0.0)
        p = float(db.session.query(db.func.sum((InvoiceItem.unit_price - InvoiceItem.buy_price) * InvoiceItem.quantity))\
            .join(Invoice).filter(db.func.date(Invoice.date) == day).scalar() or 0.0)
        sales_data.append(s)
        profit_data.append(p)
        
    # 5. Leaderboards
    # Staff Leaderboard (Last 30 Days Sales per User)
    staff_sales = db.session.query(User.username, db.func.sum(Invoice.final_amount))\
        .join(Invoice).filter(Invoice.date >= thirty_days_ago)\
        .group_by(User.username).order_by(db.func.sum(Invoice.final_amount).desc()).all()
        
    # Top Products
    top_selling = db.session.query(Product.name, db.func.sum(InvoiceItem.quantity))\
        .join(InvoiceItem).join(Invoice)\
        .group_by(Product.name).order_by(db.func.sum(InvoiceItem.quantity).desc()).limit(5).all()
        
    # Top Customers
    top_customers = db.session.query(Customer.name, db.func.sum(Invoice.final_amount))\
        .join(Invoice).group_by(Customer.name)\
        .order_by(db.func.sum(Invoice.final_amount).desc()).limit(5).all()

    return render_template('dashboard.html', 
                           settings=settings,
                           today_sales=today_sales, 
                           total_invoices=total_invoices, 
                           low_stock_count=low_stock_count, 
                           low_stock_items=low_stock_items[:5],
                           growth_pct=growth_pct, 
                           monthly_profit=monthly_profit,
                           labels=json.dumps(labels),
                           sales_data=json.dumps(sales_data),
                           profit_data=json.dumps(profit_data),
                           top_selling=top_selling,
                           top_customers=top_customers,
                           staff_sales=staff_sales)

# --- Products Management ---
@app.route('/products')
@login_required
def products():
    search = request.args.get('search', '')
    if search:
        all_products = Product.query.filter(
            db.or_(
                Product.name.like(f"%{search}%"), 
                Product.barcode == search,
                Product.category.like(f"%{search}%")
            )
        ).all()
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
    barcode = request.form.get('barcode', '').strip()
    
    # Check if barcode already exists
    if barcode and Product.query.filter_by(barcode=barcode).first():
        flash(f'Barcode {barcode} is already assigned to another product!', 'danger')
        return redirect(url_for('products'))
        
    # Handle image upload
    image_url = ''
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            filename = secure_filename(f"prod_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join('static/uploads/products', filename))
            image_url = f'uploads/products/{filename}'

    new_product = Product(
        name=name, 
        category=category, 
        price=float(price), 
        stock=int(stock), 
        unit=unit,
        barcode=barcode if barcode else None,
        image_url=image_url
    )
    db.session.add(new_product)
    db.session.flush()
    
    # If no barcode provided, generate one: SVM[ID]
    if not new_product.barcode:
        new_product.barcode = f"890{new_product.id:09d}" # Mock EAN prefix
        
    # Log initial stock
    initial_log = StockLog(product_id=new_product.id, user_id=current_user.id, change_qty=int(stock), reason="INITIAL")
    db.session.add(initial_log)
    
    db.session.commit()
    flash(f'Product {name} added with Barcode: {new_product.barcode}', 'success')
    return redirect(url_for('products'))

@app.route('/product/generate_missing_barcodes')
@login_required
@admin_required
def generate_missing_barcodes():
    products = Product.query.filter(Product.barcode == None).all()
    count = 0
    for p in products:
        p.barcode = f"890{p.id:09d}" # Standard SVM barcode
        count += 1
    db.session.commit()
    flash(f"Generated barcodes for {count} products!", "success")
    return redirect(url_for('products'))

@app.route('/product/edit/<int:product_id>', methods=['POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.name = request.form.get('name')
    product.category = request.form.get('category')
    product.barcode = request.form.get('barcode')
    product.price = float(request.form.get('price'))
    product.stock = int(request.form.get('stock'))
    product.unit = request.form.get('unit')
    
    # Handle image update
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            filename = secure_filename(f"prod_{product.id}_{file.filename}")
            file.save(os.path.join('static/uploads/products', filename))
            product.image_url = f'uploads/products/{filename}'
    
    db.session.commit()
    flash(f'Product {product.name} updated successfully!', 'success')
    return redirect(url_for('products'))

@app.route('/product/stock/update', methods=['POST'])
@login_required
def quick_stock_update():
    data = request.json
    product_id = data.get('product_id')
    change = int(data.get('change', 0))
    
    product = Product.query.get(product_id)
    if product:
        product.stock += change
        # Log the adjustment
        log = StockLog(
            product_id=product.id,
            user_id=current_user.id,
            change_qty=change,
            reason='Quick Adjustment'
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': True, 'new_stock': product.stock})
    return jsonify({'success': False, 'message': 'Product not found'})

@app.route('/product/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('Product not found!', 'danger')
        return redirect(url_for('products'))
        
    try:
        # Delete stock logs first to satisfy FK constraints
        StockLog.query.filter_by(product_id=product.id).delete()
        
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Cannot delete this product as it is linked to past invoices or transactions.', 'danger')
        
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
        # Safely convert to int if it's a numeric string, otherwise None (Walk-in)
        if customer_id and str(customer_id).strip() != "":
            try:
                customer_id = int(customer_id)
            except ValueError:
                customer_id = None
        else:
            customer_id = None
        items = data.get('items') # List of {product_id, quantity, unit_price}
        discount = float(data.get('discount', 0))
        tax_rate = float(data.get('tax_rate', 0))
        payment_method = data.get('payment_method', 'Cash')
        redeem_points = data.get('redeem_points', False)
        
        # Generate Invoice No (PREFIX-2023-XXXX)
        settings = Settings.query.first()
        prefix = settings.invoice_prefix if settings else "SVM"
        # Get next ID safely instead of simple count
        max_id = db.session.query(db.func.max(Invoice.id)).scalar() or 0
        count = max_id + 1
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
                
                # Log stock deduction
                stock_log = StockLog(product_id=prod_id, user_id=current_user.id, change_qty=-qty, reason="SALE")
                db.session.add(stock_log)
                
                # Add to Invoice Items
                product_item = db.session.get(Product, prod_id)
                cost_price = product_item.buy_price if product_item else 0.0
                
                bill_item = InvoiceItem(
                    invoice_id=new_invoice.id,
                    product_id=prod_id,
                    quantity=qty,
                    unit_price=price,
                    buy_price=cost_price, 
                    subtotal=subtotal
                )
                db.session.add(bill_item)
            
            # Calculate final total
            tax_amount = (total_amount - discount) * (tax_rate / 100)
            final_amount = (total_amount - discount) + tax_amount
            
            new_invoice.total_amount = total_amount
            new_invoice.tax_amount = tax_amount
            
            # Loyalty Points Logic
            if customer_id and settings:
                customer = db.session.get(Customer, customer_id)
                if customer:
                    if redeem_points:
                        points_to_money = customer.points * (settings.loyalty_point_value or 0)
                        discount += points_to_money
                        customer.points = 0
                    
                    # Update credit balance if payment is 'Credit'
                    if payment_method == 'Credit':
                        customer.balance = (customer.balance or 0) + final_amount
                    
                    # Recalculate tax with new discount if points were redeemed
                    tax_amount = (total_amount - discount) * (tax_rate / 100)
                    final_amount = (total_amount - discount) + tax_amount
                    
                    # Reward points based on final amount
                    if settings.loyalty_ratio and settings.loyalty_ratio > 0:
                        reward_points = int(final_amount / settings.loyalty_ratio)
                        customer.points += reward_points
                
            new_invoice.final_amount = final_amount
            new_invoice.discount = discount # update discount if points were redeemed
            
            db.session.commit()
            
            customer_phone = ""
            if new_invoice.customer:
                customer_phone = new_invoice.customer.phone
                
            store_name = settings.store_name if settings else "SVMKART"
            
            return jsonify({
                'success': True, 
                'invoice_id': new_invoice.id, 
                'invoice_no': invoice_no,
                'customer_phone': wa_format(customer_phone),
                'final_amount': final_amount,
                'store_name': store_name,
                'upi_id': settings.upi_id if settings else ""
            })
        
        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc() # This will show the real error in your terminal!
            return jsonify({'success': False, 'message': f"Engine Error: {str(e)}"})

    # GET: Load billing page
    all_products = Product.query.all()
    all_customers = Customer.query.all()
    settings = Settings.query.first()
    return render_template('billing.html', products=all_products, customers=all_customers, default_tax=settings.default_tax_rate, settings=settings)

# --- Credit Book / Kadaa Management ---
@app.route('/credit-book')
@login_required
def credit_book():
    # Only customers with balance > 0
    debtors = Customer.query.filter(Customer.balance > 0).order_by(Customer.balance.desc()).all()
    total_outstanding = db.session.query(db.func.sum(Customer.balance)).scalar() or 0.0
    return render_template('credit_book.html', debtors=debtors, total_outstanding=total_outstanding)

@app.route('/customer/payment', methods=['POST'])
@login_required
def record_customer_payment():
    customer_id = request.form.get('customer_id')
    amount = float(request.form.get('amount', 0))
    payment_method = request.form.get('payment_method', 'Cash')
    
    customer = db.session.get(Customer, customer_id)
    if customer:
        customer.balance -= amount
        if customer.balance < 0:
            customer.balance = 0
            
        # Create a dummy invoice for payment entry if needed, but for now just update balance
        db.session.commit()
        flash(f'Payment of ₹{amount} recorded for {customer.name}!', 'success')
        
    return redirect(url_for('credit_book'))

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
        group_by_invoice = db.func.date(Invoice.date)
        group_by_expense = db.func.date(Expense.date)
        label_format = '%b %d'
    elif range_type == 'yearly':
        start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0)
        group_by_invoice = db.func.strftime('%Y-%m', Invoice.date)
        group_by_expense = db.func.strftime('%Y-%m', Expense.date)
        label_format = '%b %Y'
    else: # 30days
        start_date = today - timedelta(days=30)
        group_by_invoice = db.func.date(Invoice.date)
        group_by_expense = db.func.date(Expense.date)
        label_format = '%b %d'

    # Sales Data
    sales_query = db.session.query(
        group_by_invoice.label('period'),
        db.func.sum(Invoice.final_amount).label('total')
    ).filter(Invoice.date >= start_date).group_by('period').order_by('period').all()
    
    # Expense Data
    expense_query = db.session.query(
        group_by_expense.label('period'),
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
        store_settings.upi_id = request.form.get('upi_id')
        store_settings.default_printer = request.form.get('default_printer')
        store_settings.store_logo = request.form.get('store_logo')
        
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))
    
    all_users = User.query.all()
    return render_template('settings.html', settings=store_settings, users=all_users)

@app.route('/settings/staff/add', methods=['POST'])
@login_required
@admin_required
def add_staff():
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'staff')
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists!', 'danger')
    else:
        new_user = User(username=username, password=generate_password_hash(password), role=role)
        db.session.add(new_user)
        db.session.commit()
        flash(f'Staff {username} added successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/staff/delete/<int:user_id>')
@login_required
@admin_required
def delete_staff(user_id):
    if current_user.id == user_id:
        flash('You cannot delete yourself!', 'danger')
    else:
        user = User.query.get_or_404(user_id)
        if user.username == 'admin':
            flash('Cannot delete the root admin!', 'danger')
        else:
            db.session.delete(user)
            db.session.commit()
            flash('Staff member removed.', 'success')
    return redirect(url_for('settings'))

# --- Staff Attendance & Payroll ---
@app.route('/hr')
@login_required
@admin_required
def hr_management():
    attendances = Attendance.query.order_by(Attendance.date.desc()).all()
    payrolls = Payroll.query.order_by(Payroll.year.desc(), Payroll.month.desc()).all()
    return render_template('hr.html', attendances=attendances, payrolls=payrolls)

@app.route('/attendance')
@login_required
def attendance_page():
    # Only show current user's attendance log
    attendances = Attendance.query.filter_by(user_id=current_user.id).order_by(Attendance.date.desc()).all()
    today = datetime.now().date()
    today_status = Attendance.query.filter_by(user_id=current_user.id, date=today).first()
    return render_template('attendance.html', attendances=attendances, today_status=today_status)

@app.route('/attendance/mark')
@login_required
def mark_attendance():
    today = datetime.now().date()
    attendance = Attendance.query.filter_by(user_id=current_user.id, date=today).first()
    
    if not attendance:
        # Check-in
        new_attendance = Attendance(user_id=current_user.id, date=today, check_in=datetime.utcnow(), status='present')
        db.session.add(new_attendance)
        flash('Checked-in successfully! Have a great day.', 'success')
    elif not attendance.check_out:
        # Check-out
        attendance.check_out = datetime.utcnow()
        flash('Checked-out successfully! See you tomorrow.', 'success')
    else:
        flash('You have already completed your attendance for today.', 'info')
        
    db.session.commit()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/payroll/generate', methods=['POST'])
@login_required
@admin_required
def generate_payroll():
    user_id = request.form.get('user_id')
    month = int(request.form.get('month'))
    year = int(request.form.get('year'))
    base = float(request.form.get('base_salary', 0))
    bonus = float(request.form.get('bonus', 0))
    deduct = float(request.form.get('deductions', 0))
    
    # Check if already exists
    existing = Payroll.query.filter_by(user_id=user_id, month=month, year=year).first()
    if existing:
        flash('Payroll already generated for this month/year.', 'warning')
        return redirect(url_for('settings'))
        
    final = base + bonus - deduct
    new_payroll = Payroll(
        user_id=user_id, month=month, year=year, 
        base_salary=base, bonus=bonus, deductions=deduct, 
        final_pay=final, is_paid=False
    )
    db.session.add(new_payroll)
    db.session.commit()
    flash('Payroll record created successfully.', 'success')
    return redirect(url_for('settings'))

@app.route('/payroll/pay/<int:payroll_id>')
@login_required
@admin_required
def pay_staff(payroll_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    payroll.is_paid = True
    payroll.payment_date = datetime.utcnow()
    
    # Add to internal expenses
    expense = Expense(
        category='Salary',
        amount=payroll.final_pay,
        description=f"Salary for {payroll.user.username} - {payroll.month}/{payroll.year}",
        date=datetime.utcnow()
    )
    db.session.add(expense)
    db.session.commit()
    flash(f'Payment of ₹{payroll.final_pay} marked as completed.', 'success')
    return redirect(url_for('settings'))
    
@app.route('/settings/reset', methods=['POST'])
@login_required
@admin_required
def reset_factory():
    try:
        # Fast Reset: Direct SQL for performance & stability
        db.session.execute(db.text('SET FOREIGN_KEY_CHECKS = 0'))
        
        # 1. Clear all transaction & master data
        tables = ['invoice_item', 'purchase_item', 'stock_log', 'payroll', 'attendance', 
                  'invoice', 'purchase', 'expense', 'customer', 'supplier', 'product']
        for table in tables:
            db.session.execute(db.text(f'DELETE FROM {table}'))
        
        # 2. Keep only the root admin
        db.session.execute(db.text("DELETE FROM user WHERE username != 'admin'"))
        
        # 3. Reset settings to brand new defaults
        settings = Settings.query.first()
        if settings:
            settings.store_name = 'SVMKART'
            settings.store_address = '123 Main St, City'
            settings.store_contact = '+91 936XXXXXXX'
            settings.store_email = 'support@svmcart.com'
            settings.store_website = 'www.svmcart.com'
            settings.gstin = ''
            settings.upi_id = 'yourname@upi'
            settings.default_tax_rate = 18.0
            settings.currency_symbol = '₹'
            settings.invoice_prefix = 'SVM'
            settings.terms_conditions = '1. Goods once sold cannot be returned.\n2. Warranty as per manufacturer terms.'
            settings.footer_note = 'Thank you for shopping with SVMKART!'
            
        # 4. Success and Security reset
        db.session.execute(db.text('SET FOREIGN_KEY_CHECKS = 1'))
        db.session.commit()
        
        logout_user() # Force logout to re-sync
        flash('SYSTEM HARD RESET SUCCESSFUL! Password reset to admin123', 'success')
        return redirect(url_for('login'))
        
    except Exception as e:
        db.session.rollback()
        db.session.execute(db.text('SET FOREIGN_KEY_CHECKS = 1'))
        flash(f'Error during reset: {str(e)}', 'danger')
        return redirect(url_for('settings'))
        
    return redirect(url_for('settings'))

@app.route('/settings/export/products')
@login_required
def export_products():
    products = Product.query.all()
    output = BytesIO()
    # Create CSV
    header = ['ID', 'Name', 'Category', 'Price', 'Stock', 'Unit', 'Buy Price']
    data = [[p.id, p.name, p.category, p.price, p.stock, p.unit, p.buy_price] for p in products]
    
    csv_content = ",".join(header) + "\n"
    for row in data:
        csv_content += ",".join([str(val) for val in row]) + "\n"
        
    output.write(csv_content.encode('utf-8'))
    output.seek(0)
    
    return send_file(output, download_name=f"products_export_{datetime.now().strftime('%Y%m%d')}.csv", mimetype='text/csv')

@app.route('/settings/backup/sql')
@login_required
@admin_required
def backup_database():
    # Since we use mysql, we can try to use mysqldump if available
    # Or for a simpler cross-platform approach, we can dump to JSON
    # But let's try a simple SQL-like format manually if mysqldump isn't easy
    
    # Actually, let's just use the 'mysql-connector' to get table info and dump
    # For now, let's provide a 'Backup initiated' message and potentially a simple JSON dump
    all_data = {
        'products': [p.__dict__ for p in Product.query.all()],
        'customers': [c.__dict__ for c in Customer.query.all()],
        'settings': [s.__dict__ for s in Settings.query.all()]
    }
    # Remove SQLAlchemy overhead from dict
    for key in all_data:
        for item in all_data[key]:
            item.pop('_sa_instance_state', None)
            # Handle datetime if any (settings doesn't have it, but for future)
            
    output = BytesIO()
    output.write(json.dumps(all_data, indent=4).encode('utf-8'))
    output.seek(0)
    
    return send_file(output, download_name=f"svmkart_backup_{datetime.now().strftime('%Y%m%d')}.json", mimetype='application/json')

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

# --- Supplier & Inward Management ---
@app.route('/suppliers', methods=['GET', 'POST'])
@login_required
def suppliers():
    if request.method == 'POST':
        name = request.form.get('name')
        contact = request.form.get('contact')
        address = request.form.get('address')
        gstin = request.form.get('gstin')
        
        new_supplier = Supplier(name=name, contact=contact, address=address, gstin=gstin)
        db.session.add(new_supplier)
        db.session.commit()
        flash('Supplier added successfully!', 'success')
        return redirect(url_for('suppliers'))
        
    all_suppliers = Supplier.query.all()
    return render_template('suppliers.html', suppliers=all_suppliers)

@app.route('/inward', methods=['GET', 'POST'])
@login_required
def inward():
    if request.method == 'POST':
        data = request.json
        supplier_id = data.get('supplier_id')
        items = data.get('items') # List of {product_id, quantity, buy_price}
        
        # Generate unique Purchase No safely
        max_p_id = db.session.query(db.func.max(Purchase.id)).scalar() or 0
        purchase_no = f"PUR-{datetime.now().strftime('%Y%m%d')}-{max_p_id + 1:04d}"
        
        try:
            new_purchase = Purchase(purchase_no=purchase_no, supplier_id=supplier_id)
            db.session.add(new_purchase)
            db.session.flush()
            
            total_amount = 0
            for item in items:
                pid = item.get('product_id')
                qty = int(item.get('quantity'))
                buy_price = float(item.get('buy_price'))
                subtotal = qty * buy_price
                total_amount += subtotal
                
                # Update product stock & cost price
                product = Product.query.get(pid)
                if product:
                    product.stock += qty
                    product.buy_price = buy_price # Update to latest cost price
                
                p_item = PurchaseItem(
                    purchase_id=new_purchase.id,
                    product_id=pid,
                    quantity=qty,
                    buy_price=buy_price,
                    subtotal=subtotal
                )
                db.session.add(p_item)
                
                # Log stock addition
                log = StockLog(product_id=pid, user_id=current_user.id, change_qty=qty, reason="PURCHASE")
                db.session.add(log)
            
            new_purchase.total_amount = total_amount
            
            # Record as an expense automatically
            expense = Expense(
                category='Stock Purchase',
                amount=total_amount,
                description=f"Inward Stock Purchase: {purchase_no}",
                date=datetime.utcnow()
            )
            db.session.add(expense)
            
            db.session.commit()
            return jsonify({'success': True, 'purchase_no': purchase_no})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
            
    all_suppliers = Supplier.query.all()
    all_products = Product.query.all()
    return render_template('inward.html', suppliers=all_suppliers, products=all_products)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)