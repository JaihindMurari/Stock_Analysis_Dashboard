"""
Main Blueprint — HTML page routes.
"""
from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', active='dashboard')


@main_bp.route('/stock/<symbol>')
def stock_detail(symbol):
    return render_template('stock_detail.html', symbol=symbol.upper(), active='stock')


@main_bp.route('/signals')
def signals_page():
    return render_template('signals.html', active='signals')


@main_bp.route('/trends')
def trends_page():
    return render_template('trends.html', active='trends')
