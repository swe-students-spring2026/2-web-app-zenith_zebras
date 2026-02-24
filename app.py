from flask import Flask, request, jsonify, redirect, url_for, render_template
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime
import os
from dotenv import load_dotenv
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

app = Flask(__name__)

# This is temparary until we implement auth, so we can use url_for() in templates without crashing
@app.get("/")
def root():
    return render_template("home.html")

# ---------------
# Auth guard
# ---------------


# ---------------
# landing
# ---------------


# ---------------
# Login / Signup
# ---------------
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
    return redirect(url_for("root"))

# ---------------
# Home Page
# ---------------
@app.get("/home")
#@login_required
def home():
    #Search Querey
    q = request.args.get("q", "").strip()

    query = {}
    if q:
        # I have no idea what the database schema so adjust field name as needed
        query = {"place_name": {"$regex": q, "$options": "i"}}

    #show newest first
    posts = list(posts_collection.find(query).sort("created_at", -1).limit(50))
    for p in posts:
        p["_id"] = str(p["_id"])
    return render_template("home.html", posts=posts, q=q)

# ---------------
# View Post
# ---------------
@app.route("/posts/<post_id>")
def view_post(post_id):
    post = posts_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        return "Post not found", 404
    return render_template("view_post.html", post=post)

# ---------------
# Create Post
# ---------------
@app.route("/posts/create", methods=["GET", "POST"])
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
            "hours": request.form.get("hours")
        }
        posts_collection.insert_one(post_data)
        return render_template("create_post.html", message="Post created successfully!")
    return render_template("create_post.html")

# ---------------
# Edit Post
# ---------------
@app.route("/posts/<post_id>/edit", methods=["GET", "POST"])
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
def delete_post(post_id):
    posts_collection.delete_one({"_id": ObjectId(post_id)})
    return "Deleted successfully", 200

# ---------------
# Map Page
# ---------------
@app.get("/map")
def map_page():
    posts = list(posts_collection.find({}, {"location": 1, "googlemaps": 1, "_id": 1}))
    print(posts)
    for p in posts:
        p["_id"] = str(p["id"])
    print(posts)
    return render_template("map.html", posts=posts)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)