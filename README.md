# Lost & Found Portal (Flask)

College mini-project backend using Flask, Flask-SQLAlchemy and SQLite. Existing HTML templates are retained.

## Features
- Register/login/logout with hashed passwords
- SQLite user and item storage
- Report lost/found items with optional image uploads
- Search/filter open listings
- Item detail pages and stored claim requests
- Profile updates

## Run on Windows
1. Install Python 3.10+.
2. Open this project folder in Command Prompt / VS Code terminal.
3. Create and activate a virtual environment (recommended):
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   ```
4. Install dependencies:
   ```bat
   python -m pip install -r requirements.txt
   ```
5. Start the app:
   ```bat
   python app.py
   ```
6. Open http://127.0.0.1:5000 in your browser.

The SQLite database is created automatically in Flask's `instance` folder on first run. Uploaded images are stored in `static/uploads`. Keep this as a local college demo; before deployment, set a strong `SECRET_KEY`, disable debug mode, and add CSRF protection and stricter upload validation.


## Admin portal (college demo)
- Open `/admin/login`
- Demo username: `admin`
- Demo password: `password`
- Admin can review all Lost and Found reports, compare Lost/Found pairs using a 0–100 similarity score, send match notifications, review owner responses, request follow-up, verify, and mark items as handed over.
- Regular users can search/view public Lost reports. Found reports are not included in public search and direct access is restricted to the report owner or admin.
- For anything beyond a local college demo, set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and a strong `SECRET_KEY` environment variable. Do not deploy the demo credentials publicly.


UI fix: dashboard navbar styles are included inline. Extract this updated ZIP into a new folder, stop the old Flask server, then run `python app.py` from this folder. Hard refresh the browser with Ctrl+F5. Admin portal: `/admin/login`.
