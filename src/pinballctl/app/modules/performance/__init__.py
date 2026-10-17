"""Shared bridge performance monitoring."""
from flask import Blueprint
bp = Blueprint('performance', __name__, template_folder='templates', static_folder='static')
api_bp = Blueprint('performance_api', __name__)
MODULE_META = {'title': 'Performance', 'order': 15, 'icon': 'chart-line', 'category': 'platform'}
