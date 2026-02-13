import sys
import subprocess, os, json, time
from datetime import datetime
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

client = OpenAI()
OUT = "output"
os.makedirs(OUT, exist_ok=True)

start_time = time.time()

# 1. Automatically get latest WAN Show VOD URL from playlist
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

# Extract upload date from metadata for unique filenames
metadata = subprocess.run([
    sys.executable, "-m", "yt_dlp",
    latest_video_url,
    "--print", "%(upload_date)s"
], capture_output=True, text=True)

upload_date = metadata.stdout.strip() or datetime.today().strftime("%Y%m%d")

# Base filename for this episode
base_name = f"wan_{upload_date}"
JSON_OUT = os.path.join(OUT, f"{base_name}.json")
IMG_OUT = os.path.join(OUT, f"{base_name}.png")

# 2. Download captions only (skip if already exists)
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
    # Find the file yt-dlp just created
    vtt_files = [f for f in os.listdir(OUT) if f.startswith(base_name) and f.endswith(".vtt")]
    if not vtt_files:
        raise RuntimeError("Failed to download captions.")
    CAPTION_FILE = os.path.join(OUT, vtt_files[0])

# 3. Convert VTT to plain text with deduplication
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

# 4. Summarize with OpenAI
print("⏳ Summarizing with OpenAI...")
prompt = f"""
Create:
1) One 5-12 word headline.
2) Executive bullet summary under 200 words.
3) Ignore sponsors and ads.
4) Ignore timestamps and speaker labels.

Transcript:
{text}
"""

resp = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role":"user","content":prompt}]
)

result = resp.choices[0].message.content
headline, summary = result.split("\n",1)

data = {"headline": headline.strip(), "summary": summary.strip()}
json.dump(data, open(JSON_OUT, "w"), indent=2)
print("✓ Summary generated")

# 5. Generate image
print("⏳ Generating image...")
img = Image.new("RGB", (1024,1024), (15,15,25))
draw = ImageDraw.Draw(img)
font = ImageFont.load_default()
draw.text((80,450), headline, fill="white", font=font)
img.save(IMG_OUT)

elapsed = time.time() - start_time
print(f"✓ WAN Brief Generated in {elapsed:.1f}s")
