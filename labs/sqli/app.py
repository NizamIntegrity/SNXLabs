from flask import Flask, jsonify, render_template, request, redirect, send_from_directory
import sqlite3
import os
from urllib.parse import parse_qs, urlsplit


# =========================
# PATH CONFIG
# =========================

SQLI_DIR = os.path.dirname(os.path.abspath(__file__))
LABS_DIR = os.path.dirname(SQLI_DIR)
SNXLABS_DIR = os.path.dirname(LABS_DIR)

DATABASE = os.path.join(
    SQLI_DIR,
    "lab.db"
)

ADMIN_PASSWORD = "SNXadmin123"
PRODUCT_SEED_DATA = (
    (
        1,
        "Aurora Wireless Keyboard",
        "Workspace",
        "A compact wireless keyboard with quiet, low-profile keys.",
        89.99,
        18,
    ),
    (
        2,
        "Northstar Desk Lamp",
        "Lighting",
        "A dimmable LED lamp with an adjustable arm and warm light.",
        54.00,
        24,
    ),
    (
        3,
        "Trailhead Daypack",
        "Outdoor",
        "A weather-resistant 18-liter pack for daily carry.",
        72.50,
        11,
    ),
    (
        4,
        "Harbor Ceramic Mug",
        "Kitchen",
        "A matte-glazed stoneware mug with a 350 ml capacity.",
        18.00,
        36,
    ),
)


# =========================
# FLASK
# =========================

app = Flask(
    __name__,
    template_folder=os.path.join(
        SQLI_DIR,
        "templates"
    )
)


# =========================
# DATABASE
# =========================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_products_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
        """
    )


def seed_products(connection):
    connection.executemany(
        """
        INSERT INTO products
        (id, name, category, description, price, stock)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        PRODUCT_SEED_DATA,
    )


def init_db():

    connection = get_db()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )

    existing = connection.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    if existing == 0:

        connection.executemany(
            """
            INSERT INTO users
            (username, password, role)
            VALUES (?, ?, ?)
            """,
            [
                (
                    "admin",
                    "SNXadmin123",
                    "administrator"
                ),
                (
                    "alice",
                    "alice123",
                    "user"
                ),
                (
                    "bob",
                    "bob123",
                    "user"
                )
            ]
        )

    create_products_table(connection)
    existing_products = connection.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if existing_products == 0:
        seed_products(connection)

    connection.commit()
    connection.close()


def reset_db():

    connection = get_db()

    connection.execute(
        "DROP TABLE IF EXISTS users"
    )

    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )

    connection.executemany(
        """
        INSERT INTO users
        (username, password, role)
        VALUES (?, ?, ?)
        """,
        [
            (
                "admin",
                "SNXadmin123",
                "administrator"
            ),
            (
                "alice",
                "alice123",
                "user"
            ),
            (
                "bob",
                "bob123",
                "user"
            )
        ]
    )

    connection.commit()
    connection.close()


def reset_products_db():
    connection = get_db()
    connection.execute("DROP TABLE IF EXISTS products")
    create_products_table(connection)
    seed_products(connection)
    connection.commit()
    connection.close()


def execute_product_lookup(id_expression):
    query = (
        "SELECT id, name, category, description, price, stock "
        f"FROM products WHERE id = {id_expression}"
    )
    connection = get_db()

    try:
        products = [
            dict(row)
            for row in connection.execute(query).fetchall()
        ]
        return query, products, None
    except sqlite3.Error as exc:
        return query, [], str(exc)
    finally:
        connection.close()


# =========================
# HOME
# =========================

@app.route("/")
def home():

    return send_from_directory(
        SNXLABS_DIR,
        "index.html"
    )


# =========================
# CSS
# =========================

@app.route("/css/<path:filename>")
def css(filename):

    return send_from_directory(
        os.path.join(
            SNXLABS_DIR,
            "css"
        ),
        filename
    )


# =========================
# JAVASCRIPT
# =========================

@app.route("/js/<path:filename>")
def javascript(filename):

    return send_from_directory(
        os.path.join(
            SNXLABS_DIR,
            "js"
        ),
        filename
    )


# =========================
# SQLI LAB
# =========================

