from __future__ import annotations

import io
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dairy_farm.db"

app = Flask(__name__)
app.secret_key = "smart-dairy-secret-key"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            mobile TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            mobile TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            pincode TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            payment_status TEXT NOT NULL,
            delivery_status TEXT NOT NULL DEFAULT 'Pending',
            sms_sent INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS animals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            breed TEXT NOT NULL,
            age INTEGER NOT NULL,
            milk_quantity REAL NOT NULL,
            fat_percent REAL NOT NULL,
            health_status TEXT NOT NULL,
            health_reason TEXT,
            treatment TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pregnancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_id INTEGER NOT NULL,
            pregnant TEXT NOT NULL,
            months INTEGER,
            days INTEGER,
            expected_date TEXT,
            FOREIGN KEY(animal_id) REFERENCES animals(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_id INTEGER NOT NULL,
            calf_name TEXT NOT NULL,
            calf_gender TEXT NOT NULL,
            delivery_date TEXT NOT NULL,
            mother_health TEXT NOT NULL,
            FOREIGN KEY(animal_id) REFERENCES animals(id)
        )
        """
    )

    cursor.execute("SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users(username, password, role, mobile, created_at) VALUES (?, ?, 'admin', '', ?)",
            (ADMIN_USERNAME, ADMIN_PASSWORD, datetime.now().isoformat(timespec="seconds")),
        )

    cursor.execute("SELECT COUNT(*) AS count FROM products")
    if cursor.fetchone()["count"] == 0:
        cursor.executemany(
            "INSERT INTO products(name, price, stock) VALUES (?, ?, ?)",
            [
                ("Milk", 50, 100),
                ("Curd", 40, 80),
                ("Paneer", 300, 50),
                ("Ghee", 650, 20),
            ],
        )

    db.commit()
    db.close()


def login_required(role: str | None = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if "username" not in session:
                flash("Please login first.", "error")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Unauthorized access.", "error")
                return redirect(url_for("dashboard"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        mobile = request.form["mobile"].strip()
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users(username, password, role, mobile, created_at) VALUES (?, ?, 'customer', ?, ?)",
                (username, password, mobile, datetime.now().isoformat(timespec="seconds")),
            )
            db.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        db = get_db()
        user = db.execute(
            "SELECT username, password, role FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user and user["password"] == password:
            session["username"] = user["username"]
            session["role"] = user["role"]
            session.setdefault("cart", {})
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    db = get_db()
    stats = {
        "products": db.execute("SELECT COUNT(*) c FROM products").fetchone()["c"],
        "orders": db.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"],
        "revenue": db.execute("SELECT COALESCE(SUM(price),0) s FROM orders WHERE payment_status='Paid'").fetchone()["s"],
        "animals": db.execute("SELECT COUNT(*) c FROM animals").fetchone()["c"],
    }
    return render_template("dashboard.html", stats=stats)


@app.route("/products")
@login_required()
def products():
    items = get_db().execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("products.html", products=items)


@app.route("/cart/add/<int:product_id>")
@login_required()
def add_to_cart(product_id: int):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products"))
    cart = session.get("cart", {})
    pid = str(product_id)
    cart[pid] = cart.get(pid, 0) + 1
    session["cart"] = cart
    flash(f"Added {product['name']} to cart.", "success")
    return redirect(url_for("products"))


@app.route("/cart")
@login_required()
def cart():
    db = get_db()
    cart_data = session.get("cart", {})
    rows = []
    total = 0
    for pid, qty in cart_data.items():
        product = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if not product:
            continue
        subtotal = product["price"] * qty
        total += subtotal
        rows.append({"product": product, "qty": qty, "subtotal": subtotal})
    return render_template("cart.html", items=rows, total=total)


@app.route("/checkout", methods=["GET", "POST"])
@login_required("customer")
def checkout():
    if request.method == "POST":
        session["delivery"] = {
            "mobile": request.form["mobile"],
            "address": request.form["address"],
            "city": request.form["city"],
            "pincode": request.form["pincode"],
        }
        return redirect(url_for("payment"))
    user = get_db().execute("SELECT mobile FROM users WHERE username=?", (session["username"],)).fetchone()
    return render_template("checkout.html", username=session["username"], mobile=user["mobile"] if user else "")


@app.route("/payment", methods=["GET", "POST"])
@login_required("customer")
def payment():
    db = get_db()
    cart_data = session.get("cart", {})
    delivery = session.get("delivery")
    if not cart_data or not delivery:
        flash("Add items and delivery details first.", "error")
        return redirect(url_for("cart"))

    order_rows = []
    total = 0
    for pid, qty in cart_data.items():
        product = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if product:
            line_total = product["price"] * qty
            order_rows.append((product, qty, line_total))
            total += line_total

    if request.method == "POST":
        for product, qty, line_total in order_rows:
            if product["stock"] < qty:
                flash(f"Insufficient stock for {product['name']}", "error")
                return redirect(url_for("cart"))

        for product, qty, line_total in order_rows:
            db.execute(
                """INSERT INTO orders(username,mobile,address,city,pincode,product_name,price,payment_status,delivery_status,sms_sent)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Paid', 'Pending', 0)""",
                (
                    session["username"],
                    delivery["mobile"],
                    delivery["address"],
                    delivery["city"],
                    delivery["pincode"],
                    f"{product['name']} x{qty}",
                    line_total,
                ),
            )
            db.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, product["id"]))

        db.commit()
        session["cart"] = {}
        session.pop("delivery", None)
        flash("Payment successful. Order placed!", "success")
        return redirect(url_for("order_status"))

    return render_template("payment.html", total=total, items=order_rows)


