from flask import Flask, request, redirect, url_for, render_template
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
)
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime
import os
from dotenv import load_dotenv
import re # for confirm email function, also for parsing google map link parsing
from werkzeug.security import generate_password_hash, check_password_hash # for password hashing


# ---------------------------------------------------------------------------
# Helpers for homepage search/filters and create/edit opening hours
#
# _time_to_minutes(s)           - parse "HH:MM" to minutes; used for time filter and validation
# _hours_contain_interval(...) - whether a place's hours cover the user's chosen interval (home filter)
# _parse_hours_to_start_end(s) - split stored "9:00-17:00" into start/end for edit-form dropdowns
# ---------------------------------------------------------------------------

def _time_to_minutes(s):
    """
    Convert a time string to minutes since midnight for comparison.
    Used by: homepage time filter and create/edit hours validation.
    - Input: 'HH:MM' or 'H:MM' (e.g. '09:00', '24:00').
    - Output: int minutes (0--1440), or None if invalid.
    """
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if not m:
        return None
    h, mn = int(m.group(1)), int(m.group(2))
    if h < 0 or h > 24 or mn < 0 or mn > 59 or (h == 24 and mn != 0):
        return None
    return h * 60 + mn if h < 24 else 24 * 60


def _hours_contain_interval(hours_str, start_min, end_min):
    """
    Check if a place's opening hours cover the user-selected time range (homepage filter).
    - hours_str: stored value like '9:00-17:00' or '13:00-24:00'.
    - start_min, end_min: user interval in minutes since midnight.
    Returns True if the place is open for the whole interval (or if hours are missing/invalid, so we don't hide the place).
    """
    if not hours_str or not isinstance(hours_str, str):
        return True
    parts = [p.strip() for p in hours_str.split("-")]
    if len(parts) != 2:
        return True
    open_min = _time_to_minutes(parts[0])
    close_min = _time_to_minutes(parts[1])
    if open_min is None or close_min is None:
        return True
    if close_min == 0:
        close_min = 24 * 60
    # Place is open [open_min, close_min). User interval [start_min, end_min] is contained if open_min <= start_min and close_min >= end_min.
    return open_min <= start_min and close_min >= end_min


def _parse_hours_to_start_end(hours_str):
    """
    Split stored hours (e.g. '9:00-17:00') into start and end for pre-filling create/edit dropdowns.
    Used when loading the edit form so the two dropdowns show the current saved hours.
    Returns ('00:00', '24:00') if missing or unparseable.
    """
    if not hours_str or not isinstance(hours_str, str):
        return "00:00", "24:00"
    parts = [p.strip() for p in hours_str.split("-")]
    if len(parts) != 2:
        return "00:00", "24:00"
    start_t, end_t = parts[0], parts[1]
    if _time_to_minutes(start_t) is None or _time_to_minutes(end_t) is None:
        return "00:00", "24:00"
    return start_t, end_t


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

app = Flask(__name__)

# Secret key required for sessions; use env SECRET_KEY in production
app.secret_key = os.getenv("SECRET_KEY") or "dev-secret-key-change-in-production"

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
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

# ---------------
# Root
# ---------------
# the root page should redirect to home page
# the authentification logic to check if the user is logged in or not
# and furthur redirect to login / sign up page should be verified on the home page
@app.get("/")
def root():
    return redirect('/home')

# ---------------
# Login 
# ---------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user_data = users_collection.find_one({"email": email})
        
        # if user_data and user_data["password"] == password:
        if user_data and check_password_hash(user_data["password"], str(password)):
            user = User(user_data)
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("home"))

        return render_template("login.html", error="Invalid email or password.")

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

        # hash the password for security
        password_hash = generate_password_hash(str(password))

        users_collection.insert_one({
            "netid": user_name,
            "email": email,
            "password": password_hash,
            "posts": []
        })

        return redirect(url_for("login"))

    return render_template("signup.html")


@login_required
@app.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("root"))

