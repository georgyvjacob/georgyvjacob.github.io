from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from helpers import login_required
from weasyprint import HTML
import io

app = Flask(__name__)
app.secret_key = '814843'
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


db = SQL("sqlite:///data.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    user_id = session["user_id"]

    # Default sorting and filtering parameters
    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "descending")
    transaction_type = request.args.get("type", "all")
    account = request.args.get("account", "all")

    # base SQL query
    query = "SELECT * FROM transactions WHERE user_id = ?"
    params = [user_id]

    # Applying filtering conditions
    if transaction_type != "all":
        query += " AND type = ?"
        params.append(transaction_type)
    if account != "all":
        query += " AND account = ?"
        params.append(account)

    # Applying the sorting
    order_by_clause = f"{sort_by} {'ASC' if order == 'ascending' else 'DESC'}"
    query += f" ORDER BY {order_by_clause}"

    # Executing the query
    transactions = db.execute(query, *params)

    # Balance calculations
    cash_r = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'Receipt' AND account = 'Cash' AND user_id = ?", user_id)[0]['COALESCE(SUM(amount), 0)']
    cash_p = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'Payment' AND account = 'Cash' AND user_id = ?", user_id)[0]['COALESCE(SUM(amount), 0)']
    bank_r = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'Receipt' AND account = 'Bank' AND user_id = ?", user_id)[0]['COALESCE(SUM(amount), 0)']
    bank_p = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'Payment' AND account = 'Bank' AND user_id = ?", user_id)[0]['COALESCE(SUM(amount), 0)']

    cash_balance = cash_r - cash_p
    bank_balance = bank_r - bank_p
    total = cash_balance + bank_balance

    # Get user's name
    row = db.execute("SELECT name FROM users WHERE user_id = ?", user_id)
    name = row[0]['name'] if row else None

    return render_template("index.html", name=name, transactions=transactions, cash_balance=cash_balance, bank_balance=bank_balance, total=total, sort_by=sort_by, order=order, transaction_type=transaction_type, account=account)


@app.route('/export_pdf')
@login_required
def print_transactions():
    user_id = session["user_id"]
    current_date = datetime.now().strftime("%Y-%m-%d")
    # Default sorting and filtering parameters
    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "descending")
    transaction_type = request.args.get("type", "all")
    account = request.args.get("account", "all")

    # base SQL query
    query = "SELECT * FROM transactions WHERE user_id = ?"
    params = [user_id]

    # Applying filtering conditions
    if transaction_type != "all":
        query += " AND type = ?"
        params.append(transaction_type)
    if account != "all":
        query += " AND account = ?"
        params.append(account)

    # Applying sorting
    order_by_clause = f"{sort_by} {'ASC' if order == 'ascending' else 'DESC'}"
    query += f" ORDER BY {order_by_clause}"

    # Executing the query
    transactions = db.execute(query, *params)

    row = db.execute("SELECT name FROM users WHERE user_id = ?", user_id)
    cash_r = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'Receipt' AND account = 'Cash' AND user_id = ?", user_id)[0]['COALESCE(SUM(amount), 0)']
    cash_p = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'Payment' AND account = 'Cash' AND user_id = ?", user_id)[0]['COALESCE(SUM(amount), 0)']
    bank_r = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'Receipt' AND account = 'Bank' AND user_id = ?", user_id)[0]['COALESCE(SUM(amount), 0)']
    bank_p = db.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'Payment' AND account = 'Bank' AND user_id = ?", user_id)[0]['COALESCE(SUM(amount), 0)']

    name = row[0]['name'] if row else None

    cash_balance = cash_r - cash_p
    bank_balance = bank_r - bank_p
    total = cash_balance + bank_balance

    # Passing the values for printing as a PDF
    html = render_template('print_transactions.html',sort_by=sort_by, order=order, transaction_type=transaction_type, account=account, name=name, transactions=transactions, cash_balance=cash_balance, bank_balance=bank_balance, total=total, current_date=current_date)
    pdf_file = io.BytesIO()
    HTML(string=html).write_pdf(pdf_file)
    pdf_file.seek(0)
    return send_file(pdf_file, download_name=f"{name}'s  Day Book.pdf", as_attachment=True)


