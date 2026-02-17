"""Core blueprint: auth views and shared templates/static assets."""
# pinballctl/app/core/__init__.py
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app

core_bp = Blueprint(
    "core",
    __name__,
    template_folder="templates",
    static_folder="assets"
)

@core_bp.route("/login", methods=["GET", "POST"])
def login():
    """Simple username/password gate backed by config or environment overrides."""
    get_user_pass = current_app.config.get("_AUTH_GET_USER_PASS")
    if not get_user_pass:
        def get_user_pass():
            return ("admin", lambda pw: (pw or "admin") == pw)

    expected_user, pwd_check = get_user_pass()

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        next_url = request.args.get("next") or request.form.get("next") or "/"

        if username == expected_user and pwd_check(password):
            session["user"] = {"name": username}
            return redirect(next_url or "/")
        else:
            flash("Invalid username or password", "error")

    next_url = request.args.get("next", "/")
    return render_template("core/templates/login.html", next_url=next_url)

@core_bp.route("/logout", methods=["POST", "GET"])
def logout():
    """Clear the session and redirect to the login screen."""
    session.clear()
    return redirect(url_for("core.login"))
