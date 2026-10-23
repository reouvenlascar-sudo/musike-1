#!/usr/bin/env python3
import os
import re
import subprocess
import tempfile
import uuid
from flask import Flask, request, Response, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

PORT = int(os.environ.get("PORT", 5000))

@app.route('/api/ytsearch')
def ytsearch():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    try:
        cmd = [
            'yt-dlp',
            '--flat-playlist',
            '--print', '%(id)s\t%(title)s\t%(channel)s\t%(duration)s\t%(thumbnail)s',
            f'ytsearch10:{q}'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
        items = []
        for line in result.stdout.strip().splitlines():
            parts = line.split('\t')
            if len(parts) < 3 or not parts[0]:
                continue
            dur = 0
            try:
                dur = int(float(parts[3])) if len(parts) > 3 and parts[3] not in ('None', 'NA', '') else 0
            except Exception:
                pass
            thumb = parts[4] if len(parts) > 4 and parts[4] not in ('None', 'NA', '') else f'https://i.ytimg.com/vi/{parts[0]}/hqdefault.jpg'
            items.append({
                'id': parts[0],
                'title': parts[1] or 'Sans titre',
                'channel': parts[2] or 'YouTube',
                'duration': dur,
                'thumbnail': thumb
            })
        return jsonify(items)
    except Exception as e:
        print('ytsearch error:', e)
        return jsonify([])

@app.route('/api/audio')
def audio():
    vid = request.args.get('id', '').strip()
    print(f"=== AUDIO : {vid} ===")
    if not re.match(r'^[a-zA-Z0-9_-]{11}$', vid):
        return Response('ID invalide', 400)

    tmp_dir = tempfile.gettempdir()
    unique = str(uuid.uuid4())[:8]
    out_template = os.path.join(tmp_dir, f"yt_{vid}_{unique}.%(ext)s")

    # Try multiple format selectors
    formats = [
        '140/251/bestaudio[ext=m4a]/bestaudio',
        'bestaudio',
        'best'
    ]

    created = None
    size = 0
    last_error = ""

    for fmt in formats:
        try:
            cmd = [
                'yt-dlp',
                '-f', fmt,
                '-o', out_template,
                '--no-playlist',
                '--force-overwrites',
                '--no-continue',
                '--no-cache-dir',
                '--extractor-args', 'youtube:player_client=android',
                f'https://www.youtube.com/watch?v={vid}'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            for f in os.listdir(tmp_dir):
                if f.startswith(f"yt_{vid}_{unique}"):
                    created = os.path.join(tmp_dir, f)
                    break
            
            if created and os.path.exists(created):
                size = os.path.getsize(created)
                if size > 10000:
                    break
                else:
                    try: os.unlink(created)
                    except: pass
                    created = None
            last_error = result.stderr[-300:] if result.stderr else "no output"
        except Exception as e:
            last_error = str(e)
            continue

    if not created or size < 10000:
        print("Échec final:", last_error)
        return Response('Impossible de récupérer cette vidéo', 404)

    def generate():
        with open(created, 'rb') as f:
            while True:
                chunk = f.read(32768)
                if not chunk:
                    break
                yield chunk
        try:
            os.unlink(created)
        except:
            pass

    headers = {
        'Content-Length': str(size),
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'no-store',
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'audio/mp4'
    }
    return Response(generate(), headers=headers)

@app.route('/')
def index():
    return "Musique Ruben API OK"

if __name__ == '__main__':
    print(f"Serveur sur le port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