@app.route('/print_voucher/<int:payment_id>')
@login_required
def print_voucher(payment_id):
    user_id = session["user_id"]
    current_date = datetime.now().strftime("%Y-%m-%d")
    # Fetch the specific payment
    payments = db.execute("SELECT * FROM payments WHERE id = ? AND user_id = ? AND due_date IS NULL", payment_id, user_id)

    if not payment:
        return "Payment not found", 404

    name_row = db.execute("SELECT name FROM users WHERE user_id = ?", user_id)
    name = name_row[0]['name'] if name_row else None

    html = render_template('print_voucher.html', name=name, payments=payments, current_date=current_date)
    pdf_file = io.BytesIO()
    HTML(string=html).write_pdf(pdf_file)
    pdf_file.seek(0)
    return send_file(pdf_file, download_name="Voucher.pdf", as_attachment=True)


@app.route("/register", methods=["POST", "GET"])
def register():
    session.clear()
    form_data = {}
    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        pin = request.form.get("pin")
        rows = db.execute("SELECT * FROM users WHERE username = ?", (username,))
        if not name and not username and not password and not confirmation and not pin:
            flash("All fields are required!", 'error')
        elif not name:
            flash("Name required!", 'error')
        elif not username:
            flash("Username required!", 'error')
        elif not password:
            flash("Password required!", 'error')
        elif not confirmation:
            flash("Please confirm your Password!", 'error')
        elif not pin:
            flash("PIN required!", 'error')
        elif len(rows) != 0:
            flash("Username already exists!", 'error')
        elif password != confirmation:
            flash("Passwords don't match", 'error')
        elif len(pin) != 4 or not pin.isdigit():
            flash('PIN must be exactly 4 digits.', 'error')
        else:
            pas = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash, pin, name) VALUES (?, ?, ?, ?)", username, pas, pin, name)
            flash(f"Thank you {name}. Registration successful!", 'success')
            # Redirect only if all fields are entered successfully
            return redirect(url_for('login'))
        form_data = {
            "name": name,
            "username": username,
            "password": password,
            "confirmation": confirmation,
            "pin": pin
        }
    return render_template("register.html", form=form_data)



@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    form_data = {}
    request.args.get("name")
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Query database for username
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        row = db.execute("SELECT name FROM users WHERE username = ?", username)
        # Ensure username was submitted
        if not request.form.get("username") and not request.form.get("password"):
            flash("Must provide all fields", 'error')
        elif not request.form.get("username"):
            flash("Must provide username", 'error')
        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password", 'error')
        # Ensure username exists and password is correct
        elif len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")):
            flash("invalid username and/or password", 'error')
        # Remember which user has logged in
        else:
            if rows:
                session["user_id"] = rows[0]["id"]
            if row:
                name = row[0]['name']
            else:
                name = None
                # Redirect user to home page
            db.execute("UPDATE users SET user_id = ? WHERE username = ?", session["user_id"], username)
            return redirect(url_for('index', name=name))
        form_data = {"username": request.form.get("username"),
                     "password": request.form.get("password")}
    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("login.html", form=form_data)


