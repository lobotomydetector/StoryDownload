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

@app.route('/api/proxy')
def proxy():
    """Proxy endpoint to stream media files using ID (hides source URL)"""
    media_id = request.args.get('id')
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
        
        # Stream the content back to the client
        return Response(
            response.iter_content(chunk_size=8192),
            headers={
                'Content-Type': content_type,
                'Cache-Control': 'public, max-age=3600'
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
        
        # Extract Instagram media ID from URL (e.g., "587269090_18613442032019133_...")
        import re
        media_id_part = None
        id_match = re.search(r'(\d+)_\d+_\d+', url)
        if id_match:
            media_id_part = id_match.group(1)[:10]  # First 10 digits to keep it short
        
        # Determine file extension
        content_type = response.headers.get('content-type', '')
        if 'video' in content_type or url.endswith('.mp4'):
            ext = 'mp4'
        elif 'image' in content_type or any(url.endswith(e) for e in ['.jpg', '.jpeg', '.png']):
            ext = 'jpg'
        else:
            ext = 'bin'
        
        # Create filename: username_mediaID.ext
        if media_id_part:
            filename = f'{username}_{media_id_part}.{ext}'
        else:
            filename = f'{username}_story.{ext}'
        
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
