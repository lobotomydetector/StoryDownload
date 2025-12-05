#!/usr/bin/env python3
"""
Flask web server for Instagram Stories Viewer
Provides a web UI for fetching and viewing Instagram stories
"""

from flask import Flask, render_template, request, jsonify, send_file, Response
from fetch_stories import fetch_stories
import requests
import os

import uuid

app = Flask(__name__)

# In-memory cache to store media URLs (id -> url)
# Note: In a production environment with multiple workers, use Redis or a database
MEDIA_CACHE = {}

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/api/fetch', methods=['POST'])
def fetch():
    """API endpoint to fetch stories for a username"""
    data = request.get_json()
    username = data.get('username', '').strip().lstrip('@')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    # Fetch raw stories
    raw_stories = fetch_stories(username, silent=True)
    
    # Transform stories to hide URLs
    safe_stories = []
    for story in raw_stories:
        # Generate a unique ID for this media
        media_id = str(uuid.uuid4())
        
        # Store the mapping
        MEDIA_CACHE[media_id] = story['url']
        
        # Add to safe list (without the original URL)
        safe_stories.append({
            'id': media_id,
            'type': story['type']
        })
    
    return jsonify({
        'username': username,
        'stories': safe_stories,
        'count': len(safe_stories)
    })

import base64
import json
import re

def get_media_filename(url, username):
    """Generate a unique filename for the media URL"""
    media_id_part = None
    
    # Strategy 1: Regex for standard image IDs (e.g. 123_456_789)
    id_match = re.search(r'(\d+)_\d+_\d+', url)
    if id_match:
        media_id_part = id_match.group(1)[:15]
    
    # Strategy 2: Decode 'efg' parameter for video IDs
    if not media_id_part and 'efg=' in url:
        try:
            # Extract efg value
            efg_match = re.search(r'efg=([^&]+)', url)
            if efg_match:
                # Add padding if needed for base64
                efg_str = efg_match.group(1)
                padded = efg_str + '=' * (-len(efg_str) % 4)
                decoded = base64.urlsafe_b64decode(padded)
                data = json.loads(decoded)
                
                # Look for various ID fields
                for key in ['xpv_asset_id', 'asset_id', 'image_id', 'id']:
                    if key in data:
                        media_id_part = str(data[key])[:15]
                        break
        except Exception:
            pass
            
    # Strategy 3: Fallback to hash of URL
    if not media_id_part:
        import hashlib
        media_id_part = hashlib.md5(url.encode()).hexdigest()[:10]
        
    # Determine extension
    ext = 'bin'
    if '.mp4' in url or 'video' in url:
        ext = 'mp4'
    elif '.jpg' in url or '.jpeg' in url or 'image' in url:
        ext = 'jpg'
    elif '.png' in url:
        ext = 'png'
        
    return f'{username}_{media_id_part}.{ext}'

@app.route('/api/proxy')
def proxy():
    """Proxy endpoint to stream media files using ID (hides source URL)"""
    media_id = request.args.get('id')
    username = request.args.get('username', 'story')
    
    if not media_id:
        return jsonify({'error': 'Media ID required'}), 400
    
    url = MEDIA_CACHE.get(media_id)
    if not url:
        return jsonify({'error': 'Invalid or expired media ID'}), 404
    
    try:
        # Fetch the media file
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Forward the content type
        content_type = response.headers.get('content-type', 'application/octet-stream')
        
        # Generate filename for "Save As" actions even when viewing inline
        filename = get_media_filename(url, username)
        
        # Stream the content back to the client
        return Response(
            response.iter_content(chunk_size=8192),
            headers={
                'Content-Type': content_type,
                'Cache-Control': 'public, max-age=3600',
                'Content-Disposition': f'inline; filename="{filename}"'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download')
def download():
    """Proxy endpoint to download media files using ID"""
    media_id = request.args.get('id')
    username = request.args.get('username', 'story')
    
    if not media_id:
        return jsonify({'error': 'Media ID required'}), 400
        
    url = MEDIA_CACHE.get(media_id)
    if not url:
        return jsonify({'error': 'Invalid or expired media ID'}), 404
    
    try:
        # Fetch the media file
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Generate filename
        filename = get_media_filename(url, username)
        
        # Create response with download headers
        return Response(
            response.iter_content(chunk_size=8192),
            headers={
                'Content-Type': response.headers.get('content-type', 'application/octet-stream'),
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
