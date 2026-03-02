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

load_dotenv()

MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_HOST = os.getenv("MONGO_HOST", "study_spots_mongo")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_DBNAME = os.getenv("MONGO_DBNAME")


# Use auth when MONGO_USER/MONGO_PASSWORD set; Mongo init uses same vars via docker-compose
MONGO_URI = (
    f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DBNAME}?authSource=admin"
    if MONGO_USER and MONGO_PASSWORD
    else f"mongodb://{MONGO_HOST}:{MONGO_PORT}/{MONGO_DBNAME}"
)
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
    #Search Querey
    q = request.args.get("q", "").strip()

    query = {}
    if q:
        query = {"location": {"$regex": q, "$options": "i"}}

    #show newest first
    posts = list(posts_collection.find(query).sort("created_at", -1).limit(50))
    for p in posts:
        p["_id"] = str(p["_id"])
    return render_template("home.html", posts=posts, q=q)

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
# Preset climate options for datalist; user can pick from list or type custom value
CLIMATE_OPTIONS = ["Cool", "Comfortable", "Warm"]


def _is_valid_google_maps_url(url):
    """Check if URL looks like a valid Google Maps link (google.com/maps, goo.gl/maps, maps.google)."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if not u.startswith("http://") and not u.startswith("https://"):
        return False
    u = u.lower()
    return ("google" in u and "maps" in u) or "goo.gl/maps" in u


def _validate_hours(hours_str):
    """Validate hours format 'HH:MM-HH:MM' and end > start. Returns (True, None) or (False, error_msg). Used by create/edit when hours validation is enabled."""
    if not hours_str or not isinstance(hours_str, str):
        return False, "Hours are required."
    parts = [p.strip() for p in hours_str.split("-")]
    if len(parts) != 2:
        return False, "Use format: Open-Close (e.g. 9:00-17:00)."
    m = re.match(r"^(\d{1,2}):(\d{2})$", parts[0])
    n = re.match(r"^(\d{1,2}):(\d{2})$", parts[1])
    if not m or not n:
        return False, "Use format: HH:MM-HH:MM (e.g. 9:00-17:00)."
    h1, mn1 = int(m.group(1)), int(m.group(2))
    h2, mn2 = int(n.group(1)), int(n.group(2))
    if h1 < 0 or h1 > 24 or mn1 < 0 or mn1 > 59 or (h1 == 24 and mn1 != 0):
        return False, "Invalid start time."
    if h2 < 0 or h2 > 24 or mn2 < 0 or mn2 > 59 or (h2 == 24 and mn2 != 0):
        return False, "Invalid end time."
    start_min = h1 * 60 + mn1 if h1 < 24 else 24 * 60
    end_min = h2 * 60 + mn2 if h2 < 24 else 24 * 60
    if start_min >= end_min:
        return False, "End time must be after start time."
    return True, None


@app.route("/posts/create", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        form = request.form
        googlemaps = (form.get("googlemaps") or "").strip()
        hours = (form.get("hours") or "").strip()
        # Validate Google Maps URL; on error re-render form with all fields kept
        googlemaps_error = None if _is_valid_google_maps_url(googlemaps) else "Invalid Google Maps URL. Use a link from Google Maps."
        hours_ok, hours_error = _validate_hours(hours)
        if hours_ok:
            hours_error = None

        if googlemaps_error or hours_error:
            # Re-render create form with submitted values and red error under invalid field(s)
            post = {
                "location": form.get("location", ""),
                "googlemaps": googlemaps,
                "seating": form.get("seating", ""),
                "wifi": form.get("wifi", ""),
                "outlets": form.get("outlets", ""),
                "reservable": form.get("reservable", ""),
                "climate": form.get("climate", ""),
                "hours": hours,
            }
            return render_template("create_post.html", post=post, climate_options=CLIMATE_OPTIONS, googlemaps_error=googlemaps_error, hours_error=hours_error)

        climate = (form.get("climate") or "").strip()
        post_data = {
            "netid": form.get("netid"),
            "location": form.get("location"),
            "googlemaps": googlemaps,
            "noise_level": form.get("noise_level"),
            "seating": form.get("seating"),
            "wifi": form.get("wifi"),
            "outlets": form.get("outlets"),
            "reservable": form.get("reservable"),
            "climate": climate,
            "hours": hours,
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
        "hours": ""
    }

    return render_template("create_post.html", post=empty_post, climate_options=CLIMATE_OPTIONS)

# ---------------
# Edit Post
# ---------------
@app.route("/posts/<post_id>/edit", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = posts_collection.find_one({"_id": ObjectId(post_id)})
    if request.method == "POST":
        form = request.form
        googlemaps = (form.get("googlemaps") or "").strip()
        hours = (form.get("hours") or "").strip()
        # Validate Google Maps URL; on error re-render form with all fields kept
        googlemaps_error = None if _is_valid_google_maps_url(googlemaps) else "Invalid Google Maps URL. Use a link from Google Maps."
        hours_ok, hours_error = _validate_hours(hours)
        if hours_ok:
            hours_error = None

        if googlemaps_error or hours_error:
            # Re-render edit form with submitted values and red error under invalid field(s)
            updated_data = {
                "netid": form.get("netid"),
                "location": form.get("location"),
                "googlemaps": googlemaps,
                "noise_level": form.get("noise_level"),
                "seating": form.get("seating"),
                "wifi": form.get("wifi"),
                "outlets": form.get("outlets"),
                "reservable": form.get("reservable"),
                "climate": form.get("climate", ""),
                "hours": hours,
            }
            updated_data["_id"] = str(post["_id"])
            return render_template("edit_post.html", post=updated_data, climate_options=CLIMATE_OPTIONS, googlemaps_error=googlemaps_error, hours_error=hours_error)

        climate = (form.get("climate") or "").strip()
        updated_data = {
            "netid": form.get("netid"),
            "location": form.get("location"),
            "googlemaps": googlemaps,
            "noise_level": form.get("noise_level"),
            "seating": form.get("seating"),
            "wifi": form.get("wifi"),
            "outlets": form.get("outlets"),
            "reservable": form.get("reservable"),
            "climate": climate,
            "hours": hours,
        }
        posts_collection.update_one({"_id": ObjectId(post_id)}, {"$set": updated_data})
        updated_data["_id"] = str(post["_id"])
        return render_template("edit_post.html", post=updated_data, climate_options=CLIMATE_OPTIONS, message="Post updated successfully!")
    post["_id"] = str(post["_id"])
    return render_template("edit_post.html", post=post, climate_options=CLIMATE_OPTIONS)

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