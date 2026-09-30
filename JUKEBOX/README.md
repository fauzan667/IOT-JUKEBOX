# 🎵 ESP32 Minecraft Jukebox (TCS3000 / TCS3200 + LittleFS Internal Flash)

Proyek replika fisik **Minecraft Jukebox** interaktif menggunakan mikrokontroler **ESP32**, sensor warna **TCS3000 / TCS3200**, penyimpanan audio **Internal Flash (LittleFS)** tanpa MicroSD Card, dan transmisi audio nirkabel via **Classic Bluetooth A2DP Source** langsung ke **Bluetooth Speaker**.

---

## 🔍 Status Perangkat Keras Anda Saat Ini

- **Port Terhubung:** **`COM3`** ✅
- **Chip USB Board:** **`USB-SERIAL CH340`** (`VID_1A86 & PID_7523`)
- **Status Driver:** **`OK` (Driver aktif)**
- **Sensor Warna:** **TCS3000 / TCS3200** (8 Pin: `S0`, `S1`, `S2`, `S3`, `OUT`, `VCC`, `GND`, `LED`)
- **Target Speaker:** **`YMX-868BT`** (MAC: **`12:11:8A:1A:2A:08`**, COD: `0x240418`, PIN: `0000`) ✅ **TERVERIFIKASI TERHUBUNG**
- **Penyimpanan:** **LittleFS Flash Internal** (Partisi `2.8 MB`, file demo `/moogcity.mp3` sudah terunggah) ✅

---

## 🔌 Skema Rangkaian Lengkap (Wiring TCS3000 / TCS3200 ke ESP32)

Sensor **TCS3000 / TCS3200** memiliki 8 pin. Hubungkan ke pin GPIO ESP32 seperti pada tabel berikut:

| Pin Sensor TCS3000 | Pin ESP32 | Warna Kabel (Saran) | Fungsi / Keterangan |
| :--- | :--- | :--- | :--- |
| **VCC** | **3.3V** | Merah | Tegangan daya sensor (Gunakan 3.3V agar aman untuk GPIO ESP32) |
| **GND** | **GND** | Hitam | Ground bersama |
| **S0** | **GPIO 14** | Kuning | Pengatur skala frekuensi output |
| **S1** | **GPIO 27** | Oranye | Pengatur skala frekuensi output (Di-set 20%) |
| **S2** | **GPIO 26** | Hijau | Pemilih filter warna fotodioda |
| **S3** | **GPIO 25** | Biru | Pemilih filter warna fotodioda |
| **OUT** | **GPIO 33** | Putih | Output sinyal pulsa gelombang kotak (Frekuensi warna) |
| **LED** | **GPIO 32** *(atau 3.3V)* | Ungu | Menyalakan 4 buah lampu LED putih iluminasi sensor |

> [!TIP]
> **Mengapa VCC dihubungkan ke 3.3V?**
> Chip TCS3000/TCS3200 bekerja normal pada rentang tegangan 2.7V hingga 5.5V. Dengan menghubungkan VCC ke **3.3V**, tegangan output pada pin `OUT` menjadi 3.3V (logika 3.3V), sehingga **sangat aman untuk GPIO ESP32** tanpa memerlukan konverter level tegangan (*level shifter*).

---

## 📁 Struktur File & Proyek

```
JUKEBOX/
├── data/                         # Folder file lagu MP3 yang di-flash ke ESP32
│   ├── README_DATA.txt           # Panduan konversi dan pengisian lagu
│   ├── 13.mp3
│   ├── cat.mp3
│   ├── blocks.mp3
│   └── pigstep.mp3
├── src/
│   └── main.cpp                  # Firmware C++ ESP32 (TCS3000 + LittleFS + BT A2DP)
├── partitions_custom.csv         # Alokasi partisi flash: 2.8 MB untuk LittleFS
├── platformio.ini                # Konfigurasi PlatformIO (Target COM3 otomatis)
├── flowchart.md                  # Diagram alir sistem
├── SKILL.md                      # Panduan teknis arsitektur
└── README.md                     # Dokumentasi utama proyek
```

---

## 💿 Menyiapkan Lagu Minecraft & Flash ke ESP32

1. Potong lagu Minecraft menjadi durasi **30–45 detik** (bagian intro atau chorus terbaik).
2. Simpan dalam format **MP3 64 kbps (44.1 kHz)**.
   - Ukuran 1 lagu $\approx 240 \text{ KB}$.
   - 10-12 lagu akan memakan total $\approx 2.4 \text{ MB}$, sangat aman di dalam partisi flash `2.8 MB`.
