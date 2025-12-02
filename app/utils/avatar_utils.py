"""
Avatar utility functions for resizing and optimizing avatar images
"""
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def resize_avatar_url(avatar_url, size=128):
    """
    Resize an avatar URL to a specific size for faster loading.
    Supports Cloudinary URLs and UI Avatars placeholders.

    Args:
        avatar_url: The original avatar URL
        size: The desired size in pixels (default: 128)

    Returns:
        Resized avatar URL
    """
    if not avatar_url:
        return None

    # Handle Cloudinary URLs
    if 'cloudinary.com' in avatar_url or 'res.cloudinary.com' in avatar_url:
        return resize_cloudinary_avatar(avatar_url, size)

    # Handle UI Avatars placeholders
    if 'ui-avatars.com' in avatar_url:
        return resize_ui_avatars(avatar_url, size)

    # For other URLs, return as-is (external images)
    return avatar_url


def resize_cloudinary_avatar(cloudinary_url, size=128):
    """
    Add Cloudinary transformation to resize and optimize an avatar image.

    Args:
        cloudinary_url: Original Cloudinary URL
        size: Desired size in pixels

    Returns:
        Transformed Cloudinary URL with resizing
    """
    # Cloudinary transformation format:
    # https://res.cloudinary.com/cloud_name/image/upload/w_128,h_128,c_fill,g_face,q_auto,f_auto/path/to/image

    # Find the upload segment and inject transformation
    if '/upload/' in cloudinary_url:
        transformation = f'w_{size},h_{size},c_fill,g_face,q_auto,f_auto'
        # Replace /upload/ with /upload/{transformation}/
        return cloudinary_url.replace('/upload/', f'/upload/{transformation}/')

    # If URL doesn't have /upload/, return as-is
    return cloudinary_url


def resize_ui_avatars(ui_avatars_url, size=128):
    """
    Resize a UI Avatars placeholder URL.

    Args:
        ui_avatars_url: Original UI Avatars URL
        size: Desired size in pixels

    Returns:
        UI Avatars URL with size parameter
    """
    # Parse the URL
    parsed = urlparse(ui_avatars_url)

    # Parse existing query parameters
    params = parse_qs(parsed.query)

    # Update or add size parameter
    params['size'] = [str(size)]

    # Rebuild the query string
    new_query = urlencode(params, doseq=True)

    # Rebuild the URL
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


def get_avatar_sizes():
    """
    Get recommended avatar sizes for different use cases.

    Returns:
        Dictionary of size presets
    """
    return {
        'thumbnail': 48,   # Small thumbnails in lists
        'small': 64,       # Compact displays
        'medium': 128,     # Default avatar size
        'large': 256,      # Profile pages
        'xlarge': 512,     # High-res displays
    }
