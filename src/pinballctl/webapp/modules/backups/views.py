from flask import render_template
from . import bp

@bp.get('/')
def index():
    return render_template('backups.html', title='Backup / Restore')
