from flask import Blueprint, render_template

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    # will write filters and results later, for now just booting page
    return render_template("index.html")