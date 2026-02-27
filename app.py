from flask import Flask, request, jsonify, redirect, url_for, render_template
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
import datetime
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import re # for confirm email function

load_dotenv()

MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_HOST = os.getenv("MONGO_HOST", "mongo")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_DBNAME = os.getenv("MONGO_DBNAME")


MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DBNAME}?authSource=admin"

client = MongoClient(MONGO_URI)
db = client[MONGO_DBNAME]
posts_collection = db.posts
users_collection = db.users

# Options for 24-hour clock used by forms and filters (00:00, 01:00, ..., 23:00)
HOUR_CHOICES = [f"{h:02d}:00" for h in range(0, 24)]

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # where to redirect if not logged in

# -----------------------
# User Model
# -----------------------

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.email = user_data["email"]
        self.netid = user_data["netid"]

# -----------------------
# User Loader
# -----------------------

@login_manager.user_loader
def load_user(user_id):
    try:
        object_id = ObjectId(user_id)
    except InvalidId:
        return None
    # Look up the logged-in user by ObjectId, if it exists
    user_data = users_collection.find_one({"_id": object_id})
    if user_data:
        return User(user_data)
    return None

# This is temparary until we implement auth, so we can use url_for() in templates without crashing
@app.get("/")
def root():
    return redirect(url_for("home"))

# ---------------
# Auth guard
# ---------------


# ---------------
# landing
# ---------------


# ---------------
# Login 
# ---------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user_data = users_collection.find_one({"email": email})

        if user_data and user_data["password"] == password:
            user = User(user_data)
            login_user(user)
            return redirect(url_for("home"))

        return render_template("login.html", message="Invalid email or password.")

    return render_template("login.html")

# ---------------
# Signup
# ---------------
# This function checks that all sign up info is correct and creates user in database
def is_valid_nyu_email(email):
    if not isinstance(email, str):
        return False
    
    email = email.strip()
    pattern = r'^[A-Za-z0-9._%+-]+@nyu\.edu$'
    return re.fullmatch(pattern, email, re.IGNORECASE) is not None


def is_valid_google_maps_url(url):
    # Basic validation so we only accept real Google Maps-style URLs
    if not isinstance(url, str):
        return False
    url = url.strip()
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    allowed_hosts = ("google.com", "goo.gl", "maps.app.goo.gl")
    if not any(parsed.netloc.endswith(host) for host in allowed_hosts):
        return False
    if "maps" not in parsed.path:
        return False
    return True


def is_valid_hours_range(hours_str):
    if not isinstance(hours_str, str):
        return False
    hours_str = hours_str.strip()
    if not hours_str:
        return False
    pattern = r'^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$'
    if not re.fullmatch(pattern, hours_str):
        return False
    return True


def split_hours_range(hours_str):
    # Parse "HH:MM-HH:MM" into (start, end) strings for further processing
    if not isinstance(hours_str, str):
        return "", ""
    parts = hours_str.split("-")
    if len(parts) != 2:
        return "", ""
    start, end = parts[0].strip(), parts[1].strip()
    if not is_valid_hours_range(f"{start}-{end}"):
        return "", ""
    return start, end


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Validation
        if not is_valid_nyu_email(email):
            return render_template("signup.html", error="Must use valid NYU email.")

        elif len(password) < 8:
            return render_template("signup.html", error="Password must be at least 8 characters.")

        elif password != confirm_password:
            return render_template("signup.html", error="Passwords do not match.")

        # Check duplicate
        elif users_collection.find_one({"email": email}):
            return render_template("signup.html", error="User already exists.")

        user_name = email.split("@")[0]

        users_collection.insert_one({
            "netid": user_name,
            "email": email,
            "password": password,
            "posts": []
        })

        return redirect(url_for("login"))

    return render_template("signup.html")

# -----------------------
# Placeholder routes so url_for() won't crash
# -----------------------
# @app.get("/map")
# def map_page():
#     return "<h1>Map Page (placeholder)</h1>"

