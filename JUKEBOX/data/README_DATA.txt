====================================================================
PETUNJUK PENYIMPANAN MUSIK MINECRAFT DI INTERNAL FLASH (LittleFS)
====================================================================

Folder ini ("data") adalah tempat Anda meletakkan file lagu MP3 Minecraft.
File-file di dalam folder ini akan di-upload langsung ke dalam chip Flash ESP32
menggunakan fitur "Upload Filesystem Image" di PlatformIO.

DAFTAR NAMA FILE MP3 (Simpan langsung di folder data/):
------------------------------------------------------
13.mp3        (Disc Kuning Emas - C418)
cat.mp3       (Disc Hijau Terang - C418)
blocks.mp3    (Disc Oranye/Merah - C418)
chirp.mp3     (Disc Merah Tua - C418)
far.mp3       (Disc Hijau Muda - C418)
mall.mp3      (Disc Ungu - C418)
mellohi.mp3   (Disc Magenta - C418)
stal.mp3      (Disc Hitam - C418)
strad.mp3     (Disc Putih - C418)
ward.mp3      (Disc Hijau Gelap - C418)
11.mp3        (Disc Abu Gelap - C418)
wait.mp3      (Disc Biru Laut - C418)
otherside.mp3 (Disc Biru Teal - Lena Raine)
pigstep.mp3   (Disc Merah Netherite - Lena Raine)
relic.mp3     (Disc Cokelat Tembaga - Aaron Cherof)

TIPS OPTIMASI UKURAN FILE (Agar muat di partisi 2.8 MB):
-------------------------------------------------------
1. Potong durasi lagu menjadi 30 - 45 detik (bagian intro atau chorus terbaik).
2. Konversi ke format MP3 dengan bitrate 64 kbps (atau 48 kbps mono/stereo).
   - Di 64 kbps: 30 detik lagu hanya berukuran ~240 KB!
   - 10 lagu x 240 KB = ~2.4 MB (Sangat aman dan pas di memori flash 2.8 MB).
3. Anda dapat menggunakan software gratis seperti Audacity atau web converter online.

CARA FLASH / UPLOAD FILE INI KE ESP32:
-------------------------------------
Di VS Code PlatformIO:
1. Klik ikon PlatformIO (ikon kepala semut/alien di sidebar kiri).
2. Buka menu: "esp32dev" -> "Platform".
3. Klik "Build Filesystem Image".
4. Klik "Upload Filesystem Image".
Semua lagu akan langsung tersimpan di memori internal ESP32!
