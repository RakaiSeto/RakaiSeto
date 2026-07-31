#!/usr/bin/env python3
"""Generate a YouTube Music widget SVG for GitHub profile README."""

import base64
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# ─── Config ──────────────────────────────────────────────────────────────────
PLAYLIST_ID = os.getenv("YT_PLAYLIST_ID", "PL7yCXuH9eCWmP_jSvjwPXjy_oTJmjvTeg")
TRACK_COUNT = int(os.getenv("YT_TRACK_COUNT", "5"))
OUTPUT_DIR = os.getenv("YT_OUTPUT_DIR", ".")
OUTPUT_FILE = os.getenv("YT_OUTPUT_FILE", "metrics.music.svg")

# TokyoNight theme
BG_COLOR = "#1a1b27"
CARD_BG = "#24283b"
TEXT_PRIMARY = "#c0caf5"
TEXT_SECONDARY = "#565f89"
ACCENT = "#7aa2f7"
BORDER = "#3b4261"

# ─── YouTube Music API ──────────────────────────────────────────────────────
API_URL = "https://music.youtube.com/youtubei/v1/browse?alt=json&key=AIzaSyC9XL3ZjWddXya6X74dJoCTL-WEYFDNX30"
CLIENT_CONTEXT = {
    "context": {
        "client": {
            "clientName": "WEB_REMIX",
            "clientVersion": "1.20211129.00.01",
            "gl": "US",
            "hl": "en",
        },
    },
    "browseId": f"VL{PLAYLIST_ID}",
}


def get_sapisid_hash(cookie: str) -> str:
    """Generate SAPISIDHASH authorization header."""
    sapisid = None
    for part in cookie.split("; "):
        if part.startswith("SAPISID="):
            sapisid = part.split("=", 1)[1]
            break
    if not sapisid:
        raise ValueError("SAPISID not found in cookie")
    timestamp = int(time.time())
    hash_input = f"{timestamp} {sapisid} https://music.youtube.com"
    sha1 = hashlib.sha1(hash_input.encode()).hexdigest()
    return f"SAPISIDHASH {timestamp}_{sha1}"


def fetch_playlist(cookie: str) -> list[dict]:
    """Fetch tracks from YouTube Music playlist."""
    auth = get_sapisid_hash(cookie)
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json",
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Origin": "https://music.youtube.com",
        "Origin": "https://music.youtube.com",
        "Referer": "https://music.youtube.com/",
    }
    req = Request(API_URL, data=json.dumps(CLIENT_CONTEXT).encode(), headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"API error {e.code}: {body[:500]}", file=sys.stderr)
        raise

    # Parse tracks from response
    tracks = []
    shelf = (
        data.get("contents", {})
        .get("twoColumnBrowseResultsRenderer", {})
        .get("secondaryContents", {})
        .get("sectionListRenderer", {})
        .get("contents", [{}])[0]
        .get("musicPlaylistShelfRenderer", {})
        .get("contents", [])
    )

    for item in shelf:
        renderer = item.get("musicResponsiveListItemRenderer", {})
        if not renderer:
            continue

        # Extract title from flexColumns
        flex = renderer.get("flexColumns", [])
        title = "Unknown"
        artist = "Unknown"
        if len(flex) > 0:
            runs = (
                flex[0]
                .get("musicResponsiveListItemFlexColumnRenderer", {})
                .get("text", {})
                .get("runs", [])
            )
            if runs:
                title = runs[0].get("text", "Unknown")
        if len(flex) > 1:
            runs = (
                flex[1]
                .get("musicResponsiveListItemFlexColumnRenderer", {})
                .get("text", {})
                .get("runs", [])
            )
            if runs:
                artist = runs[0].get("text", "Unknown")

        # Extract thumbnail (nested in musicThumbnailRenderer)
        thumbnails = (
            renderer.get("thumbnail", {})
            .get("musicThumbnailRenderer", {})
            .get("thumbnail", {})
            .get("thumbnails", [])
        )
        thumbnail = thumbnails[-1]["url"] if thumbnails else ""

        # Extract video ID from overlay
        video_id = (
            renderer.get("overlay", {})
            .get("musicItemThumbnailOverlayRenderer", {})
            .get("content", {})
            .get("musicPlayButtonRenderer", {})
            .get("playNavigationEndpoint", {})
            .get("watchEndpoint", {})
            .get("videoId", "")
        )

        tracks.append({
            "title": title,
            "artist": artist,
            "video_id": video_id,
            "thumbnail": thumbnail,
        })

    return tracks