@app.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---------------
# Home Page
# ---------------
@app.get("/home")
@login_required
def home():
    # Read all filter values from the query string
    q = request.args.get("q", "").strip()
    noise_level = request.args.get("noise_level", "").strip()
    wifi = request.args.get("wifi", "").strip()
    outlets = request.args.get("outlets", "").strip()
    reservable = request.args.get("reservable", "").strip()
    hours_start = request.args.get("hours_start", "").strip()
    hours_end = request.args.get("hours_end", "").strip()

    # Build the base MongoDB query for non-time filters
    query = {}
    if q:
        query["location"] = {"$regex": q, "$options": "i"}
    if noise_level:
        query["noise_level"] = noise_level
    if wifi:
        query["wifi"] = wifi
    if outlets:
        query["outlets"] = outlets
    if reservable:
        query["reservable"] = reservable

    # Get candidate posts from MongoDB, then refine them in Python using time logic
    posts = list(posts_collection.find(query).sort("created_at", -1).limit(200))

    # Helpers to work with "HH:MM" as minutes from midnight
    def to_minutes(h):
        if not isinstance(h, str) or ":" not in h:
            return None
        try:
            hh, mm = h.split(":")
            return int(hh) * 60 + int(mm)
        except ValueError:
            return None

    # Convert filter start/end strings to minutes (or None if unset)
    filter_start = to_minutes(hours_start) if hours_start else None
    filter_end = to_minutes(hours_end) if hours_end else None

    # Decide whether a post's hours overlap/contain the requested time window
    def matches_hours(post):
        if filter_start is None and filter_end is None:
            return True
        start_str, end_str = split_hours_range(post.get("hours", ""))
        s = to_minutes(start_str)
        e = to_minutes(end_str)
        if s is None or e is None:
            return False
        if filter_start is not None and filter_end is not None:
            return s <= filter_start and e >= filter_end
        if filter_start is not None:
            return e >= filter_start
        if filter_end is not None:
            return s <= filter_end
        return True

    # Apply the time filter in memory
    posts = [p for p in posts if matches_hours(p)]
    for p in posts:
        p["_id"] = str(p["_id"])
    return render_template(
        "home.html",
        posts=posts,
        q=q,
        noise_level=noise_level,
        wifi=wifi,
        outlets=outlets,
        reservable=reservable,
        hours_start=hours_start,
        hours_end=hours_end,
        hours_options=HOUR_CHOICES,
    )

# ---------------
# View Post
# ---------------
@app.route("/posts/<post_id>")
def view_post(post_id):
    try:
        object_id = ObjectId(post_id)
    except InvalidId:
        return "Post not found", 404
    post = posts_collection.find_one({"_id": object_id})
    if not post:
        return "Post not found", 404
    return render_template("view_post.html", post=post)

# ---------------
# Create Post
# ---------------
@app.route("/posts/create", methods=["GET", "POST"])
def create_post():
    if request.method == "POST":
        # Collect hours from the two dropdowns and normalize to "HH:MM-HH:MM"
        hours_start = request.form.get("hours_start", "").strip()
        hours_end = request.form.get("hours_end", "").strip()
        hours = f"{hours_start}-{hours_end}" if hours_start and hours_end else ""

        # Capture the current form state so we can re-render with user input if there are errors
        current_post = {
            "netid": request.form.get("netid", "").strip(),
            "location": request.form.get("location", "").strip(),
            "googlemaps": request.form.get("googlemaps", "").strip(),
            "noise_level": request.form.get("noise_level", ""),
            "seating": request.form.get("seating", ""),
            "wifi": request.form.get("wifi", ""),
            "outlets": request.form.get("outlets", ""),
            "reservable": request.form.get("reservable", ""),
            "climate": request.form.get("climate", "").strip(),
            "hours_start": hours_start,
            "hours_end": hours_end,
            "hours": hours,
        }

        googlemaps = current_post["googlemaps"]

        # Validate Google Maps URL and hours before inserting into Mongo
        if not is_valid_google_maps_url(googlemaps):
            return render_template(
                "create_post.html",
                post=current_post,
                error_googlemaps="Please enter a valid Google Maps URL.",
                error_hours=None,
                hours_options=HOUR_CHOICES,
            )

        if not is_valid_hours_range(hours):
            return render_template(
                "create_post.html",
                post=current_post,
                error_googlemaps=None,
                error_hours="Please enter hours as 24-hour range, e.g. 09:00-18:00.",
                hours_options=HOUR_CHOICES,
            )

        post_data = {
            # Only the fields that should be stored in MongoDB
            "netid": current_post["netid"],
            "location": current_post["location"],
            "googlemaps": current_post["googlemaps"],
            "noise_level": current_post["noise_level"],
            "seating": current_post["seating"],
            "wifi": current_post["wifi"],
            "outlets": current_post["outlets"],
            "reservable": current_post["reservable"],
            "climate": current_post["climate"],
            "hours": current_post["hours"],
            "created_at": datetime.datetime.utcnow()
        }

        result = posts_collection.insert_one(post_data)
        return redirect(url_for("view_post", post_id=result.inserted_id))
    empty_post = {
        "netid": "",
        "location": "",
        "googlemaps": "",
        "noise_level": "",
        "seating": "",
        "wifi": "",
        "outlets": "",
        "reservable": "",
        "climate": "",
        "hours_start": "",
        "hours_end": "",
        "hours": ""
    }

    return render_template(
        "create_post.html",
        post=empty_post,
        error_googlemaps=None,
        error_hours=None,
        hours_options=HOUR_CHOICES,
    )

