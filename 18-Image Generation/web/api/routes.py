from flask import Blueprint, jsonify, request, current_app, url_for
from flask_cors import cross_origin
import os
import time
from pathlib import Path
from generator import generate_profile, get_profile_data, list_profiles

# Create API blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/generate', methods=['POST'])
@cross_origin()
def generate():
    """Generate a new profile with multiple images"""
    try:
        # Get parameters from request (with defaults)
        data = request.get_json() or {}
        num_images = data.get('num_images', 8)
        
        # Limit the number of images to generate
        if num_images > 10:
            num_images = 10
        
        # Generate the profile
        profile_id, image_count, error = generate_profile(num_images)
        
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 500
            
        if not profile_id:
            return jsonify({
                'success': False,
                'error': 'Failed to generate profile'
            }), 500
            
        # Return profile data
        profile_data = get_profile_data(profile_id)
        
        # Build response
        return jsonify({
            'success': True,
            'profile_id': profile_id,
            'image_count': image_count,
            'data': profile_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/profiles', methods=['GET'])
@cross_origin()
def profiles():
    """List recent profiles"""
    try:
        limit = request.args.get('limit', 10, type=int)
        profiles = list_profiles(limit)
        
        return jsonify({
            'success': True,
            'profiles': profiles
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/profile/<profile_id>', methods=['GET'])
@cross_origin()
def get_profile(profile_id):
    """Get data for a specific profile"""
    try:
        profile_data = get_profile_data(profile_id)
        
        if not profile_data:
            return jsonify({
                'success': False,
                'error': 'Profile not found'
            }), 404
            
        return jsonify({
            'success': True,
            'data': profile_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500