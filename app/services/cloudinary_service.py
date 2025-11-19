"""
Cloudinary Service
Handles image uploads to Cloudinary cloud storage
"""
import cloudinary
import cloudinary.uploader
from flask import current_app
from typing import Dict, Optional


def init_cloudinary():
    """Initialize Cloudinary with config from Flask app"""
    cloudinary.config(
        cloud_name=current_app.config.get('CLOUDINARY_CLOUD_NAME'),
        api_key=current_app.config.get('CLOUDINARY_API_KEY'),
        api_secret=current_app.config.get('CLOUDINARY_API_SECRET'),
        secure=True
    )


def upload_image(file_content, folder: str = "bug_reports") -> Optional[Dict[str, str]]:
    """
    Upload an image to Cloudinary

    Args:
        file_content: File object or file path to upload
        folder: Cloudinary folder to store the image (default: "bug_reports")

    Returns:
        Dictionary with 'url', 'secure_url', and 'public_id' if successful, None if failed

    Raises:
        Exception: If upload fails
    """
    try:
        # Initialize Cloudinary if not already done
        init_cloudinary()

        # Upload the image to Cloudinary
        result = cloudinary.uploader.upload(
            file_content,
            folder=folder,
            resource_type="image",
            allowed_formats=['png', 'jpg', 'jpeg', 'gif'],
            transformation=[
                {'width': 1920, 'height': 1080, 'crop': 'limit'},  # Max resolution
                {'quality': 'auto:good'}  # Automatic quality optimization
            ]
        )

        return {
            'url': result.get('url'),
            'secure_url': result.get('secure_url'),
            'public_id': result.get('public_id'),
            'format': result.get('format'),
            'width': result.get('width'),
            'height': result.get('height'),
            'bytes': result.get('bytes')
        }

    except Exception as e:
        current_app.logger.error(f"Failed to upload image to Cloudinary: {str(e)}")
        raise


def upload_file(file_content, folder: str = "chat_files") -> Optional[Dict[str, str]]:
    """
    Upload any file type to Cloudinary (PDFs, CSVs, documents, etc.)

    Args:
        file_content: File object or file path to upload
        folder: Cloudinary folder to store the file (default: "chat_files")

    Returns:
        Dictionary with 'url', 'secure_url', 'public_id', 'format', and 'bytes' if successful

    Raises:
        Exception: If upload fails
    """
    try:
        # Initialize Cloudinary if not already done
        init_cloudinary()

        # Upload the file to Cloudinary as a raw resource
        result = cloudinary.uploader.upload(
            file_content,
            folder=folder,
            resource_type="raw"  # Allows any file type
        )

        return {
            'url': result.get('url'),
            'secure_url': result.get('secure_url'),
            'public_id': result.get('public_id'),
            'format': result.get('format'),
            'bytes': result.get('bytes'),
            'resource_type': result.get('resource_type')
        }

    except Exception as e:
        current_app.logger.error(f"Failed to upload file to Cloudinary: {str(e)}")
        raise


def delete_image(public_id: str) -> bool:
    """
    Delete an image from Cloudinary

    Args:
        public_id: The public ID of the image to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        init_cloudinary()
        result = cloudinary.uploader.destroy(public_id)
        return result.get('result') == 'ok'

    except Exception as e:
        current_app.logger.error(f"Failed to delete image from Cloudinary: {str(e)}")
        return False


def get_image_url(public_id: str, transformation: Optional[Dict] = None) -> str:
    """
    Get the URL for an image with optional transformations

    Args:
        public_id: The public ID of the image
        transformation: Optional Cloudinary transformation parameters

    Returns:
        The secure URL of the image
    """
    try:
        init_cloudinary()

        if transformation:
            return cloudinary.CloudinaryImage(public_id).build_url(**transformation)
        else:
            return cloudinary.CloudinaryImage(public_id).build_url()

    except Exception as e:
        current_app.logger.error(f"Failed to get image URL: {str(e)}")
        return ""
