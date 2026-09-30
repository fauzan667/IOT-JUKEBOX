#!/usr/bin/env python3
"""
=============================================================================
MINECRAFT JUKEBOX ESP32 - LOCALHOST CONTROLLER & DASHBOARD
Aplikasi web lokal untuk mengontrol pemutaran musik (Play/Stop), mengatur
volume suara (0 - 100%), deteksi lagu otomatis di folder data/, dan 1-Click Flash FS.
=============================================================================
"""

import os
import sys
import time
import json
import threading
import subprocess
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import serial

PORT = "COM3"
BAUD = 115200
HTTP_PORT = 5000

log_buffer = deque(maxlen=250)
log_lock = threading.Lock()
ser = None
ser_lock = threading.Lock()
is_bt_connected = True
is_music_playing = False
current_track = "akudahlupa.mp3"
current_volume = 80
is_flashing_fs = False

def get_available_songs():
    songs = []
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if os.path.exists(data_dir):
        for f in sorted(os.listdir(data_dir)):
            if f.lower().endswith(".mp3"):
                full_path = os.path.join(data_dir, f)
                size_kb = os.path.getsize(full_path) // 1024
                name_only = f[:-4]
                songs.append({"filename": f, "name": name_only, "size_kb": size_kb})
    return songs

def add_log(msg):
    global is_bt_connected, is_music_playing, current_track, current_volume
    with log_lock:
        timestamp = time.strftime("%H:%M:%S")
        log_buffer.append(f"[{timestamp}] {msg}")
        if "BERHASIL TERHUBUNG KE SPEAKER" in msg or "a2dp connected" in msg or '"bt":1' in msg:
            is_bt_connected = True
        elif "Koneksi terputus" in msg or '"bt":0' in msg:
            is_bt_connected = False

        if "Memutar track audio" in msg or '"state":2' in msg:
            is_music_playing = True
            if ":" in msg and ".mp3" in msg:
                current_track = msg.split(":")[-1].strip().replace("/", "")
        elif "Musik dihentikan" in msg or '"state":1' in msg or '"state":0' in msg:
            is_music_playing = False

        if "[VOLUME]" in msg and "%" in msg:
            try:
                parts = msg.split("%")[0].split(":")[-1].strip()
                current_volume = int(parts)
            except Exception:
                pass

def serial_worker():
    global ser, is_flashing_fs
    while True:
        if is_flashing_fs:
            time.sleep(0.5)
            continue

        try:
            with ser_lock:
                if ser is None or not ser.is_open:
                    try:
                        add_log(f"Membuka port serial {PORT} ({BAUD} baud)...")
                        ser = serial.Serial(PORT, BAUD, timeout=0.2)
                        ser.setDTR(False)
                        ser.setRTS(False)
                        add_log(f"Port {PORT} berhasil dibuka!")
                    except Exception as e:
                        add_log(f"Gagal membuka {PORT}: {e}. Mencoba lagi...")
                        time.sleep(2)
                        continue

            with ser_lock:
                if ser and ser.is_open and ser.in_waiting > 0:
                    raw = ser.readline()
                    if raw:
                        line = raw.decode("utf-8", errors="ignore").strip()
                        if line:
                            add_log(line)
            time.sleep(0.04)
        except Exception as e:
            add_log(f"Serial notice: {e}")
            time.sleep(0.5)

def send_serial_cmd(cmd_str):
    global ser, is_flashing_fs
    if is_flashing_fs:
        add_log("Sedang proses flash LittleFS! Harap tunggu...")
        return False

    with ser_lock:
        if ser and ser.is_open:
            try:
                ser.write((cmd_str.strip() + "\n").encode("utf-8"))
                ser.flush()
                add_log(f">> [KIRIM PERINTAH] {cmd_str.strip()}")
                return True
            except Exception as e:
                add_log(f"Error kirim perintah: {e}")
                return False
        else:
            add_log("Error: Port serial COM3 belum siap!")
            return False

