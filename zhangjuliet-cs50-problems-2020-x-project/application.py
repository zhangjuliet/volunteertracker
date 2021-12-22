import os

# from cs50 import SQL
import sqlite3
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
# db = SQL("sqlite:///volunteertracker.db")
db = sqlite3.connect("volunteertracker.db")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Sign up user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure name, username, password, and confirmation was submitted
        if not request.form.get("name") or not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("missing fields", 403)

        # Ensure passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)

        # Query database for username and ensure username does not already exist
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(rows) >= 1:
            return apology("username already exists", 403)

        # Add user to database and remember session
        primary_key = db.execute("INSERT INTO users (username, hash, name) VALUES (:username, :hash, :name)", username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")), name=request.form.get("name"))
        session["user_id"] = primary_key

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username and password was submitted
        if not request.form.get("username") or not request.form.get("password"):
            return apology("missing username and/or password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/")
@login_required
def home():
    """Show home page with greeting and volunteer statistics"""

    # Update number of events and organizations
    db.execute("UPDATE users SET num_events = (SELECT COUNT(event) FROM events WHERE user_id = :user_id) WHERE id = :user_id", user_id=session["user_id"])
    db.execute("UPDATE users SET num_organizations = (SELECT COUNT(DISTINCT organization_name) FROM organizations WHERE user_id = :user_id) WHERE id = :user_id", user_id=session["user_id"])

    # Update number of hours
    rows = db.execute("SELECT SUM(hours) as sum_hours FROM events WHERE user_id = :user_id", user_id=session["user_id"])
    if rows[0]["sum_hours"] is None:
        db.execute("UPDATE users SET num_hours = :zero WHERE id = :user_id", zero=0.00, user_id=session["user_id"])
    else:
        db.execute("UPDATE users SET num_hours = :num_hours WHERE id = :user_id", num_hours=rows[0]["sum_hours"], user_id=session["user_id"])

    # Get user information
    user = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])

    # Store user's name and total number of events, hours, and organizations
    name = user[0]["name"]
    total_events = int(user[0]["num_events"])
    total_organizations = int(user[0]["num_organizations"])
    total_hours = float(user[0]["num_hours"])

    return render_template("home.html", name=name, total_events=total_events, total_hours=total_hours, total_organizations=total_organizations)

@app.route("/events")
@login_required
def events():
    """Show all recorded events"""

    events = db.execute("SELECT * FROM events WHERE user_id = :user_id ORDER BY date ASC", user_id=session["user_id"])

    # Add up hours from events for total number of hours volunteered
    total_hours = 0.00
    for event in events:
        total_hours += float(event["hours"])

    return render_template("events.html", events=events, total_hours=total_hours)

@app.route("/add_event", methods=["GET", "POST"])
@login_required
def add_event():
    """Allow user to record new events"""

    organizations = db.execute("SELECT * FROM organizations WHERE user_id = :user_id", user_id=session["user_id"])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get event info from user's response
        event = request.form.get("event")
        date = request.form.get("date")
        location = request.form.get("location")
        organization = request.form.get("organization")
        category = request.form.get("category")
        description = request.form.get("description")
        hours = request.form.get("hours")

        # Ensure all fields were submitted
        if not event or not date or not location or not organization or not category or not description or not hours:
            return apology("missing field(s)", 403)

        # Add event to events table
        db.execute("INSERT INTO events (user_id, event, date, location, organization, category, description, hours) VALUES (:user_id, :event, :date, :location, :organization, :category, :description, :hours)",
                    user_id=session["user_id"], event=event, date=date, location=location, organization=organization, category=category, description=description, hours=hours)

        # Redirect user to events page
        flash("Event added!")
        return redirect("/events")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("add_event.html", organizations=organizations)

@app.route("/delete_event", methods=["POST"])
@login_required
def delete_event():
    """Delete specified event"""

    # Delete event from events table
    db.execute("DELETE FROM events WHERE event_id = :event_id", event_id=request.form.get("event_id"))

    # Ensure that events table isn't empty upon return
    events = db.execute("SELECT * FROM events WHERE user_id = :user_id ORDER BY date ASC", user_id=session["user_id"])

    # Add up hours from events for total number of hours volunteered
    total_hours = 0.00
    for event in events:
        total_hours += float(event["hours"])

    # Redirect user to events page
    flash("Event deleted!")
    return render_template("events.html", events=events, total_hours=total_hours)

@app.route("/organizations")
@login_required
def organizations():
    """Show all organizations joined"""

    organizations = db.execute("SELECT * FROM organizations WHERE user_id = :user_id ORDER BY date_joined ASC", user_id=session["user_id"])
    return render_template("organizations.html", organizations=organizations)

@app.route("/add_organization", methods=["GET", "POST"])
@login_required
def add_organization():
    """Allow user to add new organizations"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get organization info from user's response
        organization_name = request.form.get("organization_name").upper()
        scope = request.form.get("scope")
        date_joined = request.form.get("date_joined")

        # Ensure all fields were submitted
        if not organization_name or not scope or not date_joined:
            return apology("missing field(s)", 403)

        # Add organization to organizations table
        db.execute("INSERT INTO organizations (user_id, organization_name, scope, date_joined) VALUES (:user_id, :organization_name, :scope, :date_joined)",
                    user_id=session["user_id"], organization_name=organization_name, scope=scope, date_joined=date_joined)

        # Redirect user to organizations page
        flash("Organization added!")
        return redirect("/organizations")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("add_organization.html")

@app.route("/delete_organization", methods=["POST"])
@login_required
def delete_organization():
    """Delete specified organization"""

    # Delete organization from organizations table
    db.execute("DELETE FROM organizations WHERE organization_id = :organization_id", organization_id=request.form.get("organization_id"))

    # Ensure that organizations table isn't empty upon return
    organizations = db.execute("SELECT * FROM organizations WHERE user_id = :user_id ORDER BY date_joined ASC", user_id=session["user_id"])

    # Redirect user to organizations page
    flash("Organization deleted!")
    return render_template("organizations.html", organizations=organizations)

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow user to change password"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        rows = db.execute("SELECT hash FROM users WHERE id = :user_id", user_id=session["user_id"])

        # Ensure current password exists and is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("current_password")):
            return apology("incorrect password", 403)

        # Ensure new password and confirmation match
        if request.form.get("new_password") != request.form.get("new_confirmation"):
            return apology("new password and confirmation must match", 403)

        # Update users table with new password hash
        hash = generate_password_hash(request.form.get("new_password"))
        rows = db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", hash=hash, user_id=session["user_id"])

        # Redirect user to home page
        flash("Password successfully changed!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("change_password.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)