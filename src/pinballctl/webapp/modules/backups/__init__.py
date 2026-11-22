"""Project backup library and guarded replacement restore."""
from flask import Blueprint
bp = Blueprint('backups', __name__, template_folder='templates', static_folder='static')
api_bp = Blueprint('backups_api', __name__)
MODULE_META = {'title':'Backup / Restore','category':'overview','order':85,'icon':'box-archive'}