# ---------------
# Home Page
# ---------------
@app.get("/home")
@login_required
def home():
    # Homepage: search by name (q) and optional filters from query string
    q = request.args.get("q", "").strip()
    noise_level = request.args.get("noise_level", "").strip()
    wifi = request.args.get("wifi", "").strip()
    outlets = request.args.get("outlets", "").strip()
    reservable = request.args.get("reservable", "").strip()
    start_time = request.args.get("start_time", "").strip()
    end_time = request.args.get("end_time", "").strip()

    # Build one MongoDB query: name search + noise level (seating), wifi, outlets, reservable
    filters = []

    if q:
        filters.append({"location": {"$regex": q, "$options": "i"}})

    # Noise level filter uses seating field (Silent Study / Quiet Pair / Fit for Group from create form)
    if noise_level:
        filters.append({"seating": noise_level})

    if wifi:
        filters.append({"wifi": wifi})

    if outlets:
        filters.append({"outlets": outlets})

    if reservable:
        filters.append({"reservable": reservable})

    query = {"$and": filters} if filters else {}

    posts = list(posts_collection.find(query).sort("created_at", -1).limit(50))

    # Apply time filter in Python: show place only if its opening hours contain the chosen interval (or only start/only end)
    if start_time or end_time:
        start_min = _time_to_minutes(start_time) if start_time else 0
        end_min = _time_to_minutes(end_time) if end_time else 24 * 60
        if start_time and not end_time:
            end_min = start_min + 1  # open at start means close > start
        elif not start_time and end_time:
            start_min = 0
            end_min = end_min + 1  # still open at end means close > end
        if start_min is not None and end_min is not None and start_min <= end_min:
            posts = [p for p in posts if _hours_contain_interval(p.get("hours"), start_min, end_min)]

    for p in posts:
        p["_id"] = str(p["_id"])

    # Same hour options as create/edit so homepage filter and stored hours use the same format
    time_options = [f"{h:02d}:00" for h in range(25)]
    return render_template(
        "home.html",
        posts=posts,
        q=q,
        noise_level=noise_level,
        wifi=wifi,
        outlets=outlets,
        reservable=reservable,
        start_time=start_time,
        end_time=end_time,
        time_options=time_options,
    )

# ---------------
# View Post
# ---------------
@app.route("/posts/<post_id>")
@login_required
def view_post(post_id):
    post = posts_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        return "Post not found", 404
    return render_template("view_post.html", post=post)

# ---------------
# Create Post
# ---------------
# Hour options for opening-hours dropdowns (00:00–24:00); shared with edit and homepage filter
_TIME_OPTIONS = [f"{h:02d}:00" for h in range(25)]


