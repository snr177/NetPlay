"""A Netflix-inspired desktop video player backed by PyAV and Pygame."""

from __future__ import annotations

import queue
import re
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen
import tkinter as tk

try:
    import av
except ImportError:
    av = None

try:
    import pygame
except ImportError:
    pygame = None

try:
    from PIL import Image, ImageOps, ImageTk
except ImportError:
    Image = None
    ImageOps = None
    ImageTk = None


VIDEO_EXTENSIONS = {
    ".3gp",
    ".3g2",
    ".amv",
    ".avi",
    ".asf",
    ".divx",
    ".f4v",
    ".flv",
    ".m2v",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mod",
    ".mpe",
    ".mov",
    ".mxf",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ogv",
    ".qt",
    ".rm",
    ".rmvb",
    ".ts",
    ".vob",
    ".webm",
    ".wmv",
}
SUBTITLE_TYPES = (
    ("Subtitle files", "*.ass *.idx *.smi *.srt *.ssa *.sub *.vtt"),
    ("All files", "*.*"),
)
ASPECT_RATIOS: tuple[tuple[str, str | None], ...] = (
    ("Original", None),
    ("16:9", "16:9"),
    ("4:3", "4:3"),
    ("21:9", "21:9"),
)

BACKGROUND = "#090b10"
PANEL = "#11141d"
PANEL_LIGHT = "#191e29"
FOREGROUND = "#f4f4f5"
MUTED = "#9ca3af"
ACCENT = "#e50914"