@app.route("/logout")
def logout():
    """Log user out"""
    flash("Logged out successfully!", 'success')
    session.clear()
    return redirect("/login")

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    session.clear()
    form_data = {}
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        row = db.execute("SELECT name FROM users WHERE username = ?", username)
        if not request.form.get("username") and not request.form.get("pin") and not password and not confirmation:
            flash("Must provide all fields", 'error')
        elif not request.form.get("username"):
            flash("Must provide username", 'error')
        elif not request.form.get("pin"):
            flash("Must provide PIN", 'error')
        elif not password:
            flash("Must provide a Password!", 'error')
        elif not confirmation:
            flash("Must confirm your new password!", 'error')
        # Ensure username exists
        elif len(rows) == 0:
            flash("Invalid username", 'error')
        elif str(request.form.get("pin")) != str(rows[0]["pin"]):
            flash("Invalid PIN", 'error')
        elif password != confirmation:
            flash("Passwords don't match", 'error')
        else:
            if row:
                name = str(row[0]['name'])
            else:
                name = None
            hashed_password = generate_password_hash(password)
            db.execute("UPDATE users SET hash = ? WHERE username = ?", hashed_password, username)
            flash(f"Thank you {name}, Password updated Successfully!", 'success')
            return redirect(url_for('index', name=name))
        form_data = {"username": request.form.get("username"),
                     "pin": request.form.get("pin"),
                     "password": password,
                     "confirmation": confirmation}
    return render_template("forgot.html", form=form_data)

@app.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    form_data={}
    if request.method == "POST":
        date = request.form.get("date")
        particulars = request.form.get("particulars")
        type = request.form.get("type")
        account = request.form.get("account")
        amount = request.form.get("amount")
        row = db.execute("SELECT name FROM users WHERE user_id = ?", session["user_id"])
        if not date and not particulars and not type and not account and not amount:
            flash("Must provide all fields!", 'error')
        elif not date:
            flash("Must provide date!", 'error')
        elif not particulars:
            flash("Must provide particulars!", 'error')
        elif not type:
            flash("Must specify whether Payment/Receipt!", 'error')
        elif not account:
            flash("Must choose Cash/Bank!", 'error')
        elif not amount:
            flash("Must provide the Amount!", 'error')
        else:
            if amount and particulars and date and type and account:
                amount = float(amount)
                user_id = session["user_id"]
                db.execute("INSERT INTO transactions (date, particulars, type, account, amount, user_id) VALUES (?, ?, ?, ?, ?, ?)", date, particulars, type, account, amount, user_id)
            if type=="Payment":
                amount = float(amount)
                user_id = session["user_id"]
                db.execute("INSERT INTO payments (status, date, pay_to, pay_for, account, amount, user_id) VALUES ('Paid', ?, '________________', ?, ?, ?, ?)", date, particulars, account, amount, user_id)
            if row:
                name = str(row[0]['name'])
            else:
                name = None
            return redirect(url_for('index', name=name))
        form_data = {"date": date,
                     "particulars": particulars,
                     "type": type,
                     "account": account,
                     "amount": amount}
    name = db.execute("SELECT name FROM users WHERE user_id = ?", session["user_id"])[0]['name']
    return render_template("transactions.html", name=name, form=form_data)


