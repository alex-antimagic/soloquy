from flask import render_template, redirect, url_for, make_response
from flask_login import current_user
from app.blueprints.marketing import marketing_bp
from datetime import datetime


@marketing_bp.route('/')
def index():
    """Marketing homepage - public landing page"""
    if current_user.is_authenticated:
        return redirect(url_for('tenant.home'))
    return render_template('marketing/index.html')


@marketing_bp.route('/pricing')
def pricing():
    """Full pricing page with detailed feature comparison"""
    return render_template('marketing/pricing.html')


@marketing_bp.route('/demo')
def demo():
    """Demo request page"""
    return render_template('marketing/demo.html')


@marketing_bp.route('/sitemap.xml')
def sitemap():
    """Generate XML sitemap for SEO"""
    pages = [
        {'url': url_for('marketing.index', _external=True), 'priority': '1.0'},
        {'url': url_for('marketing.pricing', _external=True), 'priority': '0.9'},
        {'url': url_for('pages.help', _external=True), 'priority': '0.7'},
        {'url': url_for('pages.privacy', _external=True), 'priority': '0.5'},
        {'url': url_for('pages.terms', _external=True), 'priority': '0.5'},
    ]

    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{page["url"]}</loc>\n'
        sitemap_xml += f'    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>\n'
        sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
        sitemap_xml += '  </url>\n'

    sitemap_xml += '</urlset>'

    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response
