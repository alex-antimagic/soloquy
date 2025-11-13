from flask import render_template
from app.blueprints.pages import pages


@pages.route('/privacy')
def privacy():
    """Privacy Policy page"""
    return render_template('pages/privacy.html', title='Privacy Policy')


@pages.route('/terms')
def terms():
    """Terms of Service page"""
    return render_template('pages/terms.html', title='Terms of Service')


@pages.route('/help')
def help():
    """Help and Documentation page"""
    return render_template('pages/help.html', title='Help & Support')