@app.route("/payment", methods=["GET", "POST"])
@login_required
def payment():
    form_data = {}
    user_id = session["user_id"]  # Ensure user_id is retrieved at the beginning
    name_row = db.execute("SELECT name FROM users WHERE user_id = ?", user_id)
    name = name_row[0]['name'] if name_row else None

    if request.method == "POST":
        # Extract the action button to determine which form was submitted
        action = request.form.get('action')

        status = request.form.get("status")
        date = request.form.get("date")
        pay_to = request.form.get("pay_to")
        pay_for = request.form.get("pay_for")
        account = request.form.get("account")
        amount = request.form.get("amount")
        due_date = request.form.get("due_date")

        form_data = {
            "status": status or '',
            "date": date or '',
            "pay_to": pay_to or '',
            "pay_for": pay_for or '',
            "account": account or '',
            "amount": amount or '',
            "due_date": due_date or ''
        }

        if action in ["Add Voucher", "Add Reminder"]:
            if amount:
                amount = float(amount)
            if action == "Add Voucher" and status == "Paid":
                db.execute("INSERT INTO payments (status, date, pay_to, pay_for, account, amount, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            status, date, pay_to, pay_for, account, amount, user_id)
                db.execute("INSERT INTO transactions (date, type, particulars, account, amount, user_id) VALUES (?, 'Payment', ?, ?, ?, ?)", date, pay_for, account, amount, user_id)
                flash(f"Thank You {name}, Voucher created successfully!", 'success')
                return redirect(url_for('voucher', name=name))
            elif action == "Add Reminder" and status == "Due":
                db.execute("INSERT INTO payments (status, date, pay_to, pay_for, account, amount, due_date, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            status, date, pay_to, pay_for, account, amount, due_date, user_id)
                flash(f"Thank You {name}, Reminder created successfully!", 'success')
                return redirect(url_for('reminder', name=name))

    return render_template("payment.html", name=name, form=form_data)

@app.route("/voucher", methods=["GET", "POST"])
@login_required
def voucher():
    user_id = session["user_id"]

    # Default sorting and filtering parameters
    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "descending")
    account = request.args.get("account", "all")

    # Construct the base SQL query
    query = "SELECT * FROM payments WHERE user_id = ? AND due_date IS NULL"
    params = [user_id]

    # Apply filtering conditions
    if account != "all":
        query += " AND account = ?"
        params.append(account)

    # Apply sorting
    order_by_clause = f"{sort_by} {'ASC' if order == 'ascending' else 'DESC'}"
    query += f" ORDER BY {order_by_clause}"

    # Execute the query
    payments = db.execute(query, *params)

    # Get user name
    name_row = db.execute("SELECT name FROM users WHERE user_id = ?", user_id)
    name = name_row[0]['name'] if name_row else None

    return render_template("voucher.html", name=name, payments=payments, sort_by=sort_by, order=order, account=account)


@app.route("/reminder", methods=["GET", "POST"])
@login_required
def reminder():
    user_id = session["user_id"]
    name_row = db.execute("SELECT name FROM users WHERE user_id = ?", user_id)
    name = name_row[0]['name'] if name_row else None
    current_date = datetime.now().strftime("%Y-%m-%d")

    if request.method == "POST":
        payment_id = request.form.get("payment_id")
        if payment_id:
            # Fetch the payment details
            payment = db.execute("SELECT * FROM payments WHERE id = ? AND user_id = ?", payment_id, user_id)[0]
            pay_for = payment['pay_for']
            account = payment['account']
            amount = payment['amount']
            pay_to = payment['pay_to']

            # Update the payment status to "paid" and set due_date to NULL and the date to todays date
            db.execute("UPDATE payments SET date = ?, status = ?, due_date = NULL WHERE id = ? AND user_id = ?", current_date, "paid", payment_id, user_id)

            # Insert the payment details into the transactions table
            db.execute("INSERT INTO transactions (date, type, particulars, account, amount, user_id) VALUES (?, 'Payment', ?, ?, ?, ?)", current_date, pay_for, account, amount, user_id)
            flash(f"Payment to {pay_to} has been marked as PAID!", 'success')

    # Default sorting parameters
    sort_by = request.args.get("sort_by", "due_date")
    order = request.args.get("order", "descending")
    order_by_clause = f"{sort_by} {'ASC' if order == 'ascending' else 'DESC'}"

    # Fetching due payments
    payments = db.execute(f"SELECT * FROM payments WHERE user_id = ? AND due_date IS NOT NULL ORDER BY {order_by_clause}", user_id)

    return render_template("reminder.html", name=name, payments=payments, sort_by=sort_by, order=order)

@app.context_processor
def inject_user_name():
    name = None
    if "user_id" in session:
        user_id = session["user_id"]
        name_row = db.execute("SELECT name FROM users WHERE user_id = ?", user_id)
        name = name_row[0]['name'] if name_row else None
    return {'name': name}

@app.context_processor
def inject_reminder_count():
    if "user_id" in session:
        user_id = session["user_id"]
        reminder_count = db.execute("SELECT COUNT(*) AS count FROM payments WHERE user_id = ? AND due_date IS NOT NULL", user_id)[0]["count"]
        return dict(reminder_count=reminder_count)
    return dict(reminder_count=0)


if __name__ == "__main__":
    app.run(debug=True)


