# ConComply2 - AI Coding Agent Instructions

## Project Overview
ConComply2 is a Flask-based admin authentication system with user registration, login, and dashboard functionality. It's a lightweight authentication service using SQLAlchemy ORM and SQLite database.

## Architecture & Key Components

### Core Structure
- **[app.py](../app.py)**: Flask application entry point with route handlers
- **[models.py](../models.py)**: SQLAlchemy models (currently only `AdminUser`)
- **[db.py](../db.py)**: Database initialization and configuration
- **[utils.py](../utils.py)**: Password hashing utilities using werkzeug
- **[create_db.py](../create_db.py)**: Database initialization script

### Data Flow
1. Routes receive form data from Flask templates
2. Query `AdminUser` model from SQLite database
3. Use utility functions (`hash_password`, `verify_password`) for security
4. Manage user sessions via Flask `session` object
5. Flash messages for user feedback

## Current Routes & Patterns

### Implemented Routes
- `GET/POST /login`: Email/password authentication with session management
- `GET/POST /registration`: User account creation with password confirmation
- `GET/POST /dashboard`: Protected route requiring `session["user_id"]`
- `GET /logout`: Incomplete (stub exists in app.py)

### Authentication Pattern
Session-based auth using `session["user_id"]`. On protected routes, validate:
```python
user = AdminUser.query.filter_by(id=session.get("user_id")).first()
if not user:
    flash("Please log in!")
    return redirect(url_for("login"))
```

## Database & Models

### Current Schema
`AdminUser` model in [models.py](../models.py):
- `id`: Primary key
- `email`: Unique, required
- `password_hash`: Hashed password (never store plaintext)
- `address`: Optional user address
- `registration_date`: Auto-set to UTC now

### Model Creation
Run [create_db.py](../create_db.py) to initialize tables in `instance/db.db`

## Development Workflows

### Initial Setup
1. Ensure Flask, Flask-SQLAlchemy, werkzeug, python-dotenv installed
2. Set `SECRET_KEY` in `.env` file (loaded by `python-dotenv`)
3. Run `python create_db.py` to create database tables (creates `instance/db.db`)
4. Start app: `python -m flask run` (default: http://localhost:5000)

### Running the App
```bash
# From project root with virtual environment activated
python -m flask run
```
Visit http://localhost:5000/login to test authentication flow. Default routes are `/login`, `/registration`, `/dashboard`, `/logout`.

### Adding a New Protected Route
1. Follow the dashboard pattern: check `session.get("user_id")` and redirect to login if missing
2. Example:
```python
@app.route("/profile")
def profile():
    user = AdminUser.query.filter_by(id=session.get("user_id")).first()
    if not user:
        flash("Please log in!")
        return redirect(url_for("login"))
    return render_template("profile.html", user=user)
```

### Adding Routes
1. Create handler in [app.py](../app.py) with `@app.route()` decorator
2. Use form data via `request.form.get("field_name")`
3. Query models with SQLAlchemy: `AdminUser.query.filter_by(...)`
4. Use `flash()` for user notifications (supports categories: `flash("msg", "error")`)
5. Render templates with `render_template()`

### Adding Models
1. Define in [models.py](../models.py) with `Mapped` type hints (SQLAlchemy 2.0 style)
2. Delete `instance/db.db` and run `python create_db.py` to recreate schema

## Project Conventions

### Password Security
- Always hash passwords with `hash_password()` before storing
- Always verify with `verify_password()` when authenticating
- Never log or display password hashes

### Error Handling
- Broad try-except in dashboard (line 20) indicates incomplete error handling
- Use `flash()` for user-facing errors (not `print()`)
- Consider logging for debugging vs. user feedback

### Session Management
- Store only `user_id` in session (lightweight)
- Query full user object when needed
- Validate session on protected routes before proceeding

### Templates
- Located in `templates/` directory
- Use Jinja2 templating with `{% ... %}` syntax
- Flash messages pattern (see [login.html](../templates/login.html)):
```html
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <ul>
      {% for category, message in messages %}
        <li class="{{ category }}">{{ message }}</li>
      {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
```
- Forms use HTML5 validation (`required`, `type="email"`, `type="password"`) but **no server-side validation yet**

### Form Handling
- Email input type enforces basic HTML5 email format client-side
- Password confirmation checked server-side in registration (see [app.py](../app.py) line 65-70)
- **Note**: No server-side email validation (could add regex or duplicate email check)

## Important Notes

### Incomplete Features
- `/logout` route exists but may need testing (currently clears session properly at line 49)
- [routes.py](../routes.py) and [services.py](../services.py) are empty (consider moving route logic here for modularity)
- No server-side email validation on registration/login
- Dashboard POST handler is empty (line 24 in [app.py](../app.py))

### Database Schema Changes
- Models use SQLAlchemy 2.0 style with `Mapped` type hints (see [models.py](../models.py))
- After modifying `AdminUser` or adding new models: delete `instance/db.db` and run `python create_db.py`
- Database is SQLite stored at `instance/db.db` - **add to .gitignore**, not for version control

### Tech Stack
- **Framework**: Flask
- **ORM**: SQLAlchemy with `Mapped` type hints (modern approach)
- **Database**: SQLite (instance/db.db)
- **Password**: Werkzeug security functions
- **Config**: python-dotenv for environment variables

### Database Location
SQLite database stored at `instance/db.db` (relative to app root)