@app.route("/orders/status")
@login_required("customer")
def order_status():
    rows = get_db().execute("SELECT * FROM orders WHERE username=? ORDER BY id DESC", (session["username"],)).fetchall()
    return render_template("order_status.html", orders=rows)


@app.route("/admin/products", methods=["GET", "POST"])
@login_required("admin")
def admin_products():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO products(name, price, stock) VALUES (?, ?, ?)",
            (request.form["name"], float(request.form["price"]), int(request.form["stock"])),
        )
        db.commit()
        flash("Product added.", "success")
    items = db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("admin_products.html", products=items)


@app.route("/admin/products/delete/<int:product_id>")
@login_required("admin")
def delete_product(product_id: int):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/orders")
@login_required("admin")
def admin_orders():
    rows = get_db().execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    return render_template("admin_orders.html", orders=rows)


@app.route("/admin/orders/deliver/<int:order_id>")
@login_required("admin")
def mark_delivered(order_id: int):
    db = get_db()
    db.execute("UPDATE orders SET delivery_status='Delivered', sms_sent=1 WHERE id=?", (order_id,))
    db.commit()
    flash("Order marked delivered and SMS sent.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/reports")
@login_required("admin")
def reports():
    db = get_db()
    revenue = db.execute("SELECT COALESCE(SUM(price),0) s FROM orders WHERE payment_status='Paid'").fetchone()["s"]
    profit = revenue * 0.30
    product_summary = db.execute(
        "SELECT product_name, COUNT(*) as orders, SUM(price) as total FROM orders GROUP BY product_name ORDER BY total DESC"
    ).fetchall()
    return render_template("reports.html", revenue=revenue, profit=profit, summary=product_summary)