def run_uploadfs_task():
    global is_flashing_fs, ser
    is_flashing_fs = True
    add_log("[FLASH] Menutup port serial COM3 untuk flashing LittleFS...")
    with ser_lock:
        if ser and ser.is_open:
            ser.close()
            ser = None
    time.sleep(1)

    add_log("[FLASH] Menjalankan PlatformIO uploadfs (mem-flash lagu baru ke flash internal)...")
    pio_path = os.path.expandvars(r"$USERPROFILE\.platformio\penv\Scripts\platformio.exe")
    try:
        proc = subprocess.Popen(
            [pio_path, "run", "-t", "uploadfs"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in proc.stdout:
            l = line.strip()
            if l:
                add_log(f"[UPLOADFS] {l}")
        proc.wait()
        if proc.returncode == 0:
            add_log("[FLASH SUKSES] Seluruh file musik baru berhasil di-flash ke LittleFS ESP32!")
        else:
            add_log(f"[FLASH GAGAL] Kode keluar: {proc.returncode}")
    except Exception as e:
        add_log(f"[FLASH ERROR] {e}")

    time.sleep(1)
    is_flashing_fs = False

HTML_PAGE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Minecraft Jukebox Controller</title>
  <style>
    :root {
      --bg-dark: #101214;
      --card-bg: #181c22;
      --card-border: #28303a;
      --mc-green: #2ecc71;
      --mc-red: #e74c3c;
      --mc-gold: #f1c40f;
      --mc-wood: #8b5a2b;
      --mc-blue: #3498db;
      --text-main: #f0f6fc;
      --text-dim: #8b949e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }
    body {
      background: var(--bg-dark);
      color: var(--text-main);
      padding: 24px 16px;
      display: flex;
      justify-content: center;
    }
    .container {
      width: 100%;
      max-width: 880px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .header {
      background: linear-gradient(135deg, #3d2314 0%, #1a110a 100%);
      border: 2px solid var(--mc-wood);
      border-radius: 12px;
      padding: 22px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 8px 24px rgba(0,0,0,0.6);
    }
    .title-box h1 { font-size: 24px; color: #f5d76e; text-shadow: 2px 2px 0 #000; display: flex; align-items: center; gap: 10px; }
    .title-box p { color: #d5b895; font-size: 13px; margin-top: 4px; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 700;
    }
    .badge.connected { background: rgba(46, 204, 113, 0.15); border: 1px solid var(--mc-green); color: var(--mc-green); }
    .badge.disconnected { background: rgba(231, 76, 60, 0.15); border: 1px solid var(--mc-red); color: var(--mc-red); }
    .badge.playing { background: rgba(241, 196, 15, 0.15); border: 1px solid var(--mc-gold); color: var(--mc-gold); animation: pulse 1.5s infinite; }
    .badge.flashing { background: rgba(52, 152, 219, 0.15); border: 1px solid var(--mc-blue); color: var(--mc-blue); animation: pulse 1s infinite; }
    @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }
    .badge-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }

    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 680px) { .grid { grid-template-columns: 1fr; } }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.3);
    }
    .card h2 { font-size: 16px; margin-bottom: 16px; color: #58a6ff; display: flex; align-items: center; gap: 8px; }

    .device-info { display: flex; flex-direction: column; gap: 10px; font-size: 13px; }
    .device-row { display: flex; justify-content: space-between; border-bottom: 1px solid #232a34; padding-bottom: 6px; }
    .device-row span:first-child { color: var(--text-dim); }
    .device-row span:last-child { font-weight: 600; }

    .control-box { display: flex; flex-direction: column; gap: 16px; }
    select {
      width: 100%;
      background: #0d1117;
      color: #c9d1d9;
      border: 1px solid #30363d;
      padding: 12px 14px;
      border-radius: 8px;
      font-size: 14px;
      outline: none;
    }
    .btn-group { display: flex; gap: 12px; }
    button {
      flex: 1;
      padding: 15px;
      border: none;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 800;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      transition: all 0.15s;
    }
    .btn-play {
      background: linear-gradient(180deg, #2ecc71, #27ae60);
      color: #fff;
      box-shadow: 0 5px 0 #1e824c;
    }
    .btn-play:hover { background: #2ecc71; transform: translateY(-1px); }
    .btn-play:active { transform: translateY(3px); box-shadow: 0 2px 0 #1e824c; }

    .btn-stop {
      background: linear-gradient(180deg, #e74c3c, #c0392b);
      color: #fff;
      box-shadow: 0 5px 0 #962d22;
    }
    .btn-stop:hover { background: #e74c3c; transform: translateY(-1px); }
    .btn-stop:active { transform: translateY(3px); box-shadow: 0 2px 0 #962d22; }

    .btn-flash {
      width: 100%;
      padding: 12px;
      background: linear-gradient(180deg, #3498db, #2980b9);
      color: #fff;
      font-size: 13px;
      font-weight: 700;
      border-radius: 8px;
      border: none;
      box-shadow: 0 4px 0 #1c638f;
      margin-top: 4px;
    }
    .btn-flash:hover { background: #3498db; }
    .btn-flash:active { transform: translateY(2px); box-shadow: 0 2px 0 #1c638f; }

    /* Volume Section */
    .volume-box {
      background: #111419;
      border: 1px solid #28303a;
      border-radius: 10px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .volume-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 13px;
    }
    .volume-header span:first-child { color: var(--text-dim); display: flex; align-items: center; gap: 6px; }
    .volume-val { font-size: 15px; font-weight: 800; color: #58a6ff; }

    .slider-container { display: flex; align-items: center; gap: 12px; }
    input[type=range] {
      flex: 1;
      -webkit-appearance: none;
      height: 8px;
      border-radius: 4px;
      background: #232a34;
      outline: none;
    }
    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none;
      appearance: none;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: #58a6ff;
      cursor: pointer;
      box-shadow: 0 0 10px rgba(88, 166, 255, 0.6);
      transition: background 0.15s;
    }
    input[type=range]::-webkit-slider-thumb:hover { background: #79c0ff; transform: scale(1.1); }

    .vol-presets { display: flex; gap: 6px; }
    .vol-btn {
      flex: 1;
      padding: 6px 4px;
      font-size: 12px;
      font-weight: 600;
      border-radius: 6px;
      background: #1f242c;
      color: #c9d1d9;
      border: 1px solid #30363d;
      box-shadow: none;
    }
    .vol-btn:hover { background: #30363d; color: #fff; transform: none; }
    .vol-btn:active { transform: translateY(1px); }

    .console-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 20px;
    }
    .console-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .console-header h2 { font-size: 15px; color: #7ee787; }
    .console-body {
      background: #090d10;
      border: 1px solid #21262d;
      border-radius: 8px;
      padding: 12px 14px;
      height: 230px;
      overflow-y: auto;
      font-family: "Courier New", Courier, monospace;
      font-size: 12px;
      line-height: 1.5;
      color: #7ee787;
    }
    .console-body p { margin-bottom: 2px; word-break: break-all; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title-box">
        <h1>🎵 Minecraft Jukebox Controller</h1>
        <p>Kontroler Streaming Audio Bluetooth ESP32 (COM3) ke Speaker YMX-868BT</p>
      </div>
      <div id="statusBadge" class="badge connected">
        <span class="badge-dot"></span>
        <span id="statusText">Speaker Terkoneksi ✅</span>
      </div>
    </div>

    <div class="grid">
      <!-- Info Perangkat -->
      <div class="card">
        <h2>ℹ️ Informasi Hardware</h2>
        <div class="device-info">
          <div class="device-row"><span>Port Serial</span><span style="color: #7ee787;">COM3 (115200)</span></div>
          <div class="device-row"><span>Target Speaker</span><span>YMX-868BT</span></div>
          <div class="device-row"><span>MAC Address</span><span style="color: #58a6ff;">12:11:8A:1A:2A:08</span></div>
          <div class="device-row"><span>Penyimpanan</span><span>LittleFS Flash Internal (2.8 MB)</span></div>
          <div class="device-row"><span>Sensor Optik</span><span>TCS3000 (S0-S3, OUT, LED)</span></div>
          <div class="device-row"><span>Lagu Aktif</span><span id="currentTrackLabel" style="color: #f5d76e;">akudahlupa.mp3</span></div>
          <div class="device-row"><span>Volume Saat Ini</span><span id="volRowLabel" style="color: #58a6ff;">80%</span></div>
        </div>

        <div style="margin-top: 14px;">
          <button class="btn-flash" onclick="triggerFlashFS()">📥 Sync / Flash Lagu Baru ke ESP32</button>
        </div>
      </div>

      <!-- Kontrol Pemutaran & Volume -->
      <div class="card">
        <h2>🎛️ Kontrol Pemutaran & Volume</h2>
        <div class="control-box">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <label style="font-size: 13px; color: var(--text-dim);">Pilih Lagu di Folder data/:</label>
              <a href="javascript:void(0)" onclick="loadSongs()" style="font-size: 12px; color: #58a6ff; text-decoration: none;">🔄 Refresh Lagu</a>
            </div>
            <select id="trackSelect">
              <option value="akudahlupa" selected>akudahlupa.mp3 (Lagu Baru)</option>
              <option value="moogcity">moogcity.mp3 (Official Soundtrack)</option>
            </select>
          </div>

          <div class="btn-group">
            <button class="btn-play" onclick="playMusic()">▶ PLAY</button>
            <button class="btn-stop" onclick="stopMusic()">⏹ STOP</button>
          </div>

          <!-- Slider Volume -->
          <div class="volume-box">
            <div class="volume-header">
              <span>🔊 Volume Speaker</span>
              <span id="volumeVal" class="volume-val">80%</span>
            </div>
            <div class="slider-container">
              <span style="font-size: 13px; color: var(--text-dim);">0%</span>
              <input type="range" id="volumeSlider" min="0" max="100" value="80" oninput="onVolumeInput(this.value)" onchange="sendVolume(this.value)">
              <span style="font-size: 13px; color: var(--text-dim);">100%</span>
            </div>
            <div class="vol-presets">
              <button class="vol-btn" onclick="setVolumePreset(0)">🔇 Mute</button>
              <button class="vol-btn" onclick="setVolumePreset(25)">25%</button>
              <button class="vol-btn" onclick="setVolumePreset(50)">50%</button>
              <button class="vol-btn" onclick="setVolumePreset(75)">75%</button>
              <button class="vol-btn" onclick="setVolumePreset(100)">100%</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Live Console -->
    <div class="console-card">
      <div class="console-header">
        <h2>💻 Terminal Live ESP32 (COM3)</h2>
        <span style="font-size: 12px; color: var(--text-dim);">Auto-update setiap 500ms</span>
      </div>
      <div class="console-body" id="consoleBody">
        <p>[Sistem] Menghubungkan ke controller...</p>
      </div>
    </div>
  </div>

  <script>
    let isUserSliding = false;

    async function loadSongs() {
      try {
        const res = await fetch('/api/songs?t=' + Date.now());
        const songs = await res.json();
        const sel = document.getElementById('trackSelect');
        const prevVal = sel.value;
        sel.innerHTML = '';
        songs.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.name;
          opt.textContent = `${s.filename} (${s.size_kb} KB)`;
          if (opt.value === prevVal || (!prevVal && s.name === 'akudahlupa')) {
            opt.selected = true;
          }
          sel.appendChild(opt);
        });
      } catch (e) {
        console.error('Error load songs:', e);
      }
    }

    async function playMusic() {
      const track = document.getElementById('trackSelect').value;
      try {
        const res = await fetch(`/api/play?track=${track}`);
        const data = await res.json();
        console.log('Play response:', data);
      } catch (e) {
        alert('Gagal mengirim perintah: ' + e);
      }
    }

    async function stopMusic() {
      try {
        const res = await fetch('/api/stop');
        const data = await res.json();
        console.log('Stop response:', data);
      } catch (e) {
        alert('Gagal mengirim perintah: ' + e);
      }
    }

    async function triggerFlashFS() {
      if (!confirm('Flash ulang seluruh lagu di folder data/ ke dalam memori chip ESP32? (Memerlukan ~30 detik)')) return;
      try {
        const res = await fetch('/api/uploadfs');
        const data = await res.json();
        alert('Proses flash LittleFS dimulai di background! Pantau terminal live di bawah.');
      } catch (e) {
        alert('Gagal trigger uploadfs: ' + e);
      }
    }

    function onVolumeInput(val) {
      isUserSliding = true;
      document.getElementById('volumeVal').textContent = val + '%';
      document.getElementById('volRowLabel').textContent = val + '%';
    }

    async function sendVolume(val) {
      isUserSliding = false;
      document.getElementById('volumeVal').textContent = val + '%';
      document.getElementById('volRowLabel').textContent = val + '%';
      try {
        const res = await fetch(`/api/volume?val=${val}`);
        const data = await res.json();
        console.log('Volume response:', data);
      } catch (e) {
        console.error('Error volume:', e);
      }
    }

    function setVolumePreset(val) {
      document.getElementById('volumeSlider').value = val;
      sendVolume(val);
    }

    async function updateLogs() {
      try {
        const res = await fetch('/api/logs?t=' + Date.now());
        const data = await res.json();
        const box = document.getElementById('consoleBody');
        
        let isScrolledToBottom = box.scrollHeight - box.clientHeight <= box.scrollTop + 60;
        
        box.innerHTML = data.logs.map(line => `<p>${escapeHtml(line)}</p>`).join('');
        
        if (isScrolledToBottom) {
          box.scrollTop = box.scrollHeight;
        }

        const badge = document.getElementById('statusBadge');
        const text = document.getElementById('statusText');
        const trackLabel = document.getElementById('currentTrackLabel');
        
        if (data.track) {
          trackLabel.textContent = data.track;
        }

        if (!isUserSliding && data.volume !== undefined) {
          document.getElementById('volumeSlider').value = data.volume;
          document.getElementById('volumeVal').textContent = data.volume + '%';
          document.getElementById('volRowLabel').textContent = data.volume + '%';
        }

        if (data.is_flashing) {
          badge.className = 'badge flashing';
          text.textContent = '⏳ Flashing LittleFS...';
        } else if (data.is_playing) {
          badge.className = 'badge playing';
          text.textContent = '🔊 Sedang Memutar Musik!';
        } else if (data.bt_connected) {
          badge.className = 'badge connected';
          text.textContent = 'Speaker Terkoneksi ✅';
        } else {
          badge.className = 'badge disconnected';
          text.textContent = 'Menghubungkan Speaker...';
        }
      } catch (e) {
        console.error('Error logs:', e);
      }
    }

    function escapeHtml(text) {
      return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    loadSongs();
    setInterval(updateLogs, 500);
    updateLogs();
  </script>
</body>
</html>
"""

class JukeboxRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global current_volume
        url = urlparse(self.path)
        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif url.path == "/api/songs":
            songs = get_available_songs()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(songs).encode("utf-8"))
        elif url.path == "/api/play":
            params = parse_qs(url.query)
            track = params.get("track", ["akudahlupa"])[0]
            success = send_serial_cmd(f"PLAY:{track}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok" if success else "error", "track": track}).encode("utf-8"))
        elif url.path == "/api/stop":
            success = send_serial_cmd("STOP")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok" if success else "error"}).encode("utf-8"))
        elif url.path == "/api/volume":
            params = parse_qs(url.query)
            val = params.get("val", ["80"])[0]
            try:
                vol_int = max(0, min(100, int(val)))
                current_volume = vol_int
                success = send_serial_cmd(f"VOL:{vol_int}")
            except Exception:
                success = False
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok" if success else "error", "volume": current_volume}).encode("utf-8"))
        elif url.path == "/api/uploadfs":
            t = threading.Thread(target=run_uploadfs_task, daemon=True)
            t.start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode("utf-8"))
        elif url.path == "/api/logs":
            with log_lock:
                logs_list = list(log_buffer)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "logs": logs_list,
                "bt_connected": is_bt_connected,
                "is_playing": is_music_playing,
                "track": current_track,
                "volume": current_volume,
                "is_flashing": is_flashing_fs
            }).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def main():
    print("=" * 60, flush=True)
    print("  MINECRAFT JUKEBOX LOCALHOST CONTROLLER", flush=True)
    print(f"  Target: ESP32 di {PORT} | Web Server: http://localhost:{HTTP_PORT}", flush=True)
    print("=" * 60, flush=True)

    t = threading.Thread(target=serial_worker, daemon=True)
    t.start()

    server = HTTPServer(("0.0.0.0", HTTP_PORT), JukeboxRequestHandler)
    print(f"\n[SERVER SIAP] Buka browser Anda di: http://localhost:{HTTP_PORT}\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.", flush=True)
        if ser and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