@app.route("/posts/create", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        hours_start = (request.form.get("hours_start") or "").strip()
        hours_end = (request.form.get("hours_end") or "").strip()
        # Validate: end time must be after start time; if not, show error and re-render form with all inputs kept
        hours_error = None
        if hours_start and hours_end:
            start_min = _time_to_minutes(hours_start)
            end_min = _time_to_minutes(hours_end)
            if start_min is None or end_min is None or start_min >= end_min:
                hours_error = "End time must be after start time."
        if hours_error:
            # Re-render create form with submitted values and red error message beside time fields
            post = {
                "location": request.form.get("location", ""),
                "googlemaps": request.form.get("googlemaps", ""),
                "seating": request.form.get("seating", ""),
                "wifi": request.form.get("wifi", ""),
                "outlets": request.form.get("outlets", ""),
                "reservable": request.form.get("reservable", ""),
                "climate": request.form.get("climates", ""),
                "hours_start": hours_start,
                "hours_end": hours_end,
            }
            return render_template("create_post.html", post=post, time_options=_TIME_OPTIONS, hours_error=hours_error)

        hours = f"{hours_start}-{hours_end}" if hours_start and hours_end else ""
        post_data = {
            "netid": request.form.get("netid"),
            "location": request.form.get("location"),
            "googlemaps": request.form.get("googlemaps"),
            "noise_level": request.form.get("noise_level"),
            "seating": request.form.get("seating"),
            "wifi": request.form.get("wifi"),
            "outlets": request.form.get("outlets"),
            "reservable": request.form.get("reservable"),
            "climate": request.form.get("climate") or request.form.get("climates"),
            "hours": hours,
            "created_at": datetime.datetime.utcnow()
        }

        result = posts_collection.insert_one(post_data)
        return redirect(url_for("view_post", post_id=result.inserted_id))

    empty_post = {
        "location": "",
        "googlemaps": "",
        "seating": "",
        "wifi": "",
        "outlets": "",
        "reservable": "",
        "climate": "",
        "hours_start": "",
        "hours_end": "",
    }
    return render_template("create_post.html", post=empty_post, time_options=_TIME_OPTIONS)

# ---------------
# Edit Post
# ---------------
@app.route("/posts/<post_id>/edit", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = posts_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        return "Post not found", 404
    if request.method == "POST":
        hours_start = (request.form.get("hours_start") or "").strip()
        hours_end = (request.form.get("hours_end") or "").strip()
        # Same validation as create: end must be after start; on error re-render with form values and red message
        hours_error = None
        if hours_start and hours_end:
            start_min = _time_to_minutes(hours_start)
            end_min = _time_to_minutes(hours_end)
            if start_min is None or end_min is None or start_min >= end_min:
                hours_error = "End time must be after start time."
        updated_data = {
            "netid": request.form.get("netid"),
            "location": request.form.get("location"),
            "googlemaps": request.form.get("googlemaps"),
            "noise_level": request.form.get("noise_level"),
            "seating": request.form.get("seating"),
            "wifi": request.form.get("wifi"),
            "outlets": request.form.get("outlets"),
            "reservable": request.form.get("reservable"),
            "climate": request.form.get("climate"),
            "hours_start": hours_start,
            "hours_end": hours_end,
        }
        if hours_error:
            updated_data["_id"] = str(post["_id"])
            return render_template("edit_post.html", post=updated_data, time_options=_TIME_OPTIONS, hours_error=hours_error)
        hours = f"{hours_start}-{hours_end}" if hours_start and hours_end else ""
        updated_data["hours"] = hours
        del updated_data["hours_start"]
        del updated_data["hours_end"]
        # Persist only DB fields; then re-add hours_start/end for template dropdowns
        posts_collection.update_one({"_id": ObjectId(post_id)}, {"$set": updated_data})
        updated_data["_id"] = str(post["_id"])
        updated_data["hours_start"], updated_data["hours_end"] = hours_start, hours_end
        return render_template("edit_post.html", post=updated_data, time_options=_TIME_OPTIONS, message="Post updated successfully!")
    post["_id"] = str(post["_id"])
    # Pre-fill hours dropdowns from stored string (e.g. '9:00-17:00' -> start=09:00, end=17:00)
    post["hours_start"], post["hours_end"] = _parse_hours_to_start_end(post.get("hours"))
    return render_template("edit_post.html", post=post, time_options=_TIME_OPTIONS)

# ---------------
# Delete Post
# ---------------
@app.route("/posts/<post_id>/delete", methods=["GET", "POST"])
def delete_post(post_id):
    post = posts_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        return "Post not found", 404
    if request.method == "GET":
        post["_id"] = str(post["_id"])
        return render_template("delete_confirm.html", post=post)
    posts_collection.delete_one({"_id": ObjectId(post_id)})
    return redirect(url_for("home"))

# ---------------
# Map Page
# ---------------
@app.get("/map")
@login_required
def map_page():
    # retrieve posts from db
    posts = list(posts_collection.find({}))

    # for passing it to the html as json
    for p in posts:
        p["_id"] = str(p["_id"])

    # parsing google map links to location
    for p in posts:
        link = str(p["googlemaps"])
        parsed = re.search(r'@(-?\d+\.?\d*),(-?\d+\.?\d*)', link)
        if parsed:
            p["latlng"] = { "lat": float(parsed.group(1)), "lng": float(parsed.group(2)) }
            # print(p["latlng"])

    return render_template("map.html", posts=posts)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)