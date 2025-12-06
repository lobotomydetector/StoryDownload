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
        
        # Save HTML for debugging/inspection ONLY in CLI mode
        if not silent:
            try:
                with open(f'debug_{username}.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
            except Exception:
                pass # Ignore file write errors (e.g. read-only filesystem)
        
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
        
        # Helper to parse time string to minutes
        def parse_time_ago(time_str):
            try:
                time_str = time_str.lower().strip()
                if 'minute' in time_str:
                    return int(re.search(r'(\d+)', time_str).group(1))
                elif 'hour' in time_str:
                    return int(re.search(r'(\d+)', time_str).group(1)) * 60
                elif 'day' in time_str:
                    return int(re.search(r'(\d+)', time_str).group(1)) * 1440
                return 999999 # Fallback for unknown format
            except:
                return 999999

        if row_div:
            # The structure is: col-div -> card-div -> (media + card-body)
            # We need to iterate over the columns/cards to keep media and time together
            for col in row_div.find_all('div', class_=re.compile(r'col-')):
                story_data = {}
                
                # Find media
                img = col.find('img')
                video = col.find('video')
                
                if video:
                    src = video.get('src', '')
                    story_data['type'] = 'video'
                    story_data['url'] = src
                elif img:
                    src = img.get('src', '')
                    story_data['type'] = 'image'
                    story_data['url'] = src
                
                if 'url' in story_data and story_data['url']:
                    # Clean URL
                    if story_data['url'].startswith('/'):
                        story_data['url'] = f"https://www.popygram.com{story_data['url']}"
                    
                    # Find timestamp
                    # Look for the clock icon, then the span next to it
                    clock = col.find('i', class_='fa-clock')
                    if clock:
                        time_span = clock.find_next('span')
                        if time_span:
                            story_data['time_str'] = time_span.text.strip()
                            story_data['age_minutes'] = parse_time_ago(story_data['time_str'])
                    
                    if 'age_minutes' not in story_data:
                         story_data['age_minutes'] = 999999 # Put at end if no time found
                         
                    stories.append(story_data)
        
        # If no stories found in container, scan entire page (fallback - no sorting possible usually)
        if not stories:
            # ... (keep existing fallback logic but it's less likely to be used for valid stories)
            pass 
            
        # Remove duplicates (keeping the one with the lowest age if duplicates exist)
        seen = set()
        unique_stories = []
        # Sort by age first so we keep the "freshest" version if there are dupes (unlikely but good practice)
        stories.sort(key=lambda x: x.get('age_minutes', 999999))
        
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
