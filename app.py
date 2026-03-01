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
MONGO_HOST = os.getenv("MONGO_HOST", "mongo")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_DBNAME = os.getenv("MONGO_DBNAME")


MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DBNAME}?authSource=admin"

client = MongoClient(MONGO_URI)
db = client[MONGO_DBNAME]
posts_collection = db.posts
users_collection = db.users

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
@app.route("/posts/create", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        post_data = {
            "netid": request.form.get("netid"),
            "location": request.form.get("location"),
            "googlemaps": request.form.get("googlemaps"),
            "noise_level": request.form.get("noise_level"),
            "seating": request.form.get("seating"),
            "wifi": request.form.get("wifi"),
            "outlets": request.form.get("outlets"),
            "reservable": request.form.get("reservable"),
            "climate": request.form.get("climate"),
            "hours": request.form.get("hours"),
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

    return render_template("create_post.html", post=empty_post)

# ---------------
# Edit Post
# ---------------
@app.route("/posts/<post_id>/edit", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = posts_collection.find_one({"_id": ObjectId(post_id)})
    if request.method == "POST":
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
            "hours": request.form.get("hours")
        }
        posts_collection.update_one({"_id": ObjectId(post_id)}, {"$set": updated_data})
        return render_template("edit_post.html", post=updated_data, message="Post updated successfully!")
    return render_template("edit_post.html", post=post)

# ---------------
# Delete Post
# ---------------
@app.route("/posts/<post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    posts_collection.delete_one({"_id": ObjectId(post_id)})
    return "Deleted successfully", 200

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