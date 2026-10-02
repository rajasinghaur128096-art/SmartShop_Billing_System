import hashlib
import io
import os
import sqlite3

from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "shop.db")


# ============================================================
# Database
# ============================================================

def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_column_if_missing(connection, table, column, definition):
    columns = connection.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    existing_columns = {
        column_info["name"]
        for column_info in columns
    }

    if column not in existing_columns:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_db():
    connection = get_db()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            created_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            price REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            image TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            subtotal REAL NOT NULL DEFAULT 0,
            discount REAL NOT NULL DEFAULT 0,
            gst REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'UPI',
            payment_status TEXT NOT NULL DEFAULT 'Pending',
            order_status TEXT NOT NULL DEFAULT 'Processing',
            created_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY(order_id)
                REFERENCES orders(id)
                ON DELETE CASCADE,
            FOREIGN KEY(product_id)
                REFERENCES products(id)
        );
        """
    )

    add_column_if_missing(
        connection,
        "users",
        "created_at",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        connection,
        "products",
        "description",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        connection,
        "products",
        "created_at",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        connection,
        "orders",
        "phone",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        connection,
        "orders",
        "address",
        "TEXT NOT NULL DEFAULT ''"
    )

    add_column_if_missing(
        connection,
        "orders",
        "order_status",
        "TEXT NOT NULL DEFAULT 'Processing'"
    )

    add_column_if_missing(
        connection,
        "orders",
        "created_at",
        "TEXT NOT NULL DEFAULT ''"
    )

    admin = connection.execute(
        """
        SELECT id
        FROM users
        WHERE username = ?
        """,
        ("admin",)
    ).fetchone()

    if not admin:
        connection.execute(
            """
            INSERT INTO users
            (name, username, password, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Administrator",
                "admin",
                generate_password_hash("admin123"),
                "admin",
                current_time(),
            )
        )

    connection.commit()
    connection.close()


# ============================================================
# Authentication
# ============================================================

def hash_password(password):
    return generate_password_hash(password)


def verify_password(stored_password, entered_password):
    if stored_password.startswith(
        ("scrypt:", "pbkdf2:", "argon2:")
    ):
        return check_password_hash(
            stored_password,
            entered_password
        )

    old_hash = hashlib.sha256(
        entered_password.encode()
    ).hexdigest()

    return old_hash == stored_password


def get_current_user():
    return session.get("user")


@app.context_processor
def inject_global_template_data():
    # Makes the logged-in user available to every template, including checkout.
    return {
        "user": get_current_user(),
        "cart_count": get_cart_count(),
        "year": datetime.now().year,
    }


def login_required(function):
    @wraps(function)
    def decorated(*args, **kwargs):
        if not get_current_user():
            flash("Please login first.", "warning")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return decorated


def admin_required(function):
    @wraps(function)
    def decorated(*args, **kwargs):
        user = get_current_user()

        if not user or user.get("role") != "admin":
            flash(
                "Administrator access is required.",
                "danger"
            )
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return decorated


# ============================================================
# Cart
# ============================================================

def get_cart():
    cart = session.get("cart", {})

    if not isinstance(cart, dict):
        return {}

    clean_cart = {}

    for product_id, quantity in cart.items():
        try:
            product_id = str(int(product_id))
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue

        if quantity > 0:
            clean_cart[product_id] = quantity

    return clean_cart


def get_cart_details():
    cart = get_cart()
    items = []
    subtotal = 0

    connection = get_db()

    try:
        for product_id, requested_quantity in cart.items():
            product = connection.execute(
                """
                SELECT *
                FROM products
                WHERE id = ?
                """,
                (product_id,)
            ).fetchone()

            if not product:
                continue

            stock = int(product["stock"])

            if stock <= 0:
                continue

            quantity = min(
                int(requested_quantity),
                stock
            )

            line_total = round(
                float(product["price"]) * quantity,
                2
            )

            subtotal += line_total

            items.append(
                {
                    "id": product["id"],
                    "name": product["name"],
                    "category": product["category"],
                    "description": product["description"],
                    "price": float(product["price"]),
                    "stock": stock,
                    "image": product["image"],
                    "quantity": quantity,
                    "line_total": line_total,
                }
            )

    finally:
        connection.close()

    return items, round(subtotal, 2)


def get_cart_count():
    items, _ = get_cart_details()

    return sum(
        item["quantity"]
        for item in items
    )


@app.template_filter("money")
def money(value):
    return f"₹{float(value):,.2f}"


