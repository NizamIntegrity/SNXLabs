from flask import Flask, render_template, request, redirect, send_from_directory
import sqlite3
import os


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

@app.route(
    "/labs/sqli",
    methods=["GET", "POST"]
)
def sqli_lab():

    results = []
    error = None
    completed = False

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )

        connection = get_db()

        # INTENTIONALLY VULNERABLE

        query = (
            "SELECT * FROM users "
            f"WHERE username = '{username}' "
            f"AND password = '{password}'"
        )

        try:

            results = connection.execute(
                query
            ).fetchall()

            admin_found = any(
                user["username"] == "admin"
                for user in results
            )

            if (
                admin_found
                and password != ADMIN_PASSWORD
            ):
                completed = True

        except sqlite3.Error as exc:

            error = str(exc)

        connection.close()

    return render_template(
        "sqli/index.html",
        results=results,
        error=error,
        completed=completed
    )


# =========================
# RESET SQLI LAB
# =========================

@app.route(
    "/labs/sqli/reset",
    methods=["POST"]
)
def reset_sqli():

    reset_db()

    return redirect(
        "/labs/sqli"
    )


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