from flask import render_template
from . import bp

@bp.get('/')
def index():
    return render_template('performance.html', title=' · Performance')