@app.route("/labs/sqli", methods=["GET", "POST"])
@app.route(
    "/labs/sqli/authentication-bypass",
    methods=["GET", "POST"]
)
def sqli_lab():

    if request.path == "/labs/sqli" and request.method == "GET":
        return render_template(
            "sqli/hub.html",
            reset_done=request.args.get("reset") == "1",
        )

    results = []
    error = None
    completed = False
    login_outcome = None
    submitted_username = ""
    reset_done = request.args.get("reset") == "1"

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )
        submitted_username = username

        connection = get_db()

        # INTENTIONALLY VULNERABLE

        query = (
            "SELECT * FROM users "
            f"WHERE username = '{username}' "
            f"AND password = '{password}'"
        )

        try:
            challenge_admin = connection.execute(
                """
                SELECT id, username, password, role
                FROM users
                WHERE username = ? AND role = ?
                ORDER BY id
                LIMIT 1
                """,
                ("admin", "administrator")
            ).fetchone()

            results = connection.execute(
                query
            ).fetchall()

            admin_record_returned = (
                challenge_admin is not None
                and any(
                    all(
                        user[column] == challenge_admin[column]
                        for column in ("id", "username", "password", "role")
                    )
                    for user in results
                )
            )

            submitted_real_admin_credentials = (
                challenge_admin is not None
                and username == challenge_admin["username"]
                and password == challenge_admin["password"]
            )

            completed = (
                admin_record_returned
                and not submitted_real_admin_credentials
            )

        except sqlite3.Error as exc:

            error = str(exc)

        finally:
            connection.close()

        if error:
            login_outcome = "error"
        elif completed:
            login_outcome = "completed"
        elif results:
            login_outcome = "incomplete"
        else:
            login_outcome = "failed"

    return render_template(
        "sqli/index.html",
        results=results,
        error=error,
        completed=completed,
        login_outcome=login_outcome,
        submitted_username=submitted_username,
        reset_done=reset_done
    )


@app.route("/labs/sqli/id-parameter", methods=["GET", "POST"])
def id_parameter_lab():
    target_request = "/product?id=1"
    request_sent = request.method == "POST"
    browser_error = None
    sql_error = None
    sql_query = None
    products = []
    response_status = 200

    if request_sent:
        target_request = request.form.get("target_request", target_request)

    try:
        parsed_request = urlsplit(target_request)
        if (
            parsed_request.scheme
            or parsed_request.netloc
            or parsed_request.path != "/product"
            or parsed_request.fragment
        ):
            browser_error = (
                "This simulated browser only accepts the local "
                "/product endpoint. External URLs are never requested."
            )
            response_status = 400
        else:
            parameters = parse_qs(
                parsed_request.query,
                keep_blank_values=True,
            )
            id_values = parameters.get("id", [])

            if len(id_values) != 1 or not id_values[0]:
                browser_error = "Add exactly one non-empty id parameter to the request."
                response_status = 400
            else:
                sql_query, products, sql_error = execute_product_lookup(
                    id_values[0]
                )
                if sql_error:
                    response_status = 500
                elif not products:
                    response_status = 404
    except ValueError:
        browser_error = (
            "Enter a valid relative request for the local /product endpoint."
        )
        response_status = 400

    challenge_completed = (
        request_sent
        and browser_error is None
        and sql_error is None
        and len(products) > 1
    )

    return render_template(
        "sqli/id_parameter.html",
        target_request=target_request,
        request_sent=request_sent,
        browser_error=browser_error,
        sql_error=sql_error,
        sql_query=sql_query,
        products=products,
        response_status=response_status,
        challenge_completed=challenge_completed,
        reset_done=request.args.get("reset") == "1",
    )


@app.route("/product", methods=["GET"])
def product_target():
    id_expression = request.args.get("id", "1")
    query, products, error = execute_product_lookup(id_expression)

    if error:
        return jsonify(
            {
                "error": error,
                "products": [],
                "query": query,
            }
        ), 400

    response_status = 200 if products else 404
    return jsonify(
        {
            "count": len(products),
            "products": products,
            "query": query,
        }
    ), response_status


# =========================
# RESET SQLI LAB
# =========================

@app.route(
    "/labs/sqli/reset",
    methods=["POST"]
)
@app.route(
    "/labs/sqli/authentication-bypass/reset",
    methods=["POST"]
)
def reset_sqli():

    reset_db()

    if request.path == "/labs/sqli/reset":
        return redirect("/labs/sqli?reset=1")

    return redirect("/labs/sqli/authentication-bypass?reset=1")


@app.route("/labs/sqli/id-parameter/reset", methods=["POST"])
def reset_id_parameter():
    reset_products_db()
    return redirect("/labs/sqli/id-parameter?reset=1")


# =========================
# RUN SERVER
# =========================

if __name__ == "__main__":

    init_db()

    print()
    print("================================")
    print("          SNXLabs")
    print("================================")
    print()
    print("Home:")
    print("http://127.0.0.1:5000")
    print()
    print("SQL Injection Lab:")
    print("http://127.0.0.1:5000/labs/sqli")
    print()
    print("Press CTRL+C to stop.")
    print()

    app.run(
        host=os.environ.get("SNXLABS_HOST", "127.0.0.1"),
        port=5000,
        debug=False
    )