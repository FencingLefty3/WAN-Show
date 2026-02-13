import sys
import subprocess, os, json, time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

OUT = "output"
os.makedirs(OUT, exist_ok=True)

start_time = time.time()

# -----------------------------
# 1. Automatically get latest WAN Show VOD URL from playlist
# -----------------------------
PLAYLIST_URL = "https://www.youtube.com/watch?v=sRUupu5iudw&list=PL8mG-RkN2uTw7PhlnAr4pZZz2QubIbujH"
print("⏳ Fetching latest WAN Show VOD URL...")
result = subprocess.run([
    sys.executable, "-m", "yt_dlp",
    PLAYLIST_URL,
    "--flat-playlist",
    "--get-id",
], capture_output=True, text=True)

video_ids = result.stdout.strip().split("\n")

if not video_ids:
    raise RuntimeError("No videos found in playlist.")

# Pick first video (latest)
latest_id = video_ids[0]
latest_video_url = f"https://www.youtube.com/watch?v={latest_id}"
print(f"✓ Latest VOD URL detected: {latest_video_url}")

# Extract upload date for unique filenames
metadata = subprocess.run([
    sys.executable, "-m", "yt_dlp",
    latest_video_url,
    "--print", "%(upload_date)s"
], capture_output=True, text=True)

upload_date = metadata.stdout.strip() or datetime.today().strftime("%Y%m%d")

# Base filenames
base_name = f"wan_{upload_date}"
JSON_OUT = os.path.join(OUT, f"{base_name}.json")
IMG_OUT = os.path.join(OUT, f"{base_name}.png")

# -----------------------------
# 2. Download captions only (skip if already exists)
# -----------------------------
existing_vtt = [f for f in os.listdir(OUT) if f.startswith(base_name) and f.endswith(".vtt")]
if existing_vtt:
    CAPTION_FILE = os.path.join(OUT, existing_vtt[0])
    print("✓ Captions already downloaded, skipping...")
else:
    print("⏳ Downloading captions from YouTube...")
    subprocess.run([
        sys.executable, "-m", "yt_dlp",
        latest_video_url,
        "--write-auto-sub",
        "--skip-download",
        "--sub-lang", "en",
        "-o", os.path.join(OUT, base_name + ".%(ext)s")
    ], check=True)
    # Find the file yt-dlp created
    vtt_files = [f for f in os.listdir(OUT) if f.startswith(base_name) and f.endswith(".vtt")]
    if not vtt_files:
        raise RuntimeError("Failed to download captions.")
    CAPTION_FILE = os.path.join(OUT, vtt_files[0])

# -----------------------------
# 3. Convert VTT to plain text with deduplication
# -----------------------------
print("⏳ Processing captions...")
lines_seen = set()
text_lines = []

with open(CAPTION_FILE, encoding="utf8") as f:
    for line in f:
        line = line.strip()
        if not line or "-->" in line or line.startswith("WEBVTT"):
            continue
        if line not in lines_seen:
            lines_seen.add(line)
            text_lines.append(line)

text = " ".join(text_lines)

# -----------------------------
# 4. Mock summarizer (replaces OpenAI API)
# -----------------------------
def mock_summarize(transcript: str):
    """
    Returns a dummy headline and summary for testing purposes.
    """
    headline = "Mock WAN Show Headline"
    summary = "This is a dummy summary generated for testing the WAN Show automation workflow. It contains a few sentences summarizing the content without consuming any API credits."
    return headline, summary

print("⏳ Generating mock summary (no API used)...")
headline, summary = mock_summarize(text)

# Save JSON output
data = {"headline": headline.strip(), "summary": summary.strip()}
json.dump(data, open(JSON_OUT, "w"), indent=2)
print("✓ Mock summary generated")

import random

# -----------------------------
# 5. Generate image with random safe gradient
# -----------------------------
print("⏳ Generating image with random gradient...")

# Function to pick a "safe" RGB value (avoid extreme yellows, bright green, etc.)
def safe_color_component():
    return random.randint(30, 180)  # avoids too bright/neon or too dark

# Pick two colors for top and bottom of gradient
top_color = (safe_color_component(), safe_color_component(), safe_color_component())
bottom_color = (safe_color_component(), safe_color_component(), safe_color_component())

# Create image
img = Image.new("RGB", (1024, 1024), top_color)
draw = ImageDraw.Draw(img)

# Draw vertical gradient
for y in range(img.height):
    ratio = y / img.height
    r = int(top_color[0] * (1-ratio) + bottom_color[0] * ratio)
    g = int(top_color[1] * (1-ratio) + bottom_color[1] * ratio)
    b = int(top_color[2] * (1-ratio) + bottom_color[2] * ratio)
    draw.line([(0, y), (img.width, y)], fill=(r, g, b))

# Headline styling
headline_font_size = 60
subtitle_font_size = 36
try:
    headline_font = ImageFont.truetype("arial.ttf", headline_font_size)
    subtitle_font = ImageFont.truetype("arial.ttf", subtitle_font_size)
except:
    headline_font = ImageFont.load_default()
    subtitle_font = ImageFont.load_default()

# Left-aligned headline
x_margin = 80
y_start = 400
draw.text((x_margin, y_start), headline, font=headline_font, fill=(255, 255, 255))

# Subtitle with formatted date
if len(upload_date) == 8 and upload_date.isdigit():
    formatted_date = f"{upload_date[4:6]}/{upload_date[6:8]}/{upload_date[0:4]}"
else:
    formatted_date = upload_date
subtitle_text = f"Episode Date: {formatted_date}"
y_subtitle = y_start + headline_font_size + 20
draw.text((x_margin, y_subtitle), subtitle_text, font=subtitle_font, fill=(194, 194, 194))

# Save image
img.save(IMG_OUT)
print("✓ Image generated with random safe gradient")




elapsed = time.time() - start_time
print(f"✓ WAN Brief (mock) generated in {elapsed:.1f}s")

import shutil

# Paths for the "latest" files
latest_png = os.path.join(OUT, "wan_latest.png")
latest_json = os.path.join(OUT, "wan_latest.json")

# Remove old "latest" files if they exist
for f in [latest_png, latest_json]:
    if os.path.exists(f):
        os.remove(f)

# Copy the newly generated files as "latest"
shutil.copy2(IMG_OUT, latest_png)
shutil.copy2(JSON_OUT, latest_json)
print("✓ Latest files updated for web interface")