# SNXLabs

SNXLabs is a local web-security training project. Its SQL Injection lab is
intentionally vulnerable and uses disposable practice accounts and SQLite
data. Do not use real credentials or data, deploy this lab publicly, or expose
it as a production service.

## Run locally

1. Install Python 3.12 or later.
2. Install the project dependency:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Start the Flask app:

   ```bash
   python labs/sqli/app.py
   ```

4. Open `http://127.0.0.1:5000`.

The SQLite database is created at `labs/sqli/lab.db` the first time the app is
started directly. It contains only seeded training accounts. The lab's reset
button restores those accounts.

## Run in Replit

The Replit **Start application** workflow runs the Flask app on port 5000 for
the workspace preview. It binds to the workspace interfaces for preview
access; this is for development only. Do not publish or deploy the intentionally
vulnerable lab as a public service.