# NetPlay

NetPlay is a small set of tools for watching videos on your computer. You can use a web browser, use a desktop app, or download files from a magnet link.

## What is included?

- **Browser player** (`player_server.py` and `player.html`): Watch videos in your web browser.
- **Desktop player** (`play.py`): Watch videos in a separate app window.
- **Magnet downloader** (`magnet.py`): Download files using a magnet link.

You can use the browser and desktop players without using the downloader.

## What you need

- Python 3 installed on your computer.
- A terminal or command prompt.
- The video files you want to watch.

Open a terminal in the folder that contains the NetPlay files before running the commands below.

## Install the player packages

Create a separate Python environment for NetPlay. You only need to create it once:

```sh
python3 -m venv .venv
```

Turn it on whenever you open a new terminal to use NetPlay:

**macOS or Linux**

```sh
source .venv/bin/activate
```

**Windows**

```powershell
.venv\Scripts\Activate.ps1
```

Install the packages used by the players:

```sh
python -m pip install --upgrade pip
python -m pip install av pygame pillow
```

If `python3` is not recognized on your computer, try `python` instead.

## Watch videos in a web browser

The browser player looks for videos in `/home/ubuntu/Downloads`, including its subfolders. Put your videos there. If that folder does not exist on your computer, open `player_server.py` and change `VIDEO_DIR` to the folder where your videos are stored.

1. Turn on the Python environment using the command above.
2. Start the server:

   ```sh
   python player_server.py
   ```

3. Keep the terminal open while you watch.
4. Open [http://localhost:8765](http://localhost:8765) in your web browser.
5. Choose a video from the library.

To stop the server, go back to its terminal and press **Ctrl+C**.

The player can show video details, load subtitle files, and try to prepare a browser-friendly copy if a video will not play. Preparing a copy can take a long time and use extra disk space. Your original video is not changed. Copies are kept in `~/.cache/cinema-player`.

The player server can be reached by other devices on your network. Only run it on a network you trust, and do not make it public on the internet.

## Use the desktop player

Turn on the Python environment, then run:

```sh
python play.py
```

The player first looks for a folder named `downloads` next to `play.py`. Use **Choose folder** in the app to select a different folder.

The player has controls for play, pause, seeking, volume, subtitles, and screen size. Keyboard shortcuts include:

| Key | Action |
| --- | --- |
| Space | Play or pause |
| Left or right arrow | Move backward or forward |
| F | Turn full screen on or off |
| A | Change the video shape |
| B | Change audio track, when available |
| Escape | Exit full screen |

## Download with a magnet link (optional)

The downloader needs the `libtorrent` Python package. Installing it depends on your operating system. On Ubuntu, you can install it with:

```sh
sudo apt update
sudo apt install python3-libtorrent
```

Run the downloader with Python:

```sh
python magnet.py
```

Paste a complete magnet link that starts with `magnet:?`, then press Enter. By default, files are saved in a `Downloads` folder under the current folder. The downloader stops when the download is complete; it does not keep sharing the file.

Only download files that you have the right to access.

## If something does not work

- **The browser page will not open:** Check that the server is still running in the terminal. Try `http://localhost:8765` again.
- **The video list is empty:** Check that your videos are in the folder set by `VIDEO_DIR` in `player_server.py`.
- **A video will not play:** Try another browser. Some browsers cannot play some video or audio formats. The server may offer to prepare a compatible copy.
- **A package is missing:** Turn on the Python environment and run `python -m pip install av pygame pillow`.
- **The downloader reports a `libtorrent` error:** Install the correct `libtorrent` Python package for your operating system. The Ubuntu command above may not work on other systems.