# ============================================================
# Home
# ============================================================

@app.route("/")
def home():
    search = request.args.get("q", "").strip()
    selected_category = request.args.get(
        "category",
        ""
    ).strip()

    connection = get_db()

    query = """
        SELECT *
        FROM products
        WHERE stock > 0
    """

    arguments = []

    if search:
        query += """
            AND (
                name LIKE ?
                OR category LIKE ?
                OR description LIKE ?
            )
        """

        arguments.extend(
            [
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
            ]
        )

    if selected_category:
        query += " AND category = ?"
        arguments.append(selected_category)

    query += " ORDER BY id DESC"

    products = connection.execute(
        query,
        arguments
    ).fetchall()

    categories = connection.execute(
        """
        SELECT DISTINCT category
        FROM products
        ORDER BY category
        """
    ).fetchall()

    connection.close()

    return render_template(
        "home.html",
        products=products,
        categories=categories,
        search=search,
        selected_category=selected_category,
    )


# ============================================================
# Registration and login
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get(
            "name",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if len(name) < 2:
            flash("Please enter your full name.", "danger")
            return redirect(url_for("register"))

        if len(username) < 3:
            flash(
                "Username must contain at least 3 characters.",
                "danger"
            )
            return redirect(url_for("register"))

        if len(password) < 6:
            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )
            return redirect(url_for("register"))

        connection = get_db()

        try:
            connection.execute(
                """
                INSERT INTO users
                (name, username, password, role, created_at)
                VALUES (?, ?, ?, 'customer', ?)
                """,
                (
                    name,
                    username,
                    hash_password(password),
                    current_time(),
                )
            )

            connection.commit()

            flash(
                "Account created. Please login.",
                "success"
            )

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash(
                "Username already exists.",
                "danger"
            )

        finally:
            connection.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get(
            "username",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_db()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if not user or not verify_password(
            user["password"],
            password
        ):
            connection.close()

            flash(
                "Invalid username or password.",
                "danger"
            )

            return redirect(url_for("login"))

        if len(user["password"]) == 64:
            connection.execute(
                """
                UPDATE users
                SET password = ?
                WHERE id = ?
                """,
                (
                    hash_password(password),
                    user["id"],
                )
            )

            connection.commit()

        connection.close()

        session.clear()

        session["user"] = {
            "id": user["id"],
            "name": user["name"],
            "username": user["username"],
            "role": user["role"],
        }

        if user["role"] == "admin":
            return redirect(url_for("admin"))

        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("home"))


# ============================================================
# AJAX cart route
# ============================================================

@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    is_ajax = (
        request.headers.get("X-Requested-With")
        == "XMLHttpRequest"
    )

    connection = None

    try:
        connection = get_db()

        product = connection.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        ).fetchone()

        if not product:
            if is_ajax:
                return jsonify(
                    {
                        "success": False,
                        "message": "Product not found.",
                    }
                ), 404

            flash(
                "Product not found.",
                "danger"
            )

            return redirect(url_for("home"))

        if int(product["stock"]) <= 0:
            if is_ajax:
                return jsonify(
                    {
                        "success": False,
                        "message": "Product is out of stock.",
                    }
                ), 400

            flash(
                "Product is out of stock.",
                "danger"
            )

            return redirect(url_for("home"))

        try:
            quantity = int(
                request.form.get(
                    "quantity",
                    "1"
                )
            )
        except (TypeError, ValueError):
            quantity = 1

        quantity = max(1, quantity)

        cart = get_cart()
        cart_key = str(product_id)

        old_quantity = cart.get(
            cart_key,
            0
        )

        cart[cart_key] = min(
            old_quantity + quantity,
            int(product["stock"])
        )

        session["cart"] = cart
        session.modified = True

        if is_ajax:
            return jsonify(
                {
                    "success": True,
                    "message": (
                        f"{product['name']} "
                        "added to cart."
                    ),
                    "cart_count": get_cart_count(),
                }
            )

        flash(
            f"{product['name']} added to cart.",
            "success"
        )

        return redirect(
            request.referrer or url_for("home")
        )

    except Exception:
        app.logger.exception("Add to cart failed")

        if is_ajax:
            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Unable to add product "
                        "to the cart."
                    ),
                }
            ), 500

        flash(
            "Unable to add product to the cart.",
            "danger"
        )

        return redirect(url_for("home"))

    finally:
        if connection:
            connection.close()