def fetch_thumbnail_base64(url: str) -> str:
    """Fetch image and return base64 data URI."""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=10) as resp:
        data = resp.read()
    b64 = base64.b64encode(data).decode()
    return f"data:image/jpeg;base64,{b64}"


def render_svg(tracks: list[dict]) -> str:
    """Render tracks as SVG card."""
    track_count = len(tracks)
    thumb_size = 64
    padding = 16
    row_height = thumb_size + 12
    header_height = 40
    footer_height = 24
    width = 400
    height = header_height + (track_count * row_height) + footer_height + padding

    # Build track rows
    track_rows = ""
    for i, track in enumerate(tracks):
        y = header_height + (i * row_height) + padding
        thumb_data = fetch_thumbnail_base64(track["thumbnail"])
        # Escape XML
        title = (
            track["title"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        artist = (
            track["artist"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        track_rows += f"""
    <g transform="translate({padding}, {y})">
      <rect width="{thumb_size}" height="{thumb_size}" rx="8" fill="{BORDER}"/>
      <image href="{thumb_data}" width="{thumb_size}" height="{thumb_size}" rx="8" clip-path="inset(0 round 8px)"/>
      <text x="{thumb_size + 12}" y="24" fill="{TEXT_PRIMARY}" font-family="sans-serif" font-size="14" font-weight="600">{title[:35]}{'…' if len(title) > 35 else ''}</text>
      <text x="{thumb_size + 12}" y="44" fill="{TEXT_SECONDARY}" font-family="sans-serif" font-size="12">{artist[:40]}{'…' if len(artist) > 40 else ''}</text>
    </g>"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <style>
      text {{ user-select: none; }}
    </style>
  </defs>
  <rect width="{width}" height="{height}" rx="12" fill="{BG_COLOR}"/>
  <rect x="0" y="0" width="{width}" height="2" rx="1" fill="{ACCENT}"/>
  <text x="{padding}" y="28" fill="{ACCENT}" font-family="sans-serif" font-size="16" font-weight="700">♫ What I'm Listening To</text>
  {track_rows}
  <text x="{padding}" y="{height - 8}" fill="{TEXT_SECONDARY}" font-family="sans-serif" font-size="10">Updated: {time.strftime('%b %d, %Y')}</text>
</svg>"""
    return svg


def main():
    cookie = os.getenv("MUSIC_TOKEN")
    if not cookie:
        print("Error: MUSIC_TOKEN environment variable not set", file=sys.stderr)
        print("Set it with: export MUSIC_TOKEN='your_cookie_here'", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching playlist {PLAYLIST_ID}...")
    tracks = fetch_playlist(cookie)
    if not tracks:
        print("Error: No tracks found in playlist", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(tracks)} tracks, picking {TRACK_COUNT} random...")
    selected = random.sample(tracks, min(TRACK_COUNT, len(tracks)))

    for i, t in enumerate(selected, 1):
        print(f"  {i}. {t['title']} — {t['artist']}")

    print("Generating SVG...")
    svg = render_svg(selected)

    output_path = Path(OUTPUT_DIR) / OUTPUT_FILE
    output_path.write_text(svg, encoding="utf-8")
    print(f"Written to {output_path} ({output_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