# ---------------
# Edit Post
# ---------------
@app.route("/posts/<post_id>/edit", methods=["GET", "POST"])
def edit_post(post_id):
    try:
        object_id = ObjectId(post_id)
    except InvalidId:
        return "Post not found", 404
    post = posts_collection.find_one({"_id": object_id})

    # Pre-populate hours_start/hours_end on first load based on the stored "HH:MM-HH:MM"
    start_default, end_default = split_hours_range(post.get("hours", ""))
    post.setdefault("hours_start", start_default)
    post.setdefault("hours_end", end_default)

    if request.method == "POST":
        # Normalize hours from dropdowns into "HH:MM-HH:MM"
        hours_start = request.form.get("hours_start", "").strip()
        hours_end = request.form.get("hours_end", "").strip()
        hours = f"{hours_start}-{hours_end}" if hours_start and hours_end else ""

        # Capture updated form values so we can both validate and re-render on error
        form_post = {
            "netid": request.form.get("netid", "").strip(),
            "location": request.form.get("location", "").strip(),
            "googlemaps": request.form.get("googlemaps", "").strip(),
            "noise_level": request.form.get("noise_level", ""),
            "seating": request.form.get("seating", ""),
            "wifi": request.form.get("wifi", ""),
            "outlets": request.form.get("outlets", ""),
            "reservable": request.form.get("reservable", ""),
            "climate": request.form.get("climate", "").strip(),
            "hours_start": hours_start,
            "hours_end": hours_end,
            "hours": hours,
        }

        googlemaps = form_post["googlemaps"]

        # Merge edited values over the original post so template has the full state
        temp_post = dict(post)
        temp_post.update(form_post)

        if not is_valid_google_maps_url(googlemaps):
            return render_template(
                "edit_post.html",
                post=temp_post,
                message=None,
                error_googlemaps="Please enter a valid Google Maps URL.",
                error_hours=None,
                hours_options=HOUR_CHOICES,
            )
        if not is_valid_hours_range(hours):
            return render_template(
                "edit_post.html",
                post=temp_post,
                message=None,
                error_googlemaps=None,
                error_hours="Please enter hours as 24-hour range, e.g. 09:00-18:00.",
                hours_options=HOUR_CHOICES,
            )

        updated_data = {
            "netid": form_post["netid"],
            "location": form_post["location"],
            "googlemaps": form_post["googlemaps"],
            "noise_level": form_post["noise_level"],
            "seating": form_post["seating"],
            "wifi": form_post["wifi"],
            "outlets": form_post["outlets"],
            "reservable": form_post["reservable"],
            "climate": form_post["climate"],
            "hours": form_post["hours"],
        }

        posts_collection.update_one({"_id": object_id}, {"$set": updated_data})
        updated_post = posts_collection.find_one({"_id": object_id})
        s, e = split_hours_range(updated_post.get("hours", ""))
        updated_post.setdefault("hours_start", s)
        updated_post.setdefault("hours_end", e)
        return render_template(
            "edit_post.html",
            post=updated_post,
            message="Post updated successfully!",
            error_googlemaps=None,
            error_hours=None,
            hours_options=HOUR_CHOICES,
        )
    return render_template(
        "edit_post.html",
        post=post,
        message=None,
        error_googlemaps=None,
        error_hours=None,
        hours_options=HOUR_CHOICES,
    )

# ---------------
# Delete Post
# ---------------
@app.route("/posts/<post_id>/delete", methods=["POST"])
def delete_post(post_id):
    try:
        object_id = ObjectId(post_id)
    except InvalidId:
        return "Post not found", 404
    posts_collection.delete_one({"_id": object_id})
    return "Deleted successfully", 200

# ---------------
# Map Page
# ---------------
@app.get("/map")
def map_page():
    posts = list(posts_collection.find({}, {"location": 1, "googlemaps": 1, "_id": 1}))
    for p in posts:
        p["_id"] = str(p["_id"])
    return render_template("map.html", posts=posts)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)