@app.route("/cart")
def cart():
    items, subtotal = get_cart_details()

    gst = round(
        subtotal * 0.05,
        2
    )

    total = round(
        subtotal + gst,
        2
    )

    return render_template(
        "cart.html",
        items=items,
        subtotal=subtotal,
        gst=gst,
        total=total,
    )


@app.post("/cart/update")
def update_cart():
    cart = get_cart()

    for product_id in list(cart.keys()):
        try:
            quantity = int(
                request.form.get(
                    f"qty_{product_id}",
                    "0"
                )
            )
        except (TypeError, ValueError):
            quantity = 0

        if quantity <= 0:
            cart.pop(product_id, None)
        else:
            cart[product_id] = quantity

    session["cart"] = cart
    session.modified = True

    flash(
        "Cart updated.",
        "success"
    )

    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:product_id>")
def remove_from_cart(product_id):
    cart = get_cart()

    cart.pop(
        str(product_id),
        None
    )

    session["cart"] = cart
    session.modified = True

    flash(
        "Product removed from cart.",
        "success"
    )

    return redirect(url_for("cart"))


# ============================================================
# Checkout
# ============================================================

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items, subtotal = get_cart_details()

    if not items:
        flash(
            "Your cart is empty.",
            "warning"
        )

        return redirect(url_for("cart"))

    if request.method == "POST":
        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        discount_code = request.form.get(
            "discount_code",
            ""
        ).strip().upper()

        payment_method = request.form.get(
            "payment_method",
            "UPI"
        )

        if len(phone) < 10:
            flash(
                "Please enter a valid phone number.",
                "danger"
            )

            return redirect(url_for("checkout"))

        if not address:
            flash(
                "Please enter a delivery address.",
                "danger"
            )

            return redirect(url_for("checkout"))

        discount = 0

        if discount_code == "SAVE10":
            discount = round(
                subtotal * 0.10,
                2
            )

        gst = round(
            (subtotal - discount) * 0.05,
            2
        )

        total = round(
            subtotal - discount + gst,
            2
        )

        payment_status = (
            "Pending"
            if payment_method == "Cash on Delivery"
            else "Paid"
        )

        connection = get_db()

        try:
            connection.execute("BEGIN")

            for item in items:
                latest_product = connection.execute(
                    """
                    SELECT stock
                    FROM products
                    WHERE id = ?
                    """,
                    (item["id"],)
                ).fetchone()

                if (
                    not latest_product
                    or int(latest_product["stock"])
                    < int(item["quantity"])
                ):
                    connection.rollback()

                    flash(
                        f"Not enough stock for "
                        f"{item['name']}.",
                        "danger"
                    )

                    return redirect(url_for("cart"))

            order_cursor = connection.execute(
                """
                INSERT INTO orders
                (
                    user_id,
                    customer_name,
                    phone,
                    address,
                    subtotal,
                    discount,
                    gst,
                    total,
                    payment_method,
                    payment_status,
                    order_status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    get_current_user()["id"],
                    get_current_user()["name"],
                    phone,
                    address,
                    subtotal,
                    discount,
                    gst,
                    total,
                    payment_method,
                    payment_status,
                    "Processing",
                    current_time(),
                )
            )

            order_id = order_cursor.lastrowid

            for item in items:
                connection.execute(
                    """
                    INSERT INTO order_items
                    (
                        order_id,
                        product_id,
                        product_name,
                        price,
                        quantity,
                        line_total
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        item["id"],
                        item["name"],
                        item["price"],
                        item["quantity"],
                        item["line_total"],
                    )
                )

                connection.execute(
                    """
                    UPDATE products
                    SET stock = stock - ?
                    WHERE id = ?
                    AND stock >= ?
                    """,
                    (
                        item["quantity"],
                        item["id"],
                        item["quantity"],
                    )
                )

            connection.commit()

            session["cart"] = {}
            session.modified = True

            return redirect(
                url_for(
                    "bill",
                    order_id=order_id
                )
            )

        except Exception:
            connection.rollback()

            app.logger.exception(
                "Checkout failed"
            )

            flash(
                "Checkout failed. Please try again.",
                "danger"
            )

            return redirect(url_for("checkout"))

        finally:
            connection.close()

    gst = round(
        subtotal * 0.05,
        2
    )

    total = round(
        subtotal + gst,
        2
    )

    return render_template(
        "checkout.html",
        items=items,
        subtotal=subtotal,
        gst=gst,
        total=total,
    )


# ============================================================
# Orders and bills
# ============================================================

