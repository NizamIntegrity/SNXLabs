import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "labs" / "sqli" / "app.py"
REAL_DATABASE_PATH = (PROJECT_ROOT / "labs" / "sqli" / "lab.db").resolve()

spec = importlib.util.spec_from_file_location("snxlabs_sqli_app_under_test", APP_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load Flask application from {APP_PATH}")

sqli_app = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sqli_app
spec.loader.exec_module(sqli_app)


class SqliAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory(prefix="snxlabs-tests-")
        self.original_database_path = sqli_app.DATABASE
        self.database_path = Path(self.temp_directory.name) / "lab.db"
        sqli_app.DATABASE = str(self.database_path)

        self.assertNotEqual(self.database_path.resolve(), REAL_DATABASE_PATH)
        sqli_app.init_db()
        self.client = sqli_app.app.test_client()

    def tearDown(self):
        sqli_app.DATABASE = self.original_database_path
        self.temp_directory.cleanup()

    def read_users(self):
        with sqlite3.connect(sqli_app.DATABASE) as connection:
            return connection.execute(
                "SELECT username, password, role FROM users ORDER BY id"
            ).fetchall()

    def assert_homepage_served(self):
        response = self.client.get("/")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"SNXLabs", response.data)
            self.assertIn(b"Web Security Labs", response.data)
            return response.data
        finally:
            response.close()

    def test_fresh_database_initialization_seeds_practice_accounts(self):
        fresh_database_path = Path(self.temp_directory.name) / "fresh-lab.db"
        previous_database_path = sqli_app.DATABASE
        sqli_app.DATABASE = str(fresh_database_path)
        try:
            self.assertFalse(fresh_database_path.exists())

            sqli_app.init_db()
            with sqlite3.connect(fresh_database_path) as connection:
                rows = connection.execute(
                    "SELECT username, password, role FROM users ORDER BY id"
                ).fetchall()

            self.assertEqual(
                rows,
                [
                    ("admin", "SNXadmin123", "administrator"),
                    ("alice", "alice123", "user"),
                    ("bob", "bob123", "user"),
                ],
            )

            # Initialization is safe to repeat and does not duplicate seed rows.
            sqli_app.init_db()
            with sqlite3.connect(fresh_database_path) as connection:
                row_count = connection.execute(
                    "SELECT COUNT(*) FROM users"
                ).fetchone()[0]
            self.assertEqual(row_count, 3)
        finally:
            sqli_app.DATABASE = previous_database_path

    def test_normal_failed_login_shows_feedback(self):
        response = self.client.post(
            "/labs/sqli",
            data={"username": "unknown-user", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login failed:", response.data)
        self.assertIn(b"no matching accounts", response.data)

    def test_valid_regular_user_login_does_not_complete_admin_challenge(self):
        response = self.client.post(
            "/labs/sqli",
            data={"username": "alice", "password": "alice123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"alice123", response.data)
        self.assertIn(b"challenge is not complete", response.data)
        self.assertNotIn(b"Challenge Completed", response.data)

    def test_correct_administrator_login_does_not_count_as_sqli_bypass(self):
        response = self.client.post(
            "/labs/sqli",
            data={"username": "admin", "password": "SNXadmin123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"admin", response.data)
        self.assertIn(b"challenge is not complete", response.data)
        self.assertNotIn(b"Challenge Completed", response.data)

    def test_intended_sqli_challenge_returns_seeded_admin_and_completes(self):
        response = self.client.post(
            "/labs/sqli",
            data={"username": "admin' -- ", "password": "not-the-admin-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Challenge Completed", response.data)
        self.assertIn(b"What happened", response.data)
        self.assertIn(b"Why it worked", response.data)
        self.assertIn(b"Security impact", response.data)

    def test_fabricated_admin_looking_row_does_not_complete_challenge(self):
        response = self.client.post(
            "/labs/sqli",
            data={
                "username": (
                    "x' UNION SELECT 999,'admin',"
                    "'not-the-real-password','administrator' -- "
                ),
                "password": "anything",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"challenge is not complete", response.data)
        self.assertNotIn(b"Challenge Completed", response.data)

    def test_sql_error_is_rendered_as_a_training_lab_error(self):
        response = self.client.post(
            "/labs/sqli",
            data={"username": "admin' AND (", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Practice SQL error details", response.data)
        self.assertIn(b"local training lab", response.data)
        self.assertNotIn(b"Challenge Completed", response.data)

    def test_reset_restores_seed_accounts_and_reports_completion(self):
        with sqlite3.connect(sqli_app.DATABASE) as connection:
            connection.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("temporary-practice-row", "temporary-password", "user"),
            )
            connection.commit()

        response = self.client.post("/labs/sqli/reset")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/labs/sqli?reset=1")

        reset_page = self.client.get(response.headers["Location"])
        self.assertEqual(reset_page.status_code, 200)
        self.assertIn(b"Practice data restored", reset_page.data)
        self.assertEqual(
            self.read_users(),
            [
                ("admin", "SNXadmin123", "administrator"),
                ("alice", "alice123", "user"),
                ("bob", "bob123", "user"),
            ],
        )

    def test_homepage_route_serves_snxlabs_homepage(self):
        self.assert_homepage_served()

    def test_sqli_lab_route_shows_lab_and_disposable_data_notice(self):
        response = self.client.get("/labs/sqli")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SQL Injection Lab", response.data)
        self.assertIn(b"disposable data only", response.data)
        self.assertIn(b"Show Hint", response.data)
        self.assertIn(b"Reset Practice Data", response.data)

    def test_sqli_hub_lists_only_the_planned_sql_injection_challenges(self):
        response = self.client.get("/labs/sqli")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Authentication Bypass", response.data)
        self.assertIn(b"Basic / ID Parameter SQLi", response.data)
        self.assertIn(b' href="/labs/sqli/authentication-bypass"', response.data)
        self.assertIn(b' href="/labs/sqli/id-parameter"', response.data)
        for coming_soon in (
            b"Error-Based SQLi",
            b"ORDER BY SQLi",
            b"UNION-Based SQLi",
            b"Boolean-Based Blind SQLi",
            b"Time-Based Blind SQLi",
        ):
            self.assertIn(coming_soon, response.data)
        self.assertIn(b"Coming Soon", response.data)

    def test_homepage_sql_injection_card_opens_the_sqli_hub(self):
        homepage = self.assert_homepage_served()
        self.assertIn(b'href="/labs/sqli"', homepage)

        hub = self.client.get("/labs/sqli")
        self.assertEqual(hub.status_code, 200)
        self.assertIn(b"SQL Injection Lab", hub.data)

    def test_product_route_returns_one_fictional_product_for_a_normal_id(self):
        response = self.client.get("/product?id=1")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["products"][0]["id"], 1)
        self.assertEqual(payload["products"][0]["name"], "Aurora Wireless Keyboard")
        self.assertIn("WHERE id = 1", payload["query"])

    def test_product_route_returns_not_found_for_an_unknown_id(self):
        response = self.client.get("/product?id=9999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["products"], [])

    def test_id_parameter_challenge_uses_sql_results_to_detect_success(self):
        response = self.client.post(
            "/labs/sqli/id-parameter",
            data={"target_request": "/product?id=1 OR 1=1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Challenge completed", response.data)
        self.assertIn(b"Aurora Wireless Keyboard", response.data)
        self.assertIn(b"Northstar Desk Lamp", response.data)
        self.assertIn(b"Trailhead Daypack", response.data)
        self.assertIn(b"Harbor Ceramic Mug", response.data)
        self.assertIn(b"WHERE id = 1 OR 1=1", response.data)

    def test_id_parameter_unsuccessful_request_does_not_complete_challenge(self):
        response = self.client.post(
            "/labs/sqli/id-parameter",
            data={"target_request": "/product?id=9999"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No product matched this request", response.data)
        self.assertNotIn(b"Challenge completed", response.data)

    def test_id_parameter_simulator_blocks_external_urls(self):
        response = self.client.post(
            "/labs/sqli/id-parameter",
            data={"target_request": "https://example.invalid/product?id=1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"External URLs are never requested", response.data)
        self.assertIn(b"BLOCKED", response.data)
        self.assertNotIn(b"Aurora Wireless Keyboard", response.data)

    def test_id_parameter_reset_restores_only_the_fictional_product_catalog(self):
        with sqlite3.connect(sqli_app.DATABASE) as connection:
            connection.execute(
                """
                INSERT INTO products
                (id, name, category, description, price, stock)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (99, "Temporary Item", "Practice", "Temporary row", 1.00, 1),
            )
            connection.commit()

        response = self.client.post("/labs/sqli/id-parameter/reset")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "/labs/sqli/id-parameter?reset=1",
        )
        reset_page = self.client.get(response.headers["Location"])
        self.assertEqual(reset_page.status_code, 200)
        self.assertIn(b"Product practice data was restored", reset_page.data)

        with sqlite3.connect(sqli_app.DATABASE) as connection:
            product_rows = connection.execute(
                "SELECT id, name FROM products ORDER BY id"
            ).fetchall()
            user_rows = connection.execute(
                "SELECT username FROM users ORDER BY id"
            ).fetchall()

        self.assertEqual(
            product_rows,
            [
                (1, "Aurora Wireless Keyboard"),
                (2, "Northstar Desk Lamp"),
                (3, "Trailhead Daypack"),
                (4, "Harbor Ceramic Mug"),
            ],
        )
        self.assertEqual(user_rows, [("admin",), ("alice",), ("bob",)])

    def test_lab_return_home_link_points_to_working_homepage(self):
        lab_page = self.client.get("/labs/sqli")

        self.assertEqual(lab_page.status_code, 200)
        self.assertIn(b'href="/"', lab_page.data)
        self.assertIn(b"SNXLabs Home", lab_page.data)

        self.assert_homepage_served()


if __name__ == "__main__":
    unittest.main()