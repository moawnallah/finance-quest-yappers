"""Make the demo's voice clips from narration.json: voice/<id>.mp3 and voice/durations.json.

    pip install edge-tts   (Microsoft neural voices; only the narration text is sent)
    python3 make_voice.py [--voice en-US-AvaMultilingualNeural]
"""
import json, subprocess, sys
voice = sys.argv[sys.argv.index("--voice") + 1] if "--voice" in sys.argv else "en-US-AvaMultilingualNeural"
durs = {}
for line in json.load(open("narration.json")):
    out = f"voice/{line['id']}.mp3"
    subprocess.run(["edge-tts", "--voice", voice, "--rate=-4%", "--text", line["text"], "--write-media", out], check=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                             capture_output=True, text=True).stdout)
    durs[line["id"]] = round(d * 1000)
json.dump(durs, open("voice/durations.json", "w"), indent=1)
print(durs)