class VideoPlayer:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CINEMA")
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = min(1440, max(800, screen_width - 24))
        window_height = min(880, max(520, screen_height - 48))
        self.root.geometry(
            f"{window_width}x{window_height}"
            f"+{max(0, (screen_width - window_width) // 2)}"
            f"+{max(0, (screen_height - window_height) // 2)}"
        )
        self.root.minsize(min(1000, window_width), min(560, window_height))
        self.root.configure(bg=BACKGROUND)

        self.audio_channel = None
        self.audio_available = False
        self.media_duration = 0.0
        self.playback_position = 0.0
        self.playback_started_at = 0.0
        self.is_paused = False
        self.backend_error: str | None = None
        self.worker_error: str | None = None
        self.decode_thread: threading.Thread | None = None
        self.decode_stop = threading.Event()
        self.video_queue: queue.Queue = queue.Queue(maxsize=3)
        self.audio_queue: queue.Queue = queue.Queue(maxsize=20)
        self.pending_video = None
        self.current_subtitle_cues: list[tuple[float, float, str]] = []
        self.external_subtitle_cues: list[tuple[float, float, str]] = []
        self.embedded_subtitle_stream: int | None = None
        self.last_frame = None
        self.current_file: Path | None = None
        self.video_files: list[Path] = []
        self.audio_tracks: list[tuple[int, str]] = []
        self.subtitle_tracks: list[tuple[int, str]] = []
        self.audio_ids: dict[str, int] = {}
        self.subtitle_ids: dict[str, tuple[str, object]] = {}
        self.aspect_index = 0
        self.is_seeking = False
        self.is_fullscreen = False

        self.folder = Path(__file__).resolve().parent / "downloads"
        self.folder_label = tk.StringVar(value=str(self.folder))
        self.search_text = tk.StringVar()
        self.now_playing = tk.StringVar(value="Choose a video to start watching")
        self.play_button_text = tk.StringVar(value="▶")
        self.aspect_button_text = tk.StringVar(value="Aspect: Original")
        self.audio_choice = tk.StringVar(value="No audio tracks")
        self.subtitle_choice = tk.StringVar(value="Off")
        self.time_label = tk.StringVar(value="00:00 / 00:00")
        self.status_text = tk.StringVar(value="")
        self.volume_value = tk.IntVar(value=80)

        self._configure_theme()
        self._build_layout()
        self._bind_shortcuts()
        self._load_backend()
        self._refresh_library()
        self._update_playback_status()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _configure_theme(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=PANEL_LIGHT,
            background=PANEL_LIGHT,
            foreground=FOREGROUND,
            arrowcolor=FOREGROUND,
            bordercolor=PANEL_LIGHT,
            lightcolor=PANEL_LIGHT,
            darkcolor=PANEL_LIGHT,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PANEL_LIGHT)],
            foreground=[("readonly", FOREGROUND)],
        )
        style.configure(
            "Horizontal.TScale",
            background=PANEL,
            troughcolor="#343946",
            bordercolor=PANEL,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )

    def _build_layout(self) -> None:
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        header = tk.Frame(self.root, bg=BACKGROUND, height=76)
        self.header = header
        header.grid(row=0, column=0, sticky="ew", padx=28)
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        tk.Label(
            header,
            text="N",
            bg=ACCENT,
            fg="white",
            font=("TkDefaultFont", 18, "bold"),
            width=2,
            height=1,
        ).grid(row=0, column=0, sticky="w", pady=19)
        tk.Label(
            header,
            text="CINEMA",
            bg=BACKGROUND,
            fg=FOREGROUND,
            font=("TkDefaultFont", 17, "bold"),
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))
        tk.Label(
            header,
            text="YOUR PERSONAL LIBRARY",
            bg=BACKGROUND,
            fg=MUTED,
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=0, column=2, sticky="e", padx=18)
        self._button(header, "Choose folder", self._choose_folder, compact=True).grid(
            row=0, column=3, sticky="e"
        )

        body = tk.Frame(self.root, bg=BACKGROUND)
        self.body = body
        body.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 20))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self._build_library(body)
        self._build_player(body)

    def _build_library(self, parent: tk.Frame) -> None:
        sidebar = tk.Frame(parent, bg=PANEL, width=310)
        self.sidebar = sidebar
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(4, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        tk.Label(
            sidebar,
            text="MY LIBRARY",
            bg=PANEL,
            fg=FOREGROUND,
            font=("TkDefaultFont", 13, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(20, 4))
        tk.Label(
            sidebar,
            textvariable=self.folder_label,
            bg=PANEL,
            fg=MUTED,
            font=("TkDefaultFont", 8),
            wraplength=265,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

        search = tk.Entry(
            sidebar,
            textvariable=self.search_text,
            bg=PANEL_LIGHT,
            fg=FOREGROUND,
            insertbackground=FOREGROUND,
            relief="flat",
            font=("TkDefaultFont", 10),
        )
        search.grid(row=2, column=0, sticky="ew", padx=18, ipady=9)
        search.insert(0, "")
        search.bind("<KeyRelease>", lambda _event: self._render_library())

        self.library_count = tk.Label(
            sidebar,
            text="0 VIDEOS",
            bg=PANEL,
            fg=MUTED,
            font=("TkDefaultFont", 8, "bold"),
        )
        self.library_count.grid(row=3, column=0, sticky="w", padx=18, pady=14)

        list_container = tk.Frame(sidebar, bg=PANEL)
        list_container.grid(row=4, column=0, sticky="nsew", padx=12)
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        self.video_list = tk.Listbox(
            list_container,
            bg=PANEL,
            fg=FOREGROUND,
            selectbackground="#482027",
            selectforeground=FOREGROUND,
            activestyle="none",
            relief="flat",
            highlightthickness=0,
            font=("TkDefaultFont", 10),
            borderwidth=0,
        )
        self.video_list.grid(row=0, column=0, sticky="nsew")
        self.video_list.bind("<Double-Button-1>", self._play_selected)
        scrollbar = tk.Scrollbar(
            list_container,
            command=self.video_list.yview,
            bg=PANEL,
            troughcolor=PANEL,
            activebackground="#454b58",
            relief="flat",
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.video_list.configure(yscrollcommand=scrollbar.set)

    def _build_player(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=BACKGROUND)
        self.content = content
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        title_bar = tk.Frame(content, bg=BACKGROUND)
        self.title_bar = title_bar
        title_bar.grid(row=0, column=0, sticky="ew", pady=(4, 14))
        title_bar.grid_columnconfigure(0, weight=1)
        tk.Label(
            title_bar,
            textvariable=self.now_playing,
            bg=BACKGROUND,
            fg=FOREGROUND,
            font=("TkDefaultFont", 15, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            title_bar,
            text="← / →  5 SEC     SPACE  PLAY / PAUSE     F  FULLSCREEN     A  ASPECT     B  AUDIO",
            bg=BACKGROUND,
            fg=MUTED,
            font=("TkDefaultFont", 8),
        ).grid(row=1, column=0, sticky="w", pady=(7, 0))

        self.video_surface = tk.Frame(content, bg="#020304")
        self.video_surface.grid(row=1, column=0, sticky="nsew")
        self.video_surface.bind("<Button-1>", self._toggle_playback)
        self.video_surface.bind("<Double-Button-1>", self._toggle_fullscreen)
        self.video_image = tk.Label(
            self.video_surface,
            bg="#020304",
            bd=0,
            cursor="hand2",
        )
        self.video_image.place(relx=0.5, rely=0.5, anchor="center")
        self.video_image.bind("<Button-1>", self._toggle_playback)
        self.video_image.bind("<Double-Button-1>", self._toggle_fullscreen)
        self.subtitle_overlay = tk.Label(
            self.video_surface,
            bg="#020304",
            fg="white",
            font=("TkDefaultFont", 18, "bold"),
            wraplength=1000,
            justify="center",
        )
        self.subtitle_overlay.place(relx=0.5, rely=0.94, anchor="s")

        self.playback_panel = tk.Frame(content, bg=PANEL)
        self.playback_panel.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.playback_panel.grid_columnconfigure(0, weight=1)
        self.seek_scale = ttk.Scale(
            self.playback_panel,
            from_=0,
            to=1,
            orient="horizontal",
            command=self._seek,
        )
        self.seek_scale.grid(
            row=0, column=0, columnspan=6, sticky="ew", padx=16, pady=(12, 2)
        )
        self.seek_scale.bind("<ButtonPress-1>", self._start_seek)
        self.seek_scale.bind("<ButtonRelease-1>", self._finish_seek)

        tk.Label(
            self.playback_panel,
            textvariable=self.time_label,
            bg=PANEL,
            fg=MUTED,
            font=("TkDefaultFont", 9),
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

        transport = tk.Frame(self.playback_panel, bg=PANEL)
        transport.grid(row=2, column=0, columnspan=6, sticky="ew", padx=14, pady=(0, 6))
        transport.grid_columnconfigure(7, weight=1)
        self._button(transport, "−5s", lambda: self._seek_by(-5000), compact=True).grid(
            row=0, column=0, padx=(0, 6)
        )
        self.play_button = self._button(
            transport,
            self.play_button_text,
            self._toggle_playback,
            prominent=True,
        )
        self.play_button.grid(row=0, column=1, padx=4)
        self._button(transport, "+5s", lambda: self._seek_by(5000), compact=True).grid(
            row=0, column=2, padx=(6, 14)
        )

        tk.Label(
            transport,
            text="VOL",
            bg=PANEL,
            fg=MUTED,
            font=("TkDefaultFont", 8, "bold"),
        ).grid(row=0, column=3, padx=(14, 4))
        ttk.Scale(
            transport,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.volume_value,
            command=self._set_volume,
            length=90,
        ).grid(row=0, column=4, sticky="w", padx=6)
        self._button(
            transport,
            self.aspect_button_text,
            self._cycle_aspect_ratio,
            compact=True,
        ).grid(row=0, column=5, padx=5)
        self._button(
            transport, "Fullscreen", self._toggle_fullscreen, compact=True
        ).grid(row=0, column=6, padx=(5, 0))

        tracks = tk.Frame(self.playback_panel, bg=PANEL)
        tracks.grid(row=3, column=0, columnspan=6, sticky="ew", padx=14, pady=(0, 12))
        self.audio_combo = self._track_combo(
            tracks, self.audio_choice, self._select_audio
        )
        self.audio_combo.grid(row=0, column=0, padx=(0, 5))
        self.subtitle_combo = self._track_combo(
            tracks, self.subtitle_choice, self._select_subtitle
        )
        self.subtitle_combo.grid(row=0, column=1, padx=5)
        self._button(
            tracks, "Import subtitle", self._import_subtitle, compact=True
        ).grid(row=0, column=2, padx=5)
        self._button(tracks, "Subtitle URL", self._add_subtitle_url, compact=True).grid(
            row=0, column=3, padx=5
        )

        self.status_label = tk.Label(
            content,
            textvariable=self.status_text,
            bg=BACKGROUND,
            fg=MUTED,
            font=("TkDefaultFont", 9),
            anchor="w",
        )
        self.status_label.grid(row=3, column=0, sticky="ew", pady=(9, 0))

    def _button(
        self,
        parent: tk.Misc,
        text: str | tk.StringVar,
        command,
        *,
        compact: bool = False,
        prominent: bool = False,
    ) -> tk.Button:
        background = ACCENT if prominent else PANEL_LIGHT
        foreground = "white" if prominent else FOREGROUND
        text_option = (
            {"textvariable": text} if isinstance(text, tk.Variable) else {"text": text}
        )
        return tk.Button(
            parent,
            command=command,
            bg=background,
            fg=foreground,
            activebackground="#bd0811" if prominent else "#252b38",
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            padx=10 if compact else 14,
            pady=6 if compact else 9,
            cursor="hand2",
            font=("TkDefaultFont", 9, "bold"),
            **text_option,
        )

    @staticmethod
    def _track_combo(parent: tk.Misc, variable: tk.StringVar, callback) -> ttk.Combobox:
        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            state="readonly",
            width=17,
            values=(),
        )
        combo.bind("<<ComboboxSelected>>", callback)
        return combo

    def _load_backend(self) -> None:
        missing = [
            name
            for name, module in (
                ("PyAV", av),
                ("Pygame", pygame),
                ("Pillow", Image),
                ("Pillow ImageTk", ImageTk),
                ("Pillow ImageOps", ImageOps),
            )
            if module is None
        ]
        if missing:
            self.backend_error = (
                f"Install playback dependencies with: "
                f"python -m pip install -r "
                f"{Path(__file__).with_name('requirements-play.txt')}"
            )
            self.status_text.set(f"Missing {', '.join(missing)}. {self.backend_error}")
            return

        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            self.audio_channel = pygame.mixer.Channel(0)
            self.audio_channel.set_volume(self.volume_value.get() / 100)
            self.audio_available = True
        except pygame.error as error:
            self.audio_available = False
            self.backend_error = f"Audio output unavailable: {error}"
            self.status_text.set(
                f"Video is available; audio output is unavailable: {error}"
            )

    def _bind_shortcuts(self) -> None:
        self.root.bind_all("<KeyPress>", self._handle_keypress, add="+")
        self.root.bind("<Escape>", self._exit_fullscreen)

    def _handle_keypress(self, event: tk.Event) -> str | None:
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text)):
            return None

        key = event.keysym.lower()
        if key == "space":
            self._toggle_playback()
        elif key == "left":
            self._seek_by(-5000)
        elif key == "right":
            self._seek_by(5000)
        elif key == "f":
            self._toggle_fullscreen()
        elif key == "a":
            self._cycle_aspect_ratio()
        elif key == "b":
            self._cycle_audio_track()
        else:
            return None
        return "break"

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(
            title="Choose your video library",
            initialdir=str(self.folder) if self.folder.is_dir() else str(Path.home()),
            parent=self.root,
        )
        if selected:
            self.folder = Path(selected)
            self.folder_label.set(str(self.folder))
            self._refresh_library()

    def _refresh_library(self) -> None:
        if not self.folder.is_dir():
            self.video_files = []
            self._render_library()
            self._set_library_status(
                f"Folder not found: {self.folder} — choose an existing video folder."
            )
            return

        try:
            self.video_files = sorted(
                (
                    path
                    for path in self.folder.rglob("*")
                    if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
                ),
                key=lambda path: (path.name.casefold(), str(path).casefold()),
            )
        except OSError as error:
            messagebox.showerror(
                "Could not read folder",
                f"Unable to read {self.folder}:\n{error}",
                parent=self.root,
            )
            return
        self._render_library()
        self._set_library_status(
            "Double-click a video to play."
            if self.video_files
            else "No supported video files found in this folder."
        )

    def _set_library_status(self, message: str) -> None:
        if self.backend_error:
            message = f"{message} {self.backend_error}"
        self.status_text.set(message)

    def _render_library(self) -> None:
        query = self.search_text.get().strip().casefold()
        files = [path for path in self.video_files if query in path.name.casefold()]
        self.video_list.delete(0, tk.END)
        for path in files:
            self.video_list.insert(tk.END, f"  {path.stem}")
        self.library_count.configure(
            text=f"{len(files)} VIDEO{'S' if len(files) != 1 else ''}"
        )

    def _play_selected(self, _event: tk.Event | None = None) -> None:
        selection = self.video_list.curselection()
        if not selection:
            return
        query = self.search_text.get().strip().casefold()
        visible_files = [
            path for path in self.video_files if query in path.name.casefold()
        ]
        if selection[0] < len(visible_files):
            self._play_file(visible_files[selection[0]])

    def _play_file(self, path: Path) -> None:
        if av is None or pygame is None:
            messagebox.showerror(
                "Playback unavailable",
                self.backend_error or "Install the playback dependencies first.",
                parent=self.root,
            )
            return
        try:
            with av.open(str(path)) as container:
                video_stream = next(
                    (stream for stream in container.streams if stream.type == "video"),
                    None,
                )
                if video_stream is None:
                    raise ValueError("This file does not contain a video stream.")

                audio_streams = [
                    stream for stream in container.streams if stream.type == "audio"
                ]
                subtitle_streams = [
                    stream for stream in container.streams if stream.type == "subtitle"
                ]
                self.media_duration = (
                    float(container.duration / av.time_base)
                    if container.duration is not None
                    else 0.0
                )
                self.audio_tracks = [
                    (stream.index, self._describe_stream(stream))
                    for stream in audio_streams
                ]
                self.subtitle_tracks = [
                    (stream.index, self._describe_stream(stream))
                    for stream in subtitle_streams
                ]

            self.current_file = path
            self.is_paused = False
            self.now_playing.set(path.stem)
            self.play_button_text.set("Ⅱ")
            self.audio_ids = self._make_track_options(self.audio_tracks)
            self.subtitle_ids = self._make_subtitle_options(self.subtitle_tracks)
            self.audio_combo.configure(values=list(self.audio_ids))
            self.subtitle_combo.configure(values=("Off", *self.subtitle_ids.keys()))
            self.audio_choice.set(next(iter(self.audio_ids), "No audio tracks"))
            self.subtitle_choice.set("Off")
            self.embedded_subtitle_stream = None
            self.external_subtitle_cues = []
            self.current_subtitle_cues = []
            self.subtitle_overlay.configure(text="")
            self.seek_scale.configure(to=max(1, self.media_duration * 1000))
            self.seek_scale.set(0)
            self.time_label.set(
                f"00:00 / {self._format_time(int(self.media_duration * 1000))}"
            )
            self._select_library_item(path)
            self._start_playback(0.0)
            status = f"Now playing: {path.name}"
            if not self.audio_available:
                status += " — audio output unavailable"
            self._set_library_status(status)
        except (OSError, ValueError, av.error.FFmpegError) as error:
            messagebox.showerror("Could not play video", str(error), parent=self.root)

    @staticmethod
    def _describe_stream(stream) -> str:
        metadata = stream.metadata or {}
        title = metadata.get("title", "").strip()
        language = metadata.get("language", "").strip()
        codec = stream.codec_context.name
        parts = [part for part in (language, title, codec) if part]
        return " — ".join(parts) or f"{stream.type} stream"

    def _select_library_item(self, path: Path) -> None:
        query = self.search_text.get().strip().casefold()
        visible_files = [
            item for item in self.video_files if query in item.name.casefold()
        ]
        for index, item in enumerate(visible_files):
            if item == path:
                self.video_list.selection_clear(0, tk.END)
                self.video_list.selection_set(index)
                self.video_list.see(index)
                break

    def _toggle_playback(self, _event: tk.Event | None = None) -> None:
        if self.current_file is None:
            return
        if not self.is_paused:
            self.playback_position = self._current_position()
            self.is_paused = True
            if self.audio_available and self.audio_channel is not None:
                self.audio_channel.pause()
            self.play_button_text.set("▶")
        else:
            self.playback_started_at = time.monotonic()
            self.is_paused = False
            if self.audio_available and self.audio_channel is not None:
                self.audio_channel.unpause()
            self.play_button_text.set("Ⅱ")

    def _seek_by(self, milliseconds: int) -> None:
        if self.current_file is None:
            return
        position = self._current_position() + milliseconds / 1000
        if self.media_duration > 0:
            position = min(self.media_duration, max(0, position))
        self._start_playback(position)

    def _start_seek(self, _event: tk.Event) -> None:
        self.is_seeking = True

    def _finish_seek(self, _event: tk.Event) -> None:
        self.is_seeking = False
        position = float(self.seek_scale.get()) / 1000
        if self.media_duration > 0:
            position = min(self.media_duration, max(0, position))
        self._start_playback(position)

    def _seek(self, value: str | float) -> None:
        if self.is_seeking:
            position = max(0, float(value)) / 1000
            self.time_label.set(
                f"{self._format_time(int(position * 1000))} / "
                f"{self._format_time(int(self.media_duration * 1000))}"
            )

    def _set_volume(self, value: str) -> None:
        if self.audio_channel is not None:
            self.audio_channel.set_volume(int(float(value)) / 100)

    @staticmethod
    def _make_track_options(
        tracks: list[tuple[int, str]],
    ) -> dict[str, int]:
        options: dict[str, int] = {}
        for track_id, name in tracks:
            label = f"{name}  (track {track_id})"
            options[label] = track_id
        return options

    @staticmethod
    def _make_subtitle_options(
        tracks: list[tuple[int, str]],
    ) -> dict[str, tuple[str, object]]:
        return {
            f"{name}  (track {track_id})": ("embedded", track_id)
            for track_id, name in tracks
        }

    @staticmethod
    def _put_queue(target: queue.Queue, item, stop: threading.Event) -> bool:
        while not stop.is_set():
            try:
                target.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def _start_playback(self, position: float) -> None:
        if self.current_file is None or av is None:
            return
        was_paused = self.is_paused
        self._stop_decoder()
        self._empty_queue(self.video_queue)
        self._empty_queue(self.audio_queue)
        self.pending_video = None
        self.current_subtitle_cues = []
        if self.audio_channel is not None:
            self.audio_channel.stop()
        self.subtitle_overlay.configure(text="")

        self.playback_position = max(0, position)
        self.playback_started_at = time.monotonic()
        self.is_paused = was_paused
        self.play_button_text.set("▶" if was_paused else "Ⅱ")
        selected_audio = self.audio_ids.get(self.audio_choice.get())
        selected_subtitle = self.subtitle_ids.get(self.subtitle_choice.get())
        self.embedded_subtitle_stream = (
            int(selected_subtitle[1])
            if selected_subtitle and selected_subtitle[0] == "embedded"
            else None
        )
        self.decode_stop = threading.Event()
        self.worker_error = None
        self.decode_thread = threading.Thread(
            target=self._decode_media,
            args=(
                self.current_file,
                self.playback_position,
                selected_audio,
                self.embedded_subtitle_stream,
                self.decode_stop,
            ),
            daemon=True,
        )
        self.decode_thread.start()

    @staticmethod
    def _empty_queue(target: queue.Queue) -> None:
        while True:
            try:
                target.get_nowait()
            except queue.Empty:
                return

    def _stop_decoder(self) -> None:
        self.decode_stop.set()
        if self.decode_thread is not None and self.decode_thread.is_alive():
            self.decode_thread.join(timeout=1)

    def _decode_media(
        self,
        path: Path,
        start_position: float,
        audio_stream_index: int | None,
        subtitle_stream_index: int | None,
        stop: threading.Event,
    ) -> None:
        try:
            with av.open(str(path)) as container:
                video_stream = next(
                    (stream for stream in container.streams if stream.type == "video"),
                    None,
                )
                if video_stream is None:
                    raise ValueError("This file does not contain a video stream.")
                streams = [video_stream]
                audio_stream = next(
                    (
                        stream
                        for stream in container.streams
                        if stream.type == "audio" and stream.index == audio_stream_index
                    ),
                    None,
                )
                subtitle_stream = next(
                    (
                        stream
                        for stream in container.streams
                        if stream.type == "subtitle"
                        and stream.index == subtitle_stream_index
                    ),
                    None,
                )
                if audio_stream is not None:
                    streams.append(audio_stream)
                if subtitle_stream is not None:
                    streams.append(subtitle_stream)
                subtitle_decoder = (
                    av.CodecContext.create(subtitle_stream.codec_context.name, "r")
                    if subtitle_stream is not None
                    else None
                )
                audio_resampler = (
                    av.AudioResampler(format="s16", layout="stereo", rate=44100)
                    if audio_stream is not None and self.audio_available
                    else None
                )
                if start_position > 0:
                    container.seek(
                        int(start_position * av.time_base),
                        backward=True,
                        any_frame=False,
                    )

                for packet in container.demux(streams):
                    if stop.is_set():
                        return
                    if packet.stream.type == "video":
                        for frame in packet.decode():
                            if stop.is_set():
                                return
                            timestamp = self._frame_time(frame, start_position)
                            if timestamp < start_position:
                                continue
                            if self.video_queue.full():
                                continue
                            image = frame.to_ndarray(format="rgb24")
                            try:
                                self.video_queue.put_nowait((timestamp, image))
                            except queue.Full:
                                continue
                    elif packet.stream.type == "audio" and audio_resampler:
                        for frame in packet.decode():
                            for output in audio_resampler.resample(frame):
                                timestamp = self._frame_time(output, start_position)
                                if timestamp + output.samples / 44100 < start_position:
                                    continue
                                sound = output.to_ndarray().tobytes()
                                if not self._put_queue(
                                    self.audio_queue,
                                    (timestamp, sound),
                                    stop,
                                ):
                                    return
                    elif (
                        packet.stream.type == "subtitle"
                        and subtitle_decoder is not None
                    ):
                        for subtitle in subtitle_decoder.decode(packet):
                            text = self._subtitle_text(subtitle)
                            if text:
                                timestamp = self._frame_time(packet, start_position)
                                if timestamp >= start_position:
                                    self.current_subtitle_cues.append(
                                        (timestamp, timestamp + 4.0, text)
                                    )
        except (av.error.FFmpegError, OSError, RuntimeError, ValueError) as error:
            if not stop.is_set():
                self.worker_error = str(error)

    @staticmethod
    def _frame_time(frame, fallback: float) -> float:
        if frame.pts is None or frame.time_base is None:
            return fallback
        return float(frame.pts * frame.time_base)

    @staticmethod
    def _subtitle_text(subtitle) -> str:
        text = getattr(subtitle, "text", b"")
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        if not text:
            text = getattr(subtitle, "ass", b"")
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            if text.count(",") >= 8:
                text = text.split(",", 8)[-1]
        return text.replace(r"\N", "\n").replace(r"\n", "\n").strip()

    def _current_position(self) -> float:
        if self.is_paused:
            return self.playback_position
        position = self.playback_position + max(
            0, time.monotonic() - self.playback_started_at
        )
        return min(position, self.media_duration) if self.media_duration else position

    def _select_audio(self, _event: tk.Event | None = None) -> None:
        if self.current_file is not None:
            self._start_playback(self._current_position())

    def _cycle_audio_track(self) -> None:
        if len(self.audio_tracks) < 2:
            return
        labels = list(self.audio_ids)
        try:
            next_index = (labels.index(self.audio_choice.get()) + 1) % len(labels)
        except ValueError:
            next_index = 0
        self.audio_choice.set(labels[next_index])
        self._select_audio()

    def _select_subtitle(self, _event: tk.Event | None = None) -> None:
        choice = self.subtitle_ids.get(self.subtitle_choice.get())
        if choice and choice[0] == "embedded":
            self._start_playback(self._current_position())
        elif choice and choice[0] == "external":
            self.external_subtitle_cues = choice[1]
            self._start_playback(self._current_position())
        else:
            self.embedded_subtitle_stream = None
            self.external_subtitle_cues = []
            self.current_subtitle_cues = []
            self.subtitle_overlay.configure(text="")
            if self.current_file is not None:
                self._start_playback(self._current_position())

    def _import_subtitle(self) -> None:
        if self.current_file is None:
            messagebox.showinfo(
                "Choose a video first",
                "Start a video before adding subtitles.",
                parent=self.root,
            )
            return
        selected = filedialog.askopenfilename(
            title="Import subtitle",
            filetypes=SUBTITLE_TYPES,
            parent=self.root,
        )
        if selected:
            self._add_subtitle(selected)

    def _add_subtitle_url(self) -> None:
        if self.current_file is None:
            messagebox.showinfo(
                "Choose a video first",
                "Start a video before adding subtitles.",
                parent=self.root,
            )
            return
        url = simpledialog.askstring(
            "Subtitle URL",
            "Paste a direct URL to a subtitle file:",
            parent=self.root,
        )
        if not url:
            return
        parsed = urlsplit(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            messagebox.showerror(
                "Invalid subtitle URL",
                "Enter a complete HTTP or HTTPS URL.",
                parent=self.root,
            )
            return
        self._add_subtitle(url.strip())

    def _add_subtitle(self, source: str) -> None:
        try:
            parsed = urlsplit(source)
            if parsed.scheme in {"http", "https"}:
                with urlopen(source, timeout=15) as response:
                    content = response.read(2 * 1024 * 1024 + 1)
                if len(content) > 2 * 1024 * 1024:
                    raise ValueError("Subtitle files must be smaller than 2 MiB.")
                name = Path(unquote(parsed.path)).name or "Online subtitles"
                text = content.decode("utf-8-sig")
            else:
                subtitle_path = Path(source).expanduser().resolve()
                if subtitle_path.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError("Subtitle files must be smaller than 2 MiB.")
                text = subtitle_path.read_text(encoding="utf-8-sig")
                name = subtitle_path.name
            cues = self._parse_subtitle_file(name, text)
            if not cues:
                raise ValueError("No readable subtitle cues were found.")
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror("Could not add subtitle", str(error), parent=self.root)
            return
        label = f"{name}  (external)"
        self.subtitle_ids[label] = ("external", cues)
        self.subtitle_combo.configure(values=("Off", *self.subtitle_ids.keys()))
        self.subtitle_choice.set(label)
        self.external_subtitle_cues = cues
        self.current_subtitle_cues = []
        self._start_playback(self._current_position())
        self._set_library_status(f"Loaded {len(cues)} subtitle cues from {name}.")

    @staticmethod
    def _parse_subtitle_file(name: str, text: str) -> list[tuple[float, float, str]]:
        cues: list[tuple[float, float, str]] = []

        def seconds(value: str) -> float:
            value = value.replace(",", ".")
            parts = value.split(":")
            if len(parts) != 3:
                raise ValueError(f"Invalid subtitle time: {value}")
            hours, minutes, seconds_part = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds_part)

        if Path(name).suffix.lower() in {".ass", ".ssa"}:
            for line in text.splitlines():
                if not line.startswith("Dialogue:"):
                    continue
                fields = line.removeprefix("Dialogue:").strip().split(",", 9)
                if len(fields) != 10:
                    continue
                start = seconds(fields[1])
                end = seconds(fields[2])
                content = fields[9]
                content = re.sub(r"\{[^}]*\}", "", content)
                content = content.replace(r"\N", "\n").replace(r"\n", "\n")
                if content.strip() and end >= start:
                    cues.append((start, end, content.strip()))
            return cues

        lines = text.lstrip("\ufeff").splitlines()
        timestamp = re.compile(
            r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*"
            r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
        )
        index = 0
        while index < len(lines):
            match = timestamp.search(lines[index])
            if match:
                start, end = seconds(match.group(1)), seconds(match.group(2))
                index += 1
                content: list[str] = []
                while index < len(lines) and lines[index].strip():
                    content.append(lines[index].strip())
                    index += 1
                if content and end >= start:
                    cues.append((start, end, "\n".join(content)))
            index += 1
        return cues

    def _cycle_aspect_ratio(self) -> None:
        self.aspect_index = (self.aspect_index + 1) % len(ASPECT_RATIOS)
        label, ratio = ASPECT_RATIOS[self.aspect_index]
        self.aspect_button_text.set(f"Aspect: {label}")
        if self.last_frame is not None:
            self._show_frame(self.last_frame)

    def _toggle_fullscreen(self, _event: tk.Event | None = None) -> None:
        self._set_fullscreen(not self.is_fullscreen)

    def _set_fullscreen(self, enabled: bool) -> None:
        self.is_fullscreen = enabled
        self.root.attributes("-fullscreen", enabled)
        if enabled:
            self.body.grid_configure(padx=0, pady=0)
            self.header.grid_remove()
            self.sidebar.grid_remove()
            self.content.grid_configure(column=0)
            self.body.grid_columnconfigure(0, weight=1)
            self.body.grid_columnconfigure(1, weight=0)
            self.title_bar.grid_remove()
            self.video_surface.grid_configure(row=0)
            self.status_label.grid_remove()
        else:
            self.body.grid_configure(padx=28, pady=(0, 20))
            self.header.grid()
            self.sidebar.grid()
            self.content.grid_configure(column=1)
            self.body.grid_columnconfigure(0, weight=0)
            self.body.grid_columnconfigure(1, weight=1)
            self.title_bar.grid()
            self.video_surface.grid_configure(row=1)
            self.status_label.grid()

    def _exit_fullscreen(self, _event: tk.Event | None = None) -> None:
        if self.is_fullscreen:
            self._set_fullscreen(False)

    def _update_playback_status(self) -> None:
        if self.current_file is not None:
            position = self._current_position()
            self._pump_audio()
            self._display_due_video(position)
            self._display_subtitle(position)
            current_ms = int(position * 1000)
            if not self.is_seeking:
                self.seek_scale.set(current_ms)
                self.time_label.set(
                    f"{self._format_time(current_ms)} / "
                    f"{self._format_time(int(self.media_duration * 1000))}"
                )
            if self.worker_error:
                error = self.worker_error
                self.worker_error = None
                self.is_paused = True
                self.play_button_text.set("▶")
                self._set_library_status(f"Playback error: {error}")
            elif (
                self.decode_thread is not None
                and not self.decode_thread.is_alive()
                and self.video_queue.empty()
                and self.audio_queue.empty()
                and self.pending_video is None
            ):
                if not self.is_paused:
                    self.is_paused = True
                    self.playback_position = min(position, self.media_duration)
                    self.play_button_text.set("▶")
        self.root.after(20, self._update_playback_status)

    def _pump_audio(self) -> None:
        if not self.audio_available or self.audio_channel is None or pygame is None:
            return
        if self.audio_channel.get_busy() and self.audio_channel.get_queue() is not None:
            return
        try:
            _timestamp, audio = self.audio_queue.get_nowait()
        except queue.Empty:
            return
        try:
            sound = pygame.mixer.Sound(buffer=audio)
            if self.audio_channel.get_busy():
                self.audio_channel.queue(sound)
            else:
                self.audio_channel.play(sound)
                if self.is_paused:
                    self.audio_channel.pause()
        except pygame.error as error:
            self.audio_available = False
            self.backend_error = f"Audio output unavailable: {error}"
            self._set_library_status(self.backend_error)

    def _display_due_video(self, position: float) -> None:
        newest_frame = None
        if self.pending_video is not None:
            timestamp, frame = self.pending_video
            if timestamp <= position + 0.02:
                newest_frame = frame
                self.pending_video = None
        while True:
            try:
                timestamp, frame = self.video_queue.get_nowait()
            except queue.Empty:
                break
            if timestamp > position + 0.02:
                self.pending_video = (timestamp, frame)
                break
            newest_frame = frame
        if newest_frame is not None:
            self.last_frame = newest_frame
            self._show_frame(newest_frame)

    def _show_frame(self, frame) -> None:
        if Image is None or ImageOps is None or ImageTk is None:
            return
        surface_width = self.video_surface.winfo_width()
        surface_height = self.video_surface.winfo_height()
        if surface_width <= 1 or surface_height <= 1:
            return
        image = Image.fromarray(frame)
        _ratio_label, ratio = ASPECT_RATIOS[self.aspect_index]
        if ratio:
            numerator, denominator = (int(value) for value in ratio.split(":"))
            target_ratio = numerator / denominator
            if ImageOps is not None:
                if surface_width / surface_height > target_ratio:
                    width = int(surface_height * target_ratio)
                    size = (width, surface_height)
                else:
                    height = int(surface_width / target_ratio)
                    size = (surface_width, height)
                image = ImageOps.fit(image, size)
        image.thumbnail(
            (surface_width, surface_height),
            Image.Resampling.LANCZOS,
        )
        self.video_photo = ImageTk.PhotoImage(image=image)
        self.video_image.configure(image=self.video_photo)

    def _display_subtitle(self, position: float) -> None:
        cues = self.external_subtitle_cues or self.current_subtitle_cues
        active = next(
            (text for start, end, text in cues if start <= position <= end),
            "",
        )
        self.subtitle_overlay.configure(text=active)

    def _close(self) -> None:
        self._stop_decoder()
        if self.audio_channel is not None:
            self.audio_channel.stop()
        if pygame is not None and self.audio_available:
            pygame.mixer.quit()
        self.root.destroy()

    @staticmethod
    def _format_time(milliseconds: int) -> str:
        total_seconds = max(0, milliseconds // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        return f"{minutes:02}:{seconds:02}"


def main() -> None:
    root = tk.Tk()
    VideoPlayer(root)
    root.mainloop()


if __name__ == "__main__":
    main()