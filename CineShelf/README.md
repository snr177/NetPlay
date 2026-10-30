# CineShelf

A modern, Netflix-inspired local media player for Ubuntu Linux.
Built with Python 3, PySide6, and libVLC.

---

## Features

- Scans a local folder and displays videos in a poster grid.
- Plays video and audio using libVLC (MP4, MKV, AVI, MOV, WMV, WebM, TS, FLV, and more).
- Selects multiple audio tracks (English, Hindi, Telugu, Tamil, and any track in the file).
- Selects embedded subtitles.
- Imports external subtitle files (SRT, ASS, SSA, VTT, SUB).
- Downloads subtitles from a URL.
- Keyboard shortcuts for all major controls.
- Full-screen playback.
- Aspect ratio selection (Auto, 16:9, 4:3, 21:9, and more).
- Continue Watching — saves and restores playback position.
- Search bar to filter the library.
- Dark streaming-platform interface.

---

## Requirements

| Component | Minimum version |
|-----------|----------------|
| Ubuntu    | 20.04 LTS      |
| Python    | 3.9            |
| VLC       | 3.0            |
| libvlc-dev| 3.0            |

---

## Installation

### Step 1 — Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv vlc libvlc-dev
```

### Step 2 — Verify VLC

```bash
vlc --version
python3 -c "import vlc; i=vlc.Instance(); print('libVLC OK'); i.release()"
```

### Step 3 — Clone or copy the project

```bash
cd ~
git clone <repository_url> CineShelf
cd CineShelf
```

### Step 4 — Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 5 — Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 6 — Run the application

```bash
python3 main.py
```

---

## Default Media Folder

The application scans `/home/ubuntu/Downloads` by default.

To change the folder:
- Click **Change Folder** in the sidebar inside the application, or
- Edit `config.json` and set `"media_folder"` to your preferred path.

---

## Keyboard Shortcuts

| Key          | Action                         |
|--------------|-------------------------------|
| Space        | Play / Pause                  |
| Right Arrow  | Forward 5 seconds             |
| Left Arrow   | Backward 5 seconds            |
| F            | Toggle full screen            |
| Escape       | Exit full screen              |
| A            | Cycle aspect ratio            |
| B            | Next audio track              |
| Shift+B      | Previous audio track          |
| Up Arrow     | Increase volume               |
| Down Arrow   | Decrease volume               |
| M            | Mute / Unmute                 |
| N            | Next video                    |
| P            | Previous video                |

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## Troubleshooting

### VLC not found

```
ERROR: python-vlc is not installed.
```

Run:
```bash
pip install python-vlc
sudo apt install vlc libvlc-dev
```

### libVLC initialisation failed

```
ERROR: libVLC could not be initialised.
```

Check:
```bash
ldconfig -p | grep libvlc
```

If `libvlc.so` is not listed:
```bash
sudo apt install libvlc-dev
```

### No video output on Wayland

VLC uses X11 by default for video embedding.
On a Wayland session, set the `QT_QPA_PLATFORM` variable:

```bash
QT_QPA_PLATFORM=xcb python3 main.py
```

Or switch to an X11 session from the login screen.

### Black video window but audio plays

This can occur when the VLC video output module is not embedded correctly.
Try:

```bash
sudo apt install vlc-plugin-base vlc-plugin-video-output
```

Then restart the application.

### Subtitle URL fails

- Confirm the URL points directly to a subtitle file (`.srt`, `.ass`, `.ssa`, `.vtt`, `.sub`).
- Confirm the URL uses `http://` or `https://`.
- Check your internet connection.
- The file must be smaller than 5 MB.

### Application crashes on startup

Check whether all Python packages are installed:

```bash
pip install -r requirements.txt
python3 -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
python3 -c "import vlc; print('python-vlc OK')"
```

---

## Project Structure

```
CineShelf/
├── main.py                     Entry point
├── requirements.txt
├── config.json                 Runtime settings
├── README.md
│
├── app/
│   ├── application.py          Qt application setup
│   └── settings.py             Settings loader
│
├── core/
│   ├── vlc_backend.py          All libVLC calls
│   ├── playback_controller.py  Qt-safe playback control
│   ├── track_manager.py        Audio track selection
│   ├── aspect_ratio.py         Aspect ratio cycling
│   └── keyboard_manager.py     Keyboard shortcut handler
│
├── services/
│   ├── library_scanner.py      Background directory scan
│   ├── metadata_service.py     Async VLC metadata reader
│   ├── subtitle_service.py     Subtitle download and validation
│   ├── thumbnail_service.py    VLC-based thumbnail generator
│   └── playback_history.py     Continue Watching storage
│
├── ui/
│   ├── main_window.py          Top-level window and page switcher
│   ├── home_page.py            Library grid and sidebar
│   ├── player_page.py          Video player screen
│   ├── video_card.py           Single video poster card
│   ├── control_bar.py          Playback control overlay
│   ├── audio_menu.py           Audio track menu
│   ├── subtitle_menu.py        Subtitle track and import menu
│   └── dialogs.py              URL input and resume dialogs
│
├── assets/
│   └── styles/
│       └── dark_theme.qss      Qt dark stylesheet
│
└── tests/
    ├── test_library.py
    ├── test_playback.py
    ├── test_tracks.py
    └── test_subtitles.py
```

---

## Security Notes

- Subtitle files downloaded from URLs are validated before loading.
- Only HTTP and HTTPS URLs are accepted.
- Files larger than 5 MB are rejected.
- Downloaded files are not executed.
- Shell commands are not used with untrusted file names.

---

## Known Limitations

- Video embedding uses the X11 window system. Wayland requires the `xcb` backend (see Troubleshooting).
- Thumbnail generation requires the `dummy` VLC output module.
- Not every codec is supported. Codec support depends on the VLC installation and available plugins.
- Subtitle URL loading requires a direct link to a subtitle file. Scraping or login-protected pages are not supported.