@app.route("/admin/reports/pdf")
@login_required("admin")
def report_pdf():
    db = get_db()
    revenue = db.execute("SELECT COALESCE(SUM(price),0) s FROM orders WHERE payment_status='Paid'").fetchone()["s"]
    profit = revenue * 0.30
    lines = [
        "Smart Dairy Farming Report",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Total Revenue: Rs.{revenue:.2f}",
        f"Profit (30%): Rs.{profit:.2f}",
    ]
    content = "\n".join(lines)
    pdf = f"%PDF-1.1\n1 0 obj<<>>endobj\n2 0 obj<< /Length {len(content)+35} >>stream\nBT /F1 12 Tf 50 750 Td ({content}) Tj ET\nendstream endobj\n3 0 obj<< /Type /Page /Parent 4 0 R /Contents 2 0 R >>endobj\n4 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n5 0 obj<< /Type /Catalog /Pages 4 0 R >>endobj\nxref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000030 00000 n \n0000000000 00000 n \n0000000000 00000 n \n0000000000 00000 n \ntrailer<< /Root 5 0 R /Size 6>>\nstartxref\n0\n%%EOF"
    return send_file(
        io.BytesIO(pdf.encode("latin1", errors="ignore")),
        as_attachment=True,
        download_name="dairy-report.pdf",
        mimetype="application/pdf",
    )


@app.route("/admin/animals", methods=["GET", "POST"])
@login_required("admin")
def animals():
    db = get_db()
    if request.method == "POST":
        db.execute(
            """INSERT INTO animals(code,name,breed,age,milk_quantity,fat_percent,health_status,health_reason,treatment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request.form["code"],
                request.form["name"],
                request.form["breed"],
                int(request.form["age"]),
                float(request.form["milk_quantity"]),
                float(request.form["fat_percent"]),
                request.form["health_status"],
                request.form.get("health_reason", ""),
                request.form.get("treatment", ""),
            ),
        )
        db.commit()
        flash("Animal added.", "success")
    rows = db.execute("SELECT * FROM animals ORDER BY id DESC").fetchall()
    total_milk = sum(row["milk_quantity"] for row in rows)
    return render_template("animals.html", animals=rows, total_milk=total_milk)


@app.route("/admin/pregnancies", methods=["GET", "POST"])
@login_required("admin")
def pregnancies():
    db = get_db()
    if request.method == "POST":
        animal_id = int(request.form["animal_id"])
        pregnant = request.form["pregnant"]
        months = int(request.form.get("months") or 0)
        days = int(request.form.get("days") or 0)
        expected = None
        if pregnant == "Yes":
            expected = (datetime.now() + timedelta(days=max(0, (9 - months) * 30 - days))).date().isoformat()
        db.execute(
            "INSERT INTO pregnancies(animal_id,pregnant,months,days,expected_date) VALUES (?, ?, ?, ?, ?)",
            (animal_id, pregnant, months, days, expected),
        )
        db.commit()
        flash("Pregnancy record saved.", "success")
    animals_rows = db.execute("SELECT id, name, code FROM animals ORDER BY name").fetchall()
    rows = db.execute(
        "SELECT p.*, a.name as animal_name, a.code as animal_code FROM pregnancies p JOIN animals a ON p.animal_id = a.id ORDER BY p.id DESC"
    ).fetchall()
    return render_template("pregnancies.html", pregnancies=rows, animals=animals_rows)


@app.route("/admin/deliveries", methods=["GET", "POST"])
@login_required("admin")
def deliveries():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO deliveries(animal_id,calf_name,calf_gender,delivery_date,mother_health) VALUES (?, ?, ?, ?, ?)",
            (
                int(request.form["animal_id"]),
                request.form["calf_name"],
                request.form["calf_gender"],
                request.form["delivery_date"],
                request.form["mother_health"],
            ),
        )
        db.commit()
        flash("Delivery record saved.", "success")
    animals_rows = db.execute("SELECT id, name, code FROM animals ORDER BY name").fetchall()
    rows = db.execute(
        "SELECT d.*, a.name as animal_name, a.code as animal_code FROM deliveries d JOIN animals a ON d.animal_id = a.id ORDER BY d.id DESC"
    ).fetchall()
    return render_template("deliveries.html", deliveries=rows, animals=animals_rows)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