@app.route("/orders")
@login_required
def my_orders():
    connection = get_db()

    orders = connection.execute(
        """
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (get_current_user()["id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "orders.html",
        orders=orders,
    )


def get_authorized_order(order_id):
    connection = get_db()

    order = connection.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()

    if not order:
        connection.close()
        abort(404)

    user = get_current_user()

    if (
        order["user_id"] != user["id"]
        and user["role"] != "admin"
    ):
        connection.close()
        abort(403)

    items = connection.execute(
        """
        SELECT *
        FROM order_items
        WHERE order_id = ?
        ORDER BY id
        """,
        (order_id,)
    ).fetchall()

    connection.close()

    return order, items


@app.route("/bill/<int:order_id>")
@login_required
def bill(order_id):
    order, items = get_authorized_order(order_id)

    return render_template(
        "bill.html",
        order=order,
        items=items,
    )


@app.route("/bill/<int:order_id>/pdf")
@login_required
def download_pdf(order_id):
    order, items = get_authorized_order(order_id)

    output = io.BytesIO()
    pdf = canvas.Canvas(
        output,
        pagesize=A4
    )

    page_width, page_height = A4
    left = 50
    right = page_width - 50
    y = page_height - 55

    pdf.setFont(
        "Helvetica-Bold",
        22
    )

    pdf.drawString(
        left,
        y,
        "SMARTSHOP INVOICE"
    )

    y -= 35

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        left,
        y,
        f"Order #{order['id']}"
    )

    pdf.drawRightString(
        right,
        y,
        order["created_at"]
    )

    y -= 25

    pdf.drawString(
        left,
        y,
        f"Customer: {order['customer_name']}"
    )

    y -= 16

    pdf.drawString(
        left,
        y,
        f"Phone: {order['phone']}"
    )

    y -= 16

    address = order["address"].replace(
        "\n",
        " "
    )

    pdf.drawString(
        left,
        y,
        f"Address: {address[:85]}"
    )

    y -= 30

    pdf.line(
        left,
        y,
        right,
        y
    )

    y -= 25

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        left,
        y,
        "Product"
    )

    pdf.drawString(
        330,
        y,
        "Price"
    )

    pdf.drawString(
        405,
        y,
        "Qty"
    )

    pdf.drawRightString(
        right,
        y,
        "Total"
    )

    y -= 20

    pdf.setFont(
        "Helvetica",
        10
    )

    for item in items:
        product_name = item["product_name"]

        if len(product_name) > 40:
            product_name = product_name[:37] + "..."

        pdf.drawString(
            left,
            y,
            product_name
        )

        pdf.drawString(
            330,
            y,
            f"Rs. {float(item['price']):.2f}"
        )

        pdf.drawString(
            410,
            y,
            str(item["quantity"])
        )

        pdf.drawRightString(
            right,
            y,
            f"Rs. {float(item['line_total']):.2f}"
        )

        y -= 22

    y -= 15
    pdf.line(
        320,
        y,
        right,
        y
    )

    y -= 25

    totals = [
        ("Subtotal", order["subtotal"]),
        ("Discount", order["discount"]),
        ("GST", order["gst"]),
        ("TOTAL", order["total"]),
    ]

    for label, value in totals:
        pdf.drawString(
            350,
            y,
            label
        )

        pdf.drawRightString(
            right,
            y,
            f"Rs. {float(value):.2f}"
        )

        y -= 22

    y -= 20

    pdf.drawString(
        left,
        y,
        (
            f"Payment: {order['payment_method']} - "
            f"{order['payment_status']}"
        )
    )

    y -= 35

    pdf.drawString(
        left,
        y,
        "Thank you for shopping with SmartShop."
    )

    pdf.save()
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=(
            f"smartshop_invoice_{order_id}.pdf"
        ),
        mimetype="application/pdf",
    )


# ============================================================
# Admin
# ============================================================

@app.route(
    "/admin/products/edit/<int:product_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_product(product_id):
    connection = get_db()
    product = connection.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()

    if not product:
        connection.close()
        abort(404)

    if request.method == "POST":
        name = request.form.get(
            "name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        image = request.form.get(
            "image",
            ""
        ).strip()

        try:
            price = float(
                request.form.get(
                    "price",
                    "0"
                )
            )

            stock = int(
                request.form.get(
                    "stock",
                    "0"
                )
            )

        except (TypeError, ValueError):
            connection.close()

            flash(
                "Price and stock must be valid numbers.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_product",
                    product_id=product_id
                )
            )

        if (
            not name
            or not category
            or not image
            or price < 0
            or stock < 0
        ):
            connection.close()

            flash(
                "Complete all product fields correctly.",
                "danger"
            )

            return redirect(
                url_for(
                    "edit_product",
                    product_id=product_id
                )
            )

        connection.execute(
            """
            UPDATE products
            SET
                name = ?,
                category = ?,
                description = ?,
                price = ?,
                stock = ?,
                image = ?
            WHERE id = ?
            """,
            (
                name,
                category,
                description,
                price,
                stock,
                image,
                product_id,
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Product updated successfully.",
            "success"
        )

        return redirect(url_for("admin"))

    connection.close()

    return render_template(
        "edit_product.html",
        product=product,
    )
@app.get("/admin")
@admin_required
def admin():
    connection = get_db()

    products = connection.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    orders = connection.execute(
        """
        SELECT *
        FROM orders
        ORDER BY id DESC
        LIMIT 50
        """
    ).fetchall()

    total_products = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM products
        """
    ).fetchone()["total"]

    total_orders = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM orders
        """
    ).fetchone()["total"]

    total_customers = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM users
        WHERE role = 'customer'
        """
    ).fetchone()["total"]

    total_sales = connection.execute(
        """
        SELECT COALESCE(SUM(total), 0) AS total
        FROM orders
        WHERE payment_status IN ('Paid', 'Paid (Demo)')
        """
    ).fetchone()["total"]

    # Unique registered customers who have actually placed an order.
    customers_shopped = connection.execute(
        """
        SELECT COUNT(DISTINCT user_id) AS total
        FROM orders
        """
    ).fetchone()["total"]

    # Unique customers who placed an order today.
    today_shoppers = connection.execute(
        """
        SELECT COUNT(DISTINCT user_id) AS total
        FROM orders
        WHERE date(created_at) = date('now', 'localtime')
        """
    ).fetchone()["total"]

    low_stock = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM products
        WHERE stock <= 5
        """
    ).fetchone()["total"]

    connection.close()

    return render_template(
        "admin.html",
        products=products,
        orders=orders,
        total_products=total_products,
        total_orders=total_orders,
        total_customers=total_customers,
        customers_shopped=customers_shopped,
        today_shoppers=today_shoppers,
        total_sales=total_sales,
        low_stock=low_stock,
    )


@app.post("/admin/products/add")
@admin_required
def add_product():
    name = request.form.get(
        "name",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    image = request.form.get(
        "image",
        ""
    ).strip()

    try:
        price = float(
            request.form.get(
                "price",
                "0"
            )
        )

        stock = int(
            request.form.get(
                "stock",
                "0"
            )
        )

    except (TypeError, ValueError):
        flash(
            "Price and stock must be valid numbers.",
            "danger"
        )

        return redirect(url_for("admin"))

    if (
        not name
        or not category
        or not image
        or price < 0
        or stock < 0
    ):
        flash(
            "Complete all product fields correctly.",
            "danger"
        )

        return redirect(url_for("admin"))

    connection = get_db()

    connection.execute(
        """
        INSERT INTO products
        (
            name,
            category,
            description,
            price,
            stock,
            image,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            category,
            description,
            price,
            stock,
            image,
            current_time(),
        )
    )

    connection.commit()
    connection.close()

    flash(
        "Product added successfully.",
        "success"
    )

    return redirect(url_for("admin"))


@app.post("/admin/products/delete/<int:product_id>")
@admin_required
def delete_product(product_id):
    connection = get_db()

    used_in_order = connection.execute(
        """
        SELECT id
        FROM order_items
        WHERE product_id = ?
        LIMIT 1
        """,
        (product_id,)
    ).fetchone()

    if used_in_order:
        flash(
            "This product is linked to an order "
            "and cannot be deleted.",
            "warning"
        )
    else:
        connection.execute(
            """
            DELETE FROM products
            WHERE id = ?
            """,
            (product_id,)
        )

        connection.commit()

        flash(
            "Product deleted.",
            "success"
        )

    connection.close()

    return redirect(url_for("admin"))


# ============================================================
# Error handlers
# ============================================================

@app.errorhandler(403)
def forbidden(error):
    return render_template(
        "403.html"
    ), 403


@app.errorhandler(404)
def not_found(error):
    return render_template(
        "404.html"
    ), 404


@app.errorhandler(500)
def server_error(error):
    app.logger.exception(
        "Internal server error"
    )

    return render_template(
        "500.html"
    ), 500


init_db()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True,
    )