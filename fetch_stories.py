#!/usr/bin/env python3
"""
Instagram Stories Fetcher using Popygram
Usage: python fetch_stories.py <username>
"""

import sys
import requests
from bs4 import BeautifulSoup
import json
import re


def fetch_stories(username, silent=False):
    """Fetch Instagram stories for a given username via Popygram.
    
    Args:
        username: Instagram username to fetch stories for
        silent: If True, suppress console output (for API usage)
    """
    
    url = "https://www.popygram.com/view"
    
    # Use standard form data (not multipart)
    data = {
        'username': username,
        'fetch_method': 'allstories'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.popygram.com/',
        'Origin': 'https://www.popygram.com'
    }
    
    try:
        if not silent:
            print(f"[*] Fetching stories for @{username}...")
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for "no stories" message first
        no_stories_divs = soup.find_all('div', string=re.compile(r'no stories', re.IGNORECASE))
        if no_stories_divs:
            if not silent:
                print(f"[!] No stories found for @{username}")
                print("    (Account may be private or have no active stories)")
            return []
        
        # Find all story media
        stories = []
        
        # Popygram puts stories in divs with class containing "story" or in a grid
        # Look for images and videos in the row/grid that contains stories
        row_div = soup.find('div', class_=re.compile(r'row.*g-4'))
        
        if row_div:
            # Find all images in the stories container
            for img in row_div.find_all('img'):
                src = img.get('src', '')
                if src and ('cdninstagram' in src or 'media.php' in src):
                    # Clean up the URL
                    if src.startswith('/'):
                        src = f"https://www.popygram.com{src}"
                    stories.append({
                        'type': 'image',
                        'url': src
                    })
            
            # Find all videos in the stories container  
            for video in row_div.find_all('video'):
                src = video.get('src', '')
                if src:
                    if src.startswith('/'):
                        src = f"https://www.popygram.com{src}"
                    stories.append({
                        'type': 'video',
                        'url': src
                    })
        
        # If no stories found in container, scan entire page
        if not stories:
            for img in soup.find_all('img'):
                src = img.get('src', '')
                # Filter for Instagram CDN URLs or Popygram media proxy
                if 'cdninstagram.com' in src or ('media.php' in src and 'popygram.com' in src):
                    # Skip profile pictures
                    if 'profile' not in src.lower():
                        if src.startswith('/'):
                            src = f"https://www.popygram.com{src}"
                        stories.append({
                            'type': 'image',
                            'url': src
                        })
            
            for video in soup.find_all('video'):
                src = video.get('src', '')
                if src and 'cdninstagram.com' in src:
                    if src.startswith('/'):
                        src = f"https://www.popygram.com{src}"
                    stories.append({
                        'type': 'video',
                        'url': src
                    })
        
        if not stories:
            if not silent:
                print(f"[!] No stories found for @{username}")
                print("    (Could not parse any media from the response)")
                # Save the HTML for debugging
                with open(f'debug_{username}.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"    (Saved response to debug_{username}.html for inspection)")
            return []
        
        # Remove duplicates
        seen = set()
        unique_stories = []
        for story in stories:
            url = story['url']
            if url not in seen:
                seen.add(url)
                unique_stories.append(story)
        
        if not silent:
            print(f"[✓] Found {len(unique_stories)} stories")
        return unique_stories
        
    except requests.exceptions.RequestException as e:
        if not silent:
            print(f"[✗] Error fetching stories: {e}")
        return []


def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_stories.py <username>")
        print("Example: python fetch_stories.py badgalriri")
        sys.exit(1)
    
    username = sys.argv[1].strip().lstrip('@')
    stories = fetch_stories(username)
    
    if stories:
        print("\n" + "="*60)
        print("STORIES:")
        print("="*60)
        for i, story in enumerate(stories, 1):
            print(f"{i}. [{story['type'].upper()}] {story['url']}")
        
        # Save to JSON
        output_file = f"{username}_stories.json"
        with open(output_file, 'w') as f:
            json.dump(stories, f, indent=2)
        print(f"\n[✓] Saved to {output_file}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