3. Masukkan file MP3 tersebut ke folder:
   `c:\Users\MSI GAMING\Documents\Project\JUKEBOX\data\` (contoh: `cat.mp3`, `pigstep.mp3`, dll).
4. Di VS Code PlatformIO:
   - Klik ikon **PlatformIO** di sidebar kiri.
   - Buka **esp32dev** $\rightarrow$ **Platform**.
   - Klik **Build Filesystem Image** lalu **Upload Filesystem Image**.
   - PlatformIO akan mem-flash seluruh lagu langsung ke dalam chip ESP32 melalui port `COM3`!

---

## 🌐 Localhost Web Controller (Play / Stop / Monitor Musik)

Tersedia aplikasi web kontroler lokal berbasis browser untuk memudahkan Anda menguji pemutaran musik, mematikan musik, dan memantau status Bluetooth secara real-time tanpa menyentuh sensor:

1. **Akses Dashboard Sekarang:**
   - Server sudah aktif berjalan di: **[http://localhost:5000](http://localhost:5000)**
   - Buka tautan tersebut di browser Chrome / Edge / Firefox Anda.
2. **Fitur Dashboard:**
   - Tombol **▶ PLAY MUSIC**: Memutar track audio langsung ke speaker Bluetooth Anda (`YMX-868BT`).
   - Tombol **⏹ STOP**: Menghentikan pemutaran musik.
   - **Pilihan Lagu**: Memilih track (misalnya `moogcity.mp3`, `13.mp3`, `cat.mp3`, `pigstep.mp3`, dll).
   - **Terminal Live COM3**: Menampilkan log serial real-time langsung dari chip ESP32.
3. **Menjalankan Ulang di Lain Waktu:**
   Jika komputer baru dinyalakan, Anda cukup menjalankan:
   ```powershell
   & "$env:USERPROFILE\.platformio\penv\Scripts\python.exe" web_controller.py
   ```

---

## 🚀 Cara Flash Firmware Utama

1. Buka file [`src/main.cpp`](file:///c:/Users/MSI%20GAMING/Documents/Project/JUKEBOX/src/main.cpp#L20), sesuaikan nama Bluetooth Speaker Anda:
   ```cpp
   const char* BT_SPEAKER_NAME = "YMX-868BT"; // Nama speaker Anda
   ```
2. Pastikan Bluetooth Speaker Anda dalam mode **Pairing** (lampu berkedip mencari koneksi).
3. Di VS Code PlatformIO, klik tombol **PlatformIO: Upload** (panah centang/kanan di status bar bawah).
4. Buka **Serial Monitor** (115200 baud) untuk melihat ESP32 terhubung ke speaker dan siap membaca kaset.

---

## 🎨 Tabel Pemetaan Warna Kaset Disc Minecraft

| Disc | Warna Dominan Kaset | Nilai Acuan RGB Normalisasi | Lagu |
| :--- | :--- | :--- | :--- |
| **13** | Kuning Emas (Gold) | r: 0.50, g: 0.42, b: 0.08 | Musik ambient misterius C418 |
| **cat** | Hijau Lime (Green) | r: 0.20, g: 0.65, b: 0.15 | Melodi riang C418 |
| **blocks** | Oranye / Merah Bata | r: 0.68, g: 0.22, b: 0.10 | Irama ceria C418 |
| **chirp** | Merah Tua / Crimson | r: 0.65, g: 0.18, b: 0.17 | Musik retro bossa-nova C418 |
| **mall** | Ungu / Violet | r: 0.38, g: 0.22, b: 0.40 | Musik santai jazz-lofi C418 |
| **mellohi** | Pink / Magenta Lembut | r: 0.48, g: 0.22, b: 0.30 | Musik waltz melankolis C418 |
| **stal** | Hitam Pekat | r: 0.33, g: 0.33, b: 0.34 (Clear Rendah)| Musik jazz saksofon C418 |
| **strad** | Putih Gading | r: 0.38, g: 0.38, b: 0.24 (Clear Tinggi)| Musik tropis steel-drum C418 |
| **wait** | Biru Laut / Cyan | r: 0.15, g: 0.35, b: 0.50 | Musik riang C418 |
| **pigstep** | Merah Tua Netherite | r: 0.58, g: 0.18, b: 0.24 | Hip-hop chiptune Lena Raine |
| **otherside**| Biru Muda & Teal | r: 0.12, g: 0.50, b: 0.38 | Nada pop ceria Lena Raine |

---

## 🎯 Cara Kalibrasi Kaset Buatan Sendiri (Sangat Mudah)

Kaset fisik buatan Anda (kertas karton / filamen 3D print) mungkin memiliki sedikit perbedaan pantulan warna. Untuk kalibrasi:
1. Buka [`src/main.cpp`](file:///c:/Users/MSI%20GAMING/Documents/Project/JUKEBOX/src/main.cpp#L23) dan ubah:
   ```cpp
   #define CALIBRATION_MODE 1
   ```
2. Upload ke ESP32 dan buka Serial Monitor.
3. Masukkan kaset kustom Anda ke dalam slot box Jukebox.
4. Serial Monitor akan menampilkan data pembacaan langsung dari sensor TCS3000:
   ```
   [CALIB] Pulsa R: 180 G: 450 B: 620 Clear: 65 us | Norm: r=0.59 g=0.25 b=0.16 | Disc: TERDETEKSI
   ```
5. Catat nilai `r`, `g`, dan `b` tersebut, lalu masukkan ke dalam array `discDatabase[]` di `src/main.cpp`.
6. Kembalikan `#define CALIBRATION_MODE 0` lalu upload ulang. Jukebox kini 100% presisi mengenali setiap kaset buatan Anda!
