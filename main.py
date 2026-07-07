# =========================================================
# DAILY VIRAL SCORE TRACKER - 4 Channels
# GitHub Actions ke liye optimized
# =========================================================
import subprocess
import os
import whisper
import json
import pandas as pd
from datetime import datetime
import zipfile

# 🔧 CONFIGURATION - YAHAN APNE CHANNELS DAALO
CHANNELS = [
    {"name": "Triggered Insaan", "url": "https://www.youtube.com/@triggeredinsaan"},
    {"name": "Fukra Insaan", "url": "https://www.youtube.com/@FukraInsaan"},
    {"name": "Prerna Malhan", "url": "https://www.youtube.com/@Prernamalhan"},
    {"name": "Ruchika Rathore", "url": "https://www.youtube.com/@RuchikaRathoreOfficial"}
]

VIDEOS_PER_CHANNEL = 2  # Har channel ki latest 2 videos
OUTPUT_DIR = "daily_viral_scores"

# =========================================================
# SCRIPT STARTS
# =========================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/clips", exist_ok=True)

print("🎤 Loading Whisper model...")
model = whisper.load_model("base")

# Scoring function (8 signals)
def score_segment(seg, seg_idx, total):
    text = seg["text"].strip()
    score = 0
    if seg_idx < 5: score += 10  # Hook
    for w in ["love","hate","amazing","crazy","wow","unbelievable","sad","happy","angry","omg"]:
        if w in text.lower(): score += 3
    for p in ["i think","in my opinion","honestly","believe me","trust me"]:
        if p in text.lower(): score += 5
    if 30 < len(text) < 100: score += 4
    if any(c.isdigit() for c in text) or "tip" in text.lower(): score += 6
    if "but" in text.lower() or "however" in text.lower(): score += 4
    if "finally" in text.lower() or "reveal" in text.lower(): score += 5
    if len(text) > 80: score += 3
    if "!" in text or "?" in text: score += 2
    return score

all_results = []
today_date = datetime.now().strftime("%Y-%m-%d")

print(f"\n📊 DAILY VIRAL SCORE REPORT - {today_date}\n")

for channel in CHANNELS:
    channel_name = channel["name"]
    channel_url = channel["url"]
    print(f"\n🔍 Scanning: {channel_name}")
    
    cmd = ["yt-dlp", "--flat-playlist", "--print", "url", f"{channel_url}/videos"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    urls = [u for u in result.stdout.strip().split('\n') if u.startswith('http')][:VIDEOS_PER_CHANNEL]
    
    if not urls:
        print(f"   ⚠️ No videos found")
        continue
    
    print(f"   📹 Found {len(urls)} videos")
    
    for vid_idx, video_url in enumerate(urls, 1):
        print(f"\n   📹 Video {vid_idx}: {video_url}")
        video_filename = f"{OUTPUT_DIR}/temp_{channel_name.replace(' ', '_')}_v{vid_idx}.mp4"
        
        try:
            subprocess.run(["yt-dlp", "-f", "best[height<=720]", video_url, "-o", video_filename], 
                          check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"      ❌ Download failed: {e}")
            continue
        
        print(f"      🎧 Transcribing...")
        try:
            result_trans = model.transcribe(video_filename, word_timestamps=True)
            segments = result_trans["segments"]
        except Exception as e:
            print(f"      ❌ Transcription failed: {e}")
            continue
        
        scored = []
        for i, seg in enumerate(segments):
            scored.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "score": score_segment(seg, i, len(segments))
            })
        
        top_clips = sorted(scored, key=lambda x: x["score"], reverse=True)[:2]
        avg_score = sum([c["score"] for c in scored]) / len(scored) if scored else 0
        max_score = max([c["score"] for c in scored]) if scored else 0
        
        all_results.append({
            "channel": channel_name,
            "video_url": video_url,
            "avg_viral_score": round(avg_score, 2),
            "max_viral_score": max_score,
            "total_segments": len(scored)
        })
        
        for clip_i, clip in enumerate(top_clips, 1):
            start_sec = int(clip["start"])
            duration = max(5, int(clip["end"]) - start_sec)
            clip_name = f"{channel_name.replace(' ', '_')}_v{vid_idx}_clip{clip_i}_{start_sec}s.mp4"
            clip_path = f"{OUTPUT_DIR}/clips/{clip_name}"
            subprocess.run([
                "ffmpeg", "-ss", str(start_sec), "-i", video_filename,
                "-t", str(duration), "-c", "copy", clip_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"      🎬 Clip saved: {clip_name}")
        
        if os.path.exists(video_filename):
            os.remove(video_filename)

# Save JSON report
with open(f"{OUTPUT_DIR}/daily_report_{today_date}.json", 'w') as f:
    json.dump({"date": today_date, "rankings": all_results}, f, indent=2)

# Save CSV report
df = pd.DataFrame([{
    "Channel": v["channel"],
    "Avg_Viral_Score": v["avg_viral_score"],
    "Max_Viral_Score": v["max_viral_score"],
    "Video_URL": v["video_url"]
} for v in all_results])
df = df.sort_values("Avg_Viral_Score", ascending=False)
df.to_csv(f"{OUTPUT_DIR}/daily_report_{today_date}.csv", index=False)

# Create ZIP
zip_file = f"{OUTPUT_DIR}/daily_viral_clips_{today_date}.zip"
with zipfile.ZipFile(zip_file, 'w') as zipf:
    for root, dirs, files in os.walk(f"{OUTPUT_DIR}/clips"):
        for file in files:
            zipf.write(os.path.join(root, file), os.path.basename(file))

print(f"\n✅ Done! Report saved in {OUTPUT_DIR}")
