import customtkinter as ctk
import subprocess
import threading
import queue
import re
import os
import sys
import time
import glob
import random  # Important for the pause
import json
import io
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from tkinter import filedialog

try:
    from PIL import Image
except ImportError:
    Image = None

# --- SYSTEM-FIX: CORRECT PATHS ---
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

os.chdir(application_path)
# -------------------------------------

# --- SETTINGS PERSISTENCE ---
SETTINGS_FILE = os.path.join(application_path, "settings.json")

DEFAULT_SETTINGS = {
    "output_dir": os.path.join(application_path, "videos"),
    "custom_output_dir": "",
    "use_custom_output": False,
    "yt_dlp_path": "yt-dlp.exe",
    "urls_file": "urls.txt",
    "cookie_mode": "none",
    "cookie_browser": "",
    "cookie_browser_profile": "",
    "cookie_file_path": "",
}

def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update(saved)
        except Exception:
            pass
    return settings

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# --- CONFIGURATION ---
class Config:
    _settings = load_settings()

    OUTPUT_DIR = _settings.get("output_dir", DEFAULT_SETTINGS["output_dir"])
    CUSTOM_OUTPUT_DIR = _settings.get("custom_output_dir", "")
    USE_CUSTOM_OUTPUT = _settings.get("use_custom_output", False)

    YT_DLP_PATH = _settings.get("yt_dlp_path", "yt-dlp.exe")
    URLS_FILE = _settings.get("urls_file", "urls.txt")
    ICON_FILE = "icon.ico"

    COOKIE_MODE = _settings.get("cookie_mode", "none")
    COOKIE_BROWSER = _settings.get("cookie_browser", "")
    COOKIE_BROWSER_PROFILE = _settings.get("cookie_browser_profile", "")
    COOKIE_FILE_PATH = _settings.get("cookie_file_path", "")

    @classmethod
    def reload(cls):
        cls._settings = load_settings()
        cls.OUTPUT_DIR = cls._settings.get("output_dir", DEFAULT_SETTINGS["output_dir"])
        cls.CUSTOM_OUTPUT_DIR = cls._settings.get("custom_output_dir", "")
        cls.USE_CUSTOM_OUTPUT = cls._settings.get("use_custom_output", False)
        cls.YT_DLP_PATH = cls._settings.get("yt_dlp_path", "yt-dlp.exe")
        cls.URLS_FILE = cls._settings.get("urls_file", "urls.txt")
        cls.COOKIE_MODE = cls._settings.get("cookie_mode", "none")
        cls.COOKIE_BROWSER = cls._settings.get("cookie_browser", "")
        cls.COOKIE_BROWSER_PROFILE = cls._settings.get("cookie_browser_profile", "")
        cls.COOKIE_FILE_PATH = cls._settings.get("cookie_file_path", "")

    @classmethod
    def save_all(cls):
        data = {
            "output_dir": cls.OUTPUT_DIR,
            "custom_output_dir": cls.CUSTOM_OUTPUT_DIR,
            "use_custom_output": cls.USE_CUSTOM_OUTPUT,
            "yt_dlp_path": cls.YT_DLP_PATH,
            "urls_file": cls.URLS_FILE,
            "cookie_mode": cls.COOKIE_MODE,
            "cookie_browser": cls.COOKIE_BROWSER,
            "cookie_browser_profile": cls.COOKIE_BROWSER_PROFILE,
            "cookie_file_path": cls.COOKIE_FILE_PATH,
        }
        save_settings(data)


# --- UI DEFINITION ---
class YtDlpUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("yt-dlp PowerUI")
        
        # Calculate window size and centered position
        win_width = 1300
        win_height = 900
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - win_width) // 2
        y = (screen_height - win_height) // 2
        self.geometry(f"{win_width}x{win_height}+{x}+{y}")
        
        if os.path.exists(Config.ICON_FILE):
            try: self.iconbitmap(Config.ICON_FILE)
            except: pass

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Layout Grid: Column 1 (Right) should grow
        self.grid_columnconfigure(1, weight=1)
        
        # Row 0: Toolbar, Row 1: Queue (large), Row 2: Placeholder, Row 3: Log
        self.grid_rowconfigure(0, weight=0)  # Toolbar
        self.grid_rowconfigure(1, weight=10) # Queue
        self.grid_rowconfigure(2, weight=0)  # Placeholder
        self.grid_rowconfigure(3, weight=1)  # Log

        # --- 1. SIDEBAR (Left) ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=5, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Controls", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(padx=20, pady=(20, 10))

        # Start Queue + Add directly below "Controls"
        self.start_btn = ctk.CTkButton(self.sidebar, text="▶ Start Queue", fg_color="green", height=40, font=ctk.CTkFont(size=14, weight="bold"), command=self.start_queue)
        self.start_btn.pack(padx=20, pady=(0, 25), fill="x")

        self.add_btn = ctk.CTkButton(self.sidebar, text="➕ Add", command=self.add_manual_job)
        self.add_btn.pack(padx=20, pady=(0, 10), fill="x")

        ctk.CTkLabel(self.sidebar, text="Manual Entry:", text_color="gray").pack(anchor="w", padx=20, pady=(10, 0))

        self.url_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Paste URL...")
        self.url_entry.pack(padx=20, pady=5, fill="x")

        # Time section panel with individual HH:MM:SS fields
        self.time_panel = TimeInputPanel(self.sidebar)
        self.time_panel.pack(padx=20, pady=5, fill="x")

        # Mode selection (Video/Audio)
        self.mode_var = ctk.StringVar(value="video")
        self.radio_video = ctk.CTkRadioButton(self.sidebar, text="Video (Best)", variable=self.mode_var, value="video", command=self.update_options)
        self.radio_video.pack(padx=20, pady=5, anchor="w")
        self.radio_mp3 = ctk.CTkRadioButton(self.sidebar, text="Audio (MP3)", variable=self.mode_var, value="mp3", command=self.update_options)
        self.radio_mp3.pack(padx=20, pady=5, anchor="w")

        # Quality & Format Dropdowns
        ctk.CTkLabel(self.sidebar, text="Quality/Resolution:", text_color="gray", font=("Arial", 11)).pack(anchor="w", padx=20, pady=(10, 0))
        self.quality_var = ctk.StringVar(value="Best")
        self.quality_combo = ctk.CTkComboBox(self.sidebar, variable=self.quality_var, values=["Best", "4K", "1080p", "720p", "480p"])
        self.quality_combo.pack(padx=20, pady=5, fill="x")

        ctk.CTkLabel(self.sidebar, text="Format:", text_color="gray", font=("Arial", 11)).pack(anchor="w", padx=20, pady=(5, 0))
        self.format_var = ctk.StringVar(value="MP4")
        self.format_combo = ctk.CTkComboBox(self.sidebar, variable=self.format_var, values=["MP4", "MKV", "WEBM"])
        self.format_combo.pack(padx=20, pady=5, fill="x")

        # Aspect Ratio Dropdown
        ctk.CTkLabel(self.sidebar, text="Aspect Ratio:", text_color="gray", font=("Arial", 11)).pack(anchor="w", padx=20, pady=(5, 0))
        self.ratio_var = ctk.StringVar(value="Original")
        self.ratio_combo = ctk.CTkComboBox(self.sidebar, variable=self.ratio_var, values=["Original", "9:16 (Vertical)"])
        self.ratio_combo.pack(padx=20, pady=5, fill="x")

        # Encoder Dropdown
        ctk.CTkLabel(self.sidebar, text="Encoder:", text_color="gray", font=("Arial", 11)).pack(anchor="w", padx=20, pady=(5, 0))
        self.encoder_var = ctk.StringVar(value="CPU (Standard)")
        self.encoder_combo = ctk.CTkComboBox(self.sidebar, variable=self.encoder_var, values=["CPU (Standard)", "GPU (NVIDIA)"])
        self.encoder_combo.pack(padx=20, pady=5, fill="x")

        # Custom output folder checkbox
        self.custom_output_var = ctk.BooleanVar(value=Config.USE_CUSTOM_OUTPUT)
        self.custom_output_checkbox = ctk.CTkCheckBox(
            self.sidebar, text="Use custom target folder",
            variable=self.custom_output_var, command=self.update_output_display
        )
        self.custom_output_checkbox.pack(padx=20, pady=(15, 2), anchor="w")

        # Output folder display + Browse
        self.output_dir_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.output_dir_frame.pack(padx=20, pady=(0, 5), fill="x")
        self.output_dir_label = ctk.CTkLabel(
            self.output_dir_frame,
            text=self._short_path(Config.CUSTOM_OUTPUT_DIR) if Config.CUSTOM_OUTPUT_DIR else "(Default)",
            text_color="#A9A9A9", font=("Arial", 10), anchor="w"
        )
        self.output_dir_label.pack(side="left", fill="x", expand=True)
        self.browse_btn = ctk.CTkButton(
            self.output_dir_frame, text="📁", width=32, height=24,
            fg_color="#444444", hover_color="#555555",
            command=self.browse_output_dir
        )
        self.browse_btn.pack(side="right")

        # Settings Button
        self.settings_btn = ctk.CTkButton(
            self.sidebar, text="⚙ Settings", fg_color="#444444",
            hover_color="#555555", height=28, font=("Arial", 11),
            command=self.open_settings
        )
        self.settings_btn.pack(padx=20, pady=(10, 5), fill="x")

        # --- 2. TOOLBAR (Right top, next to Controls) ---
        self.toolbar = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar.grid(row=0, column=1, padx=20, pady=(20, 5), sticky="ew")

        # Cookies/Auth (left) – Selection based on saved settings
        cookie_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        cookie_frame.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(cookie_frame, text="Cookies/Auth:", text_color="gray", font=("Arial", 11)).pack(side="left", padx=(0, 5))
        self.cookie_var = ctk.StringVar(value=self._cookie_setting_to_display())
        self.cookie_combo = ctk.CTkComboBox(
            cookie_frame, variable=self.cookie_var, width=200,
            values=["None", "Browser: Chrome", "Browser: Firefox", "Browser: Edge", "Browser: Brave", "Cookie File (Settings)"]
        )
        self.cookie_combo.pack(side="left")

        # Import urls.txt (middle-left)
        self.import_btn = ctk.CTkButton(self.toolbar, text="📂 Import urls.txt", fg_color="#555555", hover_color="#444444", command=self.import_from_file)
        self.import_btn.pack(side="left", padx=10)

        # Error Button (right)
        self.error_btn = ctk.CTkButton(self.toolbar, text="⚠️ Errors (0)", fg_color="#333333", hover_color="#444444", command=self.show_error_window)
        self.error_btn.pack(side="right", padx=(10, 0))

        # yt-dlp Update (right, before Errors)
        self.update_btn = ctk.CTkButton(self.toolbar, text="⬇ yt-dlp Update", fg_color="#444444", height=28, font=("Arial", 11), command=self.update_ytdlp)
        self.update_btn.pack(side="right", padx=5)

        # --- 3. JOB LIST (Right center - Large) ---
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Queue")
        self.scroll_frame.grid(row=1, column=1, padx=20, pady=(5, 5), sticky="nsew")
        
        # --- 4. LOG OUTPUT (Right bottom - Smaller) ---
        self.log_textbox = ctk.CTkTextbox(self, height=150, font=("Consolas", 11))
        self.log_textbox.grid(row=3, column=1, padx=20, pady=(5, 20), sticky="nsew")
        
        # Create target folder if not existing
        self.ensure_output_dirs()

        self.log_textbox.insert("0.0", f"--- System Ready | Save Location: {self.get_output_dir()} ---\n")

        self.is_running = False
        self.jobs = []
        self.failed_jobs = [] # List for failed jobs (URL, Mode, Time, Quality, Format)
        self.current_job = None
        self.current_process = None
        self.skip_requested = False
        self.thumbnail_size = (96, 54)
        self._thumb_images = []
        self.metadata_cache = {}
        self.thumbnail_cache = {}
        self.thumbnail_loading = set()

    def _short_path(self, path, max_len=30):
        """Shortens a path for display."""
        if not path:
            return "(Default)"
        if len(path) <= max_len:
            return path
        return "..." + path[-(max_len - 3):]

    def _cookie_setting_to_display(self):
        """Converts Config cookie settings to dropdown text."""
        mode = Config.COOKIE_MODE
        if mode == "browser":
            browser = Config.COOKIE_BROWSER.capitalize()
            return f"Browser: {browser}"
        elif mode == "file":
            return "Cookie File (Settings)"
        return "None"

    def browse_output_dir(self):
        """Opens a folder dialog to select the target folder."""
        folder = filedialog.askdirectory(title="Choose target folder")
        if folder:
            Config.CUSTOM_OUTPUT_DIR = folder
            Config.USE_CUSTOM_OUTPUT = True
            Config.save_all()
            self.custom_output_var.set(True)
            self.output_dir_label.configure(text=self._short_path(folder))
            self.log(f"Save location: {folder}", "SYS")

    def open_settings(self):
        """Opens the settings window."""
        SettingsWindow(self)

    def get_output_dir(self):
        """Returns the current save location (custom or default)."""
        if self.custom_output_var.get() and Config.CUSTOM_OUTPUT_DIR:
            return Config.CUSTOM_OUTPUT_DIR
        return os.path.abspath(Config.OUTPUT_DIR)

    def ensure_output_dirs(self):
        """Ensures the selected target folder exists."""
        output = self.get_output_dir()
        if not os.path.exists(output):
            os.makedirs(output, exist_ok=True)

    def update_output_display(self):
        """Logs the new save location when checkbox is changed."""
        self.log(f"Save location: {self.get_output_dir()}", "SYS")

    def update_options(self):
        mode = self.mode_var.get()
        if mode == "video":
            self.quality_combo.configure(values=["Best", "4K", "1080p", "720p", "480p"])
            self.quality_var.set("Best")
            self.format_combo.configure(values=["MP4", "MKV", "WEBM"])
            self.format_var.set("MP4")
        else:
            self.quality_combo.configure(values=["Best", "High", "Mid", "Low"])
            self.quality_var.set("Best")
            self.format_combo.configure(values=["MP3", "M4A", "WAV", "FLAC"])
            self.format_var.set("MP3")

    def show_error_window(self):
        if not self.failed_jobs: return
        ErrorWindow(self, self.failed_jobs, self.retry_failed_jobs)

    def retry_failed_jobs(self, jobs_to_retry):
        for job_data in jobs_to_retry:
             # Job Data: (url, mode, section, quality, fmt, ratio, encoder)
             self.create_job_widget(*job_data)
        self.failed_jobs = [] # Reset
        self._refresh_error_button()

    def log(self, message, tag="INFO"):
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_textbox.insert("end", f"[{timestamp}] [{tag}] {message}\n")
            self.log_textbox.see("end")
        except: pass

    def _build_cookie_args(self, cookie_selection):
        args = []
        if cookie_selection.startswith("Browser:"):
            browser_name = cookie_selection.split(": ", 1)[1].lower()
            profile = Config.COOKIE_BROWSER_PROFILE.strip()
            if profile:
                args += ['--cookies-from-browser', f'{browser_name}:{profile}']
            else:
                args += ['--cookies-from-browser', browser_name]
        elif "Cookie-Datei" in cookie_selection or cookie_selection.startswith("Datei:"):
            cookie_path = Config.COOKIE_FILE_PATH
            if cookie_path and os.path.exists(cookie_path):
                args += ['--cookies', cookie_path]
            elif cookie_path:
                self.log(f"Warning: Cookie file not found: {cookie_path}", "WARN")
        return args

    def _apply_job_metadata(self, job, title=None, thumbnail_url=None):
        def update_ui():
            if title:
                job.set_title(title)
            if thumbnail_url:
                self._load_thumbnail_async(job, thumbnail_url)
        self.after(0, update_ui)

    def _get_metadata_entry(self, url):
        return self.metadata_cache.setdefault(url, {})

    def _update_metadata_entry(self, url, **kwargs):
        entry = self._get_metadata_entry(url)
        for key, value in kwargs.items():
            if value is not None:
                entry[key] = value
        return entry

    def _extract_youtube_video_id(self, url):
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            path = parsed.path.strip('/')

            if host in {"youtu.be", "www.youtu.be"} and path:
                return path.split('/')[0]

            if "youtube.com" in host or "youtube-nocookie.com" in host:
                query_id = parse_qs(parsed.query).get("v")
                if query_id:
                    return query_id[0]

                parts = [p for p in path.split('/') if p]
                if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v"}:
                    return parts[1]
        except Exception:
            return None
        return None

    def _get_youtube_thumbnail_url(self, url):
        video_id = self._extract_youtube_video_id(url)
        if not video_id:
            return None
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    def _apply_cached_metadata_to_job(self, job, load_thumbnail=False):
        entry = self.metadata_cache.get(job.url)
        if not entry:
            return

        if entry.get("title"):
            job.set_title(entry["title"])

        cached_image = self.thumbnail_cache.get(job.url)
        if cached_image:
            job.set_thumbnail(cached_image)
        elif load_thumbnail and entry.get("thumbnail_url"):
            self._load_thumbnail_async(job, entry["thumbnail_url"])

    def _prime_job_preview(self, job):
        self._apply_cached_metadata_to_job(job, load_thumbnail=True)

        if self.metadata_cache.get(job.url, {}).get("thumbnail_url"):
            return

        thumb_url = self._get_youtube_thumbnail_url(job.url)
        if thumb_url:
            self._update_metadata_entry(job.url, thumbnail_url=thumb_url)
            self._apply_cached_metadata_to_job(job, load_thumbnail=True)

    def _fetch_ytdlp_title(self, url, cookie_selection):
        cmd = [Config.YT_DLP_PATH]
        cmd += self._build_cookie_args(cookie_selection)
        cmd += ['--print', 'title', '--skip-download', '--no-warnings', '--no-playlist', url]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode != 0:
            return None

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return lines[-1] if lines else None

    def _fetch_ytdlp_metadata(self, url, cookie_selection):
        cmd = [
            Config.YT_DLP_PATH,
            '--dump-single-json',
            '--skip-download',
            '--no-warnings',
            '--no-playlist',
            url
        ]
        cmd[1:1] = self._build_cookie_args(cookie_selection)
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}

        data = json.loads(result.stdout)
        if isinstance(data, dict) and data.get('entries'):
            entries = [e for e in data['entries'] if e]
            if entries:
                data = entries[0]
        return data if isinstance(data, dict) else {}



    def _extract_thumbnail_url(self, data):
        if not isinstance(data, dict):
            return None

        candidates = [
            data.get("thumbnail"),
            data.get("thumbnail_url"),
            data.get("thumb"),
            data.get("cover"),
            data.get("image"),
            data.get("poster"),
        ]

        thumbs = data.get("thumbnails")
        if isinstance(thumbs, list):
            for item in reversed(thumbs):
                if isinstance(item, dict) and item.get("url"):
                    candidates.append(item["url"])
        elif isinstance(thumbs, dict) and thumbs.get("url"):
            candidates.append(thumbs["url"])

        images = data.get("images")
        if isinstance(images, list):
            for item in images:
                if isinstance(item, dict) and item.get("url"):
                    candidates.append(item["url"])
                elif isinstance(item, str):
                    candidates.append(item)

        for candidate in candidates:
            if candidate and isinstance(candidate, str) and candidate.startswith("http"):
                return candidate
        return None

    def _fetch_job_metadata(self, job):
        try:
            thumb = self._get_youtube_thumbnail_url(job.url)
            title = None
            if thumb:
                self._update_metadata_entry(job.url, thumbnail_url=thumb)
            else:
                data = self._fetch_ytdlp_metadata(job.url, self.cookie_var.get())
                title = data.get("title")
                thumb = self._extract_thumbnail_url(data)
                self._update_metadata_entry(job.url, title=title, thumbnail_url=thumb)
            self._apply_cached_metadata_to_job(job, load_thumbnail=True)
        except Exception as e:
            self.log(f"Metadata not loaded for {job.url}: {e}", "META")

    def _ensure_job_metadata(self, job, cookie_selection, include_thumbnail=True):
        entry = self._get_metadata_entry(job.url)
        youtube_thumb = self._get_youtube_thumbnail_url(job.url)

        if youtube_thumb and not entry.get("thumbnail_url"):
            entry["thumbnail_url"] = youtube_thumb

        needs_fetch = False
        if youtube_thumb:
            needs_fetch = not entry.get("title")
        else:
            needs_fetch = not entry.get("title") or (include_thumbnail and not entry.get("thumbnail_url"))

        if needs_fetch:
            if youtube_thumb:
                title = self._fetch_ytdlp_title(job.url, cookie_selection)
                if not title:
                    data = self._fetch_ytdlp_metadata(job.url, cookie_selection)
                    title = data.get("title")
                    if not entry.get("thumbnail_url"):
                        entry["thumbnail_url"] = self._extract_thumbnail_url(data)
                self._update_metadata_entry(job.url, title=title)
            else:
                data = self._fetch_ytdlp_metadata(job.url, cookie_selection)
                self._update_metadata_entry(
                    job.url,
                    title=data.get("title"),
                    thumbnail_url=self._extract_thumbnail_url(data)
                )

        self._apply_cached_metadata_to_job(job, load_thumbnail=include_thumbnail)
        return self.metadata_cache.get(job.url, {})

    def _load_thumbnail_async(self, job, thumbnail_url):
        cached_image = self.thumbnail_cache.get(job.url)
        if cached_image:
            job.set_thumbnail(cached_image)
            return

        if job.url in self.thumbnail_loading:
            return

        def worker():
            try:
                if Image is None:
                    return
                self.thumbnail_loading.add(job.url)
                req = urllib.request.Request(thumbnail_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as response:
                    image_bytes = response.read()
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                resampling = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                image.thumbnail(self.thumbnail_size, resampling)

                bg = Image.new("RGB", self.thumbnail_size, "#1f1f1f")
                x = (self.thumbnail_size[0] - image.width) // 2
                y = (self.thumbnail_size[1] - image.height) // 2
                bg.paste(image, (x, y))

                ctk_image = ctk.CTkImage(light_image=bg, dark_image=bg, size=self.thumbnail_size)

                def update_ui():
                    self._thumb_images.append(ctk_image)
                    self.thumbnail_cache[job.url] = ctk_image
                    job.set_thumbnail(ctk_image)
                self.after(0, update_ui)
            except Exception:
                pass
            finally:
                self.thumbnail_loading.discard(job.url)

        threading.Thread(target=worker, daemon=True).start()

    def request_skip(self, job_widget):
        if not self.is_running or self.current_job is not job_widget:
            self.log("Skip only possible for the currently running job.", "WARN")
            return
        self.skip_requested = True
        job_widget.set_detail("Skip requested...")
        self.log(f"Skip requested: {job_widget.url}", "SKIP")
        process = self.current_process
        if process and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

    def _refresh_error_button(self):
        err_count = len(self.failed_jobs)
        self.error_btn.configure(text=f"⚠️ Errors ({err_count})")
        self.error_btn.configure(fg_color="#CD3838" if err_count > 0 else "#333333")

    def _normalize_name_for_match(self, name):
        if not name:
            return ""
        stem = os.path.splitext(str(name))[0]
        stem = re.sub(r'[<>:"/\\|?*]+', ' ', stem)
        stem = re.sub(r'\s+', ' ', stem).strip(" ._").casefold()
        return stem

    def _output_already_exists(self, output_dir, display_name):
        target = self._normalize_name_for_match(display_name)
        if not target or not os.path.isdir(output_dir):
            return False

        for entry in os.listdir(output_dir):
            path = os.path.join(output_dir, entry)
            if not os.path.isfile(path):
                continue
            if entry.endswith(('.part', '.ytdl', '.tmp')):
                continue

            existing = self._normalize_name_for_match(entry)
            if existing == target or existing.startswith(target + "_"):
                return True
        return False

    def _prepare_job_for_download(self, job, cookie_selection, output_dir, include_thumbnail=True):
        metadata = self._ensure_job_metadata(job, cookie_selection, include_thumbnail=include_thumbnail)
        display_name = metadata.get("output_name") or metadata.get("title") or job.title_text

        if self._output_already_exists(output_dir, display_name):
            job.set_status("skipped")
            job.set_detail("Already exists in target folder")
            job.set_progress(1.0)
            self.log(f"Skip existing: {display_name}", "SKIP")
            return metadata, True

        return metadata, False

    # --- JOB MANAGEMENT ---
    def delete_job(self, job_widget):
        if self.is_running:
            self.log("Deletion locked while queue is running!", "WARN")
            return
        if job_widget in self.jobs:
            self.jobs.remove(job_widget)
            job_widget.destroy()
            self.log("Entry removed.", "DEL")

    def create_job_widget(self, url, mode, section, quality="Best", fmt="MP4", ratio="Original", encoder="CPU (Standard)"):
        job_id = len(self.jobs)
        job_ui = JobWidget(
            self.scroll_frame, job_id, url, mode, section, quality, fmt, ratio, encoder,
            self.delete_job, self.request_skip
        )
        job_ui.pack(fill="x", padx=5, pady=5)
        self.jobs.append(job_ui)
        self._prime_job_preview(job_ui)

    def add_manual_job(self):
        url = self.url_entry.get().strip()
        if not url: return
        # Get sections from the TimeInputPanel
        sections = self.time_panel.get_sections()
        section_str = ",".join(sections) if sections else ""
        self.create_job_widget(url, self.mode_var.get(), section_str, self.quality_var.get(), self.format_var.get(), self.ratio_var.get(), self.encoder_var.get())
        self.url_entry.delete(0, "end")
        self.time_panel.clear()

    def import_from_file(self):
        if not os.path.exists(Config.URLS_FILE):
            self.log(f"File missing: {Config.URLS_FILE}", "ERR")
            return
        if self.is_running:
            self.log("Import locked while queue is running.", "WARN")
            return

        count = 0
        try:
            with open(Config.URLS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"): continue
                
                parts = line.split()
                url = parts[0]
                mode = "video"
                section_parts = []

                for token in parts[1:]:
                    token_lower = token.lower()
                    if re.match(r'^\d{2}:\d{2}:\d{2}-\d{2}:\d{2}:\d{2}$', token):
                        section_parts.append(token)
                    elif token_lower == 'mp3':
                        mode = 'mp3'

                section = ",".join(section_parts)
                self.create_job_widget(url, mode, section, "Best", "MP4" if mode == "video" else "MP3", "Original", "CPU (Standard)")
                count += 1
            self.log(f"{count} jobs imported.", "IMPORT")
        except Exception as e:
            self.log(f"Import error: {e}", "ERR")

    def update_ytdlp(self):
        self.update_btn.configure(state="disabled", text="Loading Update...")
        self.log("Starting yt-dlp Update...", "SYS")
        
        def run_update():
            try:
                cmd = [Config.YT_DLP_PATH, "-U"]
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
                out, _ = process.communicate()
                for line in out.splitlines():
                    if line.strip(): self.log(line, "UPDATE")
                self.log("Update process finished.", "SYS")
            except Exception as e:
                self.log(f"Update error: {e}", "ERR")
            finally:
                self.update_btn.configure(state="normal", text="⬇ yt-dlp Update")

        threading.Thread(target=run_update, daemon=True).start()

    # --- QUEUE PROCESSING ---
    def start_queue(self):
        if self.is_running: return
        
        pending = [j for j in self.jobs if j.status == "pending"]
        if not pending:
            self.log("No pending jobs.", "SYS")
            return

        self.is_running = True
        self.skip_requested = False
        self.start_btn.configure(state="disabled", text="Running...")
        self.import_btn.configure(state="disabled")
        
        cookie_setting = self.cookie_var.get()
        threading.Thread(target=self.process_queue, args=(cookie_setting,), daemon=True).start()

    def process_queue(self, cookie_setting):
        # List of pending jobs
        pending_jobs = [j for j in self.jobs if j.status == "pending"]
        
        for i, job in enumerate(pending_jobs):
            if not self.is_running: break
            
            # 1. Execute job
            result = self.run_single_job(job, cookie_setting)
            if result == "stopped":
                break

            # 2. PAUSE (If not the last job)
            if i < len(pending_jobs) - 1 and result != "skipped":
                wait_time = random.randint(5, 15)
                self.log(f"⏳ Waiting {wait_time} seconds (ban protection)...", "WAIT")
                
                # Wait step by step so "Cancel" remains possible
                for _ in range(wait_time):
                    if not self.is_running: break
                    time.sleep(1)
        
        self.is_running = False
        self.start_btn.configure(state="normal", text="▶ Start Queue")
        self.import_btn.configure(state="normal")
        self.log("All tasks completed.", "FINISH")

    def _build_base_cmd(self, job, output_template, cookie_selection):
        """Builds the base command for yt-dlp (without URL and without Section)."""
        cmd = [Config.YT_DLP_PATH]
        cmd += ['-o', output_template]
        cmd += self._build_cookie_args(cookie_selection)

        if job.mode == "mp3":
            cmd += ['--extract-audio', '--audio-format', job.fmt.lower()]
            if job.quality == "Best": cmd += ['--audio-quality', '0']
            elif job.quality == "High": cmd += ['--audio-quality', '2']
            elif job.quality == "Mid": cmd += ['--audio-quality', '5']
            elif job.quality == "Low": cmd += ['--audio-quality', '9']
        else:
            ext = job.fmt.lower()
            # Prefer H264 codec (avc1), fallback to any codec in desired container
            if ext == "mp4":
                h264_pref = "vcodec~='^(avc|h264)'"  # Prefer H264
            else:
                h264_pref = ""  # No codec filter for MKV/WEBM

            if job.quality == "Best":
                if h264_pref:
                    cmd += ['-f', f"bv*[ext={ext}][{h264_pref}]+ba[ext=m4a]/bv*[ext={ext}]+ba[ext=m4a]/b[ext={ext}]/best[ext={ext}]/best"]
                else:
                    cmd += ['-f', f"bv*[ext={ext}]+ba[ext=m4a]/b[ext={ext}]/best[ext={ext}]/best"]
            elif job.quality == "4K":
                if h264_pref:
                    cmd += ['-f', f"bv*[height<=2160][ext={ext}][{h264_pref}]+ba/bv*[height<=2160][ext={ext}]+ba/b[height<=2160][ext={ext}]"]
                else:
                    cmd += ['-f', f"bv*[height<=2160][ext={ext}]+ba/b[height<=2160][ext={ext}]"]
            elif job.quality == "1080p":
                if h264_pref:
                    cmd += ['-f', f"bv*[height<=1080][ext={ext}][{h264_pref}]+ba/bv*[height<=1080][ext={ext}]+ba/b[height<=1080][ext={ext}]"]
                else:
                    cmd += ['-f', f"bv*[height<=1080][ext={ext}]+ba/b[height<=1080][ext={ext}]"]
            elif job.quality == "720p":
                if h264_pref:
                    cmd += ['-f', f"bv*[height<=720][ext={ext}][{h264_pref}]+ba/bv*[height<=720][ext={ext}]+ba/b[height<=720][ext={ext}]"]
                else:
                    cmd += ['-f', f"bv*[height<=720][ext={ext}]+ba/b[height<=720][ext={ext}]"]
            elif job.quality == "480p":
                if h264_pref:
                    cmd += ['-f', f"bv*[height<=480][ext={ext}][{h264_pref}]+ba/bv*[height<=480][ext={ext}]+ba/b[height<=480][ext={ext}]"]
                else:
                    cmd += ['-f', f"bv*[height<=480][ext={ext}]+ba/b[height<=480][ext={ext}]"]
            else:
                if h264_pref:
                    cmd += ['-f', f"bv*[ext={ext}][{h264_pref}]+ba/bv*[ext={ext}]+ba/b[ext={ext}]"]
                else:
                    cmd += ['-f', f"bv*[ext={ext}]+ba/b[ext={ext}]"]

            if job.ratio == "9:16 (Vertical)":
                if job.encoder == "GPU (NVIDIA)":
                    cmd += ['--postprocessor-args', 'ffmpeg:-vf crop=trunc(ih*9/16/2)*2:ih:(iw-ow)/2:0 -c:v h264_nvenc -c:a aac']
                else:
                    cmd += ['--postprocessor-args', 'ffmpeg:-vf crop=trunc(ih*9/16/2)*2:ih:(iw-ow)/2:0 -c:v libx264 -preset fast -c:a aac']

        return cmd

    def _set_current_process(self, job, process):
        self.current_job = job
        self.current_process = process

    def _clear_current_process(self, process):
        if self.current_process is process:
            self.current_process = None

    def _stream_process_output(self, process, line_handler):
        buffer = ""
        while True:
            chunk = process.stdout.read(1)
            if chunk == "" and process.poll() is not None:
                break
            if not chunk:
                continue
            if chunk in ("\r", "\n"):
                if buffer:
                    line_handler(buffer)
                    buffer = ""
                continue
            buffer += chunk
        if buffer:
            line_handler(buffer)

    def _parse_ytdlp_progress(self, line):
        compact = re.sub(r'\s+', ' ', line).strip()
        pct_match = re.search(
            r'\[download\]\s+(?P<pct>\d{1,3}(?:\.\d+)?)%\s+of\s+(?P<total>.+?)\s+at\s+(?P<speed>.+?)\s+ETA\s+(?P<eta>\S+)',
            compact
        )
        if pct_match:
            pct = float(pct_match.group('pct'))
            detail = f"DL | {pct_match.group('pct')}% | {pct_match.group('total')} | {pct_match.group('speed')} | ETA {pct_match.group('eta')}"
            return detail, pct / 100.0

        fallback_match = re.search(
            r'\[download\]\s+(?P<done>\S+)\s+at\s+(?P<speed>.+?)(?:\s+ETA\s+(?P<eta>\S+))?$',
            compact
        )
        if fallback_match:
            detail = f"DL | {fallback_match.group('done')} | {fallback_match.group('speed')}"
            if fallback_match.group('eta'):
                detail += f" | ETA {fallback_match.group('eta')}"
            return detail, None

        return None, None

    def _handle_ytdlp_output_line(self, job, line):
        clean = self._clean_output(line)
        if not clean:
            return

        detail, progress = self._parse_ytdlp_progress(clean)
        if detail:
            job.set_detail(detail)
            if progress is not None:
                job.set_progress(progress)
            return

        lower = clean.lower()
        if lower.startswith('[download] destination:'):
            job.set_detail(f"DL | {clean.split(':', 1)[-1].strip()}")
        elif '[merger]' in lower:
            job.set_detail("DL | Merging formats...")
        elif '[extractaudio]' in lower:
            job.set_detail("DL | Converting audio...")
        elif '[ffmpeg]' in lower:
            job.set_detail("DL | FFmpeg processing...")
        elif '[metadata]' in lower:
            return

        self.log(clean, "CLI")

    def _run_ytdlp(self, job, cmd):
        """Executes a yt-dlp command, logs live and updates progress."""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        self._set_current_process(job, process)
        try:
            self._stream_process_output(process, lambda line: self._handle_ytdlp_output_line(job, line))
            process.wait()
        finally:
            self._clear_current_process(process)

        if self.skip_requested and process.returncode != 0:
            return "skipped"
        return process.returncode

    def _find_downloaded_file(self, output_dir, pattern_prefix):
        """Finds the downloaded file by prefix pattern."""
        for f in os.listdir(output_dir):
            if f.startswith(pattern_prefix) and not f.endswith('.part'):
                return os.path.join(output_dir, f)
        return None

    def _merge_with_ffmpeg(self, part_files, output_file, output_dir):
        """Merges multiple video files with FFmpeg concat (lossless)."""
        concat_path = os.path.join(output_dir, f"_concat_{int(time.time())}.txt")
        try:
            # Create concat list
            with open(concat_path, 'w', encoding='utf-8') as f:
                for pf in part_files:
                    # FFmpeg expects forward slashes or escaped backslashes
                    safe_path = pf.replace('\\', '/')
                    f.write(f"file '{safe_path}'\n")

            self.log(f"🔗 Merge: {len(part_files)} parts → {os.path.basename(output_file)}", "MERGE")

            merge_cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', concat_path, '-c', 'copy', output_file
            ]

            result = subprocess.run(
                merge_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                self.log(f"✅ Merge successful: {os.path.basename(output_file)}", "MERGE")
                # Cleanup: delete individual parts
                for pf in part_files:
                    try: os.remove(pf)
                    except: pass
                self.log(f"🗑️ {len(part_files)} individual parts deleted.", "MERGE")
                return True
            else:
                self.log(f"❌ Merge failed: {result.stdout[-500:]}", "ERR")
                return False
        except Exception as e:
            self.log(f"❌ Merge error: {e}", "ERR")
            return False
        finally:
            # Always clean up concat file
            if os.path.exists(concat_path):
                try: os.remove(concat_path)
                except: pass

    def _clean_output(self, text):
        """Entfernt ANSI-Codes und Steuerzeichen aus Ausgaben."""
        text = re.sub(r'\033\[[0-9;]*m', '', text)
        return text.replace('\x00', '').strip()


    def run_single_job(self, job, cookie_selection):
        self.current_job = job
        self.skip_requested = False
        job.set_status("running")
        job.set_skip_enabled(True)

        output_dir = self.get_output_dir()
        job.set_progress(0.0)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        _, already_exists = self._prepare_job_for_download(job, cookie_selection, output_dir, include_thumbnail=True)
        if already_exists:
            self._refresh_error_button()
            job.set_skip_enabled(False)
            self.current_job = None
            self.current_process = None
            return "skipped"

        self.log(f"Start: {job.url} [{job.quality}/{job.fmt}/{job.ratio}/{job.encoder}] → {output_dir}", "DL")

        # Check if multiple sections are present
        sections = []
        if job.section:
            for s in job.section.split(','):
                s = s.strip()
                if re.match(r'^\d{2}:\d{2}:\d{2}-\d{2}:\d{2}:\d{2}$', s):
                    sections.append(s)

        try:
            if len(sections) > 1:
                # ====== MULTI-SECTION: Download + Auto-Merge ======
                self.log(f"📋 {len(sections)} time sections detected – starting multi-download...", "DL")
                unique_prefix = f"_part_{int(time.time())}"
                part_files = []
                all_ok = True

                for idx, sec in enumerate(sections):
                    part_label = f"{unique_prefix}_{idx+1:03d}"
                    part_template = os.path.join(output_dir, f'%(title)s_%(id)s{part_label}.%(ext)s')

                    cmd = self._build_base_cmd(job, part_template, cookie_selection)
                    cmd += ['--download-sections', f"*{sec}", '--force-keyframes-at-cuts']
                    cmd.append(job.url)

                    self.log(f"⬇️ Part {idx+1}/{len(sections)}: {sec}", "DL")
                    returncode = self._run_ytdlp(job, cmd)

                    if returncode == "skipped":
                        job.set_status("skipped")
                        job.set_detail("DL | Skipped")
                        self._refresh_error_button()
                        job.set_skip_enabled(False)
                        self.current_job = None
                        self.current_process = None
                        return "skipped"

                    if returncode != 0:
                        self.log(f"❌ Part {idx+1} failed!", "ERR")
                        all_ok = False
                        break

                    # Find downloaded file
                    found = None
                    for f in os.listdir(output_dir):
                        if part_label in f and not f.endswith('.part'):
                            found = os.path.join(output_dir, f)
                            break

                    if found:
                        part_files.append(found)
                        self.log(f"✅ Part {idx+1}: {os.path.basename(found)}", "DL")
                    else:
                        self.log(f"⚠️ Part {idx+1}: File not found!", "WARN")
                        all_ok = False
                        break

                if all_ok and len(part_files) > 1:
                    # Final file: name of first part without part suffix
                    first_name = os.path.basename(part_files[0])
                    final_name = first_name.replace(f"{unique_prefix}_001", "_Final")
                    final_path = os.path.join(output_dir, final_name)

                    merge_ok = self._merge_with_ffmpeg(part_files, final_path, output_dir)
                    job.set_status("done" if merge_ok else "error")
                    if merge_ok:
                        job.set_detail("DL | 100% | Done")
                        job.set_progress(1.0)
                    if not merge_ok:
                        self.failed_jobs.append((job.url, job.mode, job.section, job.quality, job.fmt, job.ratio, job.encoder))
                else:
                    job.set_status("error" if not all_ok else "done")
                    if all_ok:
                        job.set_detail("DL | 100% | Done")
                        job.set_progress(1.0)
                    if not all_ok:
                        self.failed_jobs.append((job.url, job.mode, job.section, job.quality, job.fmt, job.ratio, job.encoder))

            else:
                # ====== SINGLE SECTION or NO SECTION (as before) ======
                output_template = os.path.join(output_dir, '%(title)s_%(id)s.%(ext)s')
                cmd = self._build_base_cmd(job, output_template, cookie_selection)

                if len(sections) == 1:
                    cmd += ['--download-sections', f"*{sections[0]}", '--force-keyframes-at-cuts']

                cmd.append(job.url)
                returncode = self._run_ytdlp(job, cmd)
                if returncode == "skipped":
                    job.set_status("skipped")
                    job.set_detail("DL | Skipped")
                    self._refresh_error_button()
                    job.set_skip_enabled(False)
                    self.current_job = None
                    self.current_process = None
                    return "skipped"
                job.set_status("done" if returncode == 0 else "error")
                if returncode == 0:
                    job.set_detail("DL | 100% | Done")
                    job.set_progress(1.0)
                if returncode != 0:
                    self.failed_jobs.append((job.url, job.mode, job.section, job.quality, job.fmt, job.ratio, job.encoder))

        except Exception as e:
            job.set_status("error")
            self.log(str(e), "CRIT")
            self.failed_jobs.append((job.url, job.mode, job.section, job.quality, job.fmt, job.ratio, job.encoder))
            result = "error"
        else:
            result = "done" if job.status == "done" else job.status

        # Update Error Button
        self._refresh_error_button()
        job.set_skip_enabled(False)
        self.current_job = None
        self.current_process = None
        return result

# --- TIME INPUT WIDGETS ---
class TimeSegmentWidget(ctk.CTkFrame):
    """A single time segment with start and end time (HH:MM:SS fields)."""
    def __init__(self, master, remove_callback=None, show_remove=True):
        super().__init__(master, fg_color="#2B2B2B", corner_radius=6)
        self.remove_callback = remove_callback
        self.all_entries = []  # All 6 fields flat: [start_h, start_m, start_s, end_h, end_m, end_s]
        self._vars = []       # StringVars for all 6 fields

        # Start time row
        start_frame = ctk.CTkFrame(self, fg_color="transparent")
        start_frame.pack(fill="x", padx=5, pady=(5, 2))
        ctk.CTkLabel(start_frame, text="▶", width=18, font=("Arial", 11)).pack(side="left")
        self.start_h, self.start_m, self.start_s = self._create_time_row(start_frame)

        # End time row
        end_frame = ctk.CTkFrame(self, fg_color="transparent")
        end_frame.pack(fill="x", padx=5, pady=(2, 5))

        # Remove button or dash label
        if show_remove and remove_callback:
            rm_btn = ctk.CTkButton(end_frame, text="🗑", width=18, height=20, fg_color="#CD3838", hover_color="#8B0000", font=("Arial", 9), command=lambda: self.remove_callback(self))
            rm_btn.pack(side="left")
        else:
            ctk.CTkLabel(end_frame, text="⏹", width=18, font=("Arial", 11)).pack(side="left")

        self.end_h, self.end_m, self.end_s = self._create_time_row(end_frame)

    def _create_time_row(self, parent):
        """Creates an HH:MM:SS input row and adds the fields to all_entries."""
        entries = []
        for i in range(3):
            var = ctk.StringVar()
            entry = ctk.CTkEntry(parent, width=36, textvariable=var, justify="center",
                                 placeholder_text="00", font=("Consolas", 13))
            entry.pack(side="left", padx=1)
            entries.append(entry)

            # Calculate global index (0-5 across both rows)
            global_idx = len(self.all_entries)
            self.all_entries.append(entry)
            self._vars.append(var)

            # Auto-Tab: jump to next field after 2 characters (across both rows)
            var.trace_add('write', lambda *args, v=var, gi=global_idx: self._on_input(v, gi))

            # Allow only digits
            entry.bind('<Key>', lambda event: self._validate_key(event))

            if i < 2:
                ctk.CTkLabel(parent, text=":", width=8, font=("Consolas", 13, "bold")).pack(side="left")

        return entries[0], entries[1], entries[2]

    def _validate_key(self, event):
        """Allows only digits, Tab, Backspace, Delete, arrow keys."""
        allowed = {'BackSpace', 'Delete', 'Left', 'Right', 'Tab', 'Home', 'End'}
        if event.keysym in allowed:
            return None
        if event.char and event.char.isdigit():
            return None
        return 'break'

    def _on_input(self, var, global_idx):
        """Auto-Tab after 2 characters — also jumps from Start-SS to End-HH."""
        val = var.get()
        # Keep only digits
        digits = ''.join(c for c in val if c.isdigit())
        if digits != val:
            var.set(digits)
            return
        if len(digits) > 2:
            var.set(digits[:2])
        if len(digits) >= 2:
            # Jump to next field (0→1→2→3→4→5)
            if global_idx < len(self.all_entries) - 1:
                self.all_entries[global_idx + 1].focus_set()

    def get_section(self):
        """Returns the time segment as 'HH:MM:SS-HH:MM:SS' string, or None if empty."""
        start_vals = [self.start_h.get(), self.start_m.get(), self.start_s.get()]
        end_vals = [self.end_h.get(), self.end_m.get(), self.end_s.get()]

        # Check if at least one field is filled
        if all(not v for v in start_vals + end_vals):
            return None

        # Fill empty fields with "00"
        start = ":".join(v.zfill(2) if v else "00" for v in start_vals)
        end = ":".join(v.zfill(2) if v else "00" for v in end_vals)

        return f"{start}-{end}"

    def clear(self):
        """Resets all fields."""
        for entry in [self.start_h, self.start_m, self.start_s, self.end_h, self.end_m, self.end_s]:
            entry.delete(0, 'end')


class TimeInputPanel(ctk.CTkFrame):
    """Panel that manages multiple TimeSegmentWidgets with a + button."""
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.segments = []

        # Container for the segments
        self.segments_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.segments_frame.pack(fill="x")

        # Label
        ctk.CTkLabel(self, text="Time Sections (optional):", text_color="gray",
                     font=("Arial", 11)).pack(anchor="w", pady=(0, 3))

        # First segment (without remove button)
        self._add_segment(show_remove=False)

        # Plus button
        self.add_btn = ctk.CTkButton(self, text="➕ Add Section", height=24,
                                      fg_color="#444444", hover_color="#555555",
                                      font=("Arial", 11), command=self._add_with_remove)
        self.add_btn.pack(fill="x", pady=(3, 0))

    def _add_segment(self, show_remove=True):
        """Adds a new TimeSegmentWidget."""
        seg = TimeSegmentWidget(self.segments_frame,
                                remove_callback=self._remove_segment if show_remove else None,
                                show_remove=show_remove)
        seg.pack(fill="x", pady=2)
        self.segments.append(seg)
        return seg

    def _add_with_remove(self):
        """Adds a removable segment."""
        self._add_segment(show_remove=True)

    def _remove_segment(self, seg):
        """Removes a segment."""
        if seg in self.segments:
            self.segments.remove(seg)
            seg.destroy()

    def get_sections(self):
        """Returns a list of all valid time segments."""
        result = []
        for seg in self.segments:
            section = seg.get_section()
            if section and re.match(r'^\d{2}:\d{2}:\d{2}-\d{2}:\d{2}:\d{2}$', section):
                result.append(section)
        return result

    def clear(self):
        """Removes all segments and creates a new empty one."""
        for seg in self.segments:
            seg.destroy()
        self.segments.clear()
        self._add_segment(show_remove=False)


# --- WIDGET CLASS ---
class JobWidget(ctk.CTkFrame):
    def __init__(self, master, id, url, mode, section, quality, fmt, ratio, encoder, remove_callback, skip_callback):
        super().__init__(master, fg_color="#242424", corner_radius=8)
        self.status = "pending"
        self.url = url
        self.mode = mode
        self.section = section
        self.quality = quality
        self.fmt = fmt
        self.ratio = ratio
        self.encoder = encoder
        self.remove_callback = remove_callback
        self.skip_callback = skip_callback
        self.output_name = None
        self.title_text = url
        self.detail_text = self._build_default_detail()

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text=f"#{id+1}", width=30, font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5)

        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=6)
        self.info_frame.grid_columnconfigure(0, weight=1)

        self.lbl_title = ctk.CTkLabel(
            self.info_frame,
            text=self.title_text,
            anchor="w",
            justify="left",
            font=("Arial", 13, "bold"),
            wraplength=520
        )
        self.lbl_title.grid(row=0, column=0, sticky="ew")

        self.lbl_detail = ctk.CTkLabel(
            self.info_frame,
            text=self.detail_text,
            anchor="w",
            justify="left",
            text_color="#A9A9A9",
            wraplength=520
        )
        self.lbl_detail.grid(row=1, column=0, sticky="ew", pady=(2, 4))

        self.progress_bar = ctk.CTkProgressBar(self.info_frame, height=8)
        self.progress_bar.grid(row=2, column=0, sticky="ew")
        self.progress_bar.set(0)

        self.thumb_label = ctk.CTkLabel(self, text="No\nImage", width=96, height=54, corner_radius=6, fg_color="#1b1b1b")
        self.thumb_label.grid(row=0, column=2, padx=(8, 10), pady=6)

        self.lbl_status = ctk.CTkLabel(self, text="Pending", text_color="gray", width=80)
        self.lbl_status.grid(row=0, column=3, padx=5)

        self.btn_skip = ctk.CTkButton(self, text="⏭", width=40, fg_color="#666666", hover_color="#4F4F4F", command=self.on_skip, state="disabled")
        self.btn_skip.grid(row=0, column=4, padx=5, pady=5)

        self.btn_remove = ctk.CTkButton(self, text="❌", width=40, fg_color="#CD3838", hover_color="#8B0000", command=self.on_remove)
        self.btn_remove.grid(row=0, column=5, padx=(5, 10), pady=5)

    def _build_default_detail(self):
        detail = f"{self.mode.upper()} | {self.quality} | {self.fmt}"
        if self.ratio != "Original":
            detail += f" | {self.ratio} | {self.encoder}"
        if self.section:
            detail += f" | Cut: {self.section}"
        return detail

    def on_remove(self):
        self.remove_callback(self)

    def on_skip(self):
        self.skip_callback(self)

    def _refresh_info(self):
        self.lbl_title.configure(text=self.title_text)
        self.lbl_detail.configure(text=self.detail_text)

    def set_title(self, title):
        if not title:
            return
        self.title_text = title
        self._refresh_info()

    def set_detail(self, detail):
        if not detail:
            return
        self.detail_text = detail
        self._refresh_info()

    def set_thumbnail(self, image):
        self.thumb_label.configure(image=image, text="")
        self.thumb_label.image = image

    def set_progress(self, value):
        if value is None:
            return
        value = max(0.0, min(1.0, float(value)))
        self.progress_bar.set(value)

    def set_skip_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.btn_skip.configure(state=state)

    def set_status(self, status):
        self.status = status
        if status == "running":
            self.btn_remove.configure(state="disabled", fg_color="transparent", text="")
            self.btn_skip.configure(state="normal")
        elif status in ["done", "error", "skipped"]:
            self.btn_remove.configure(state="disabled", fg_color="transparent", text="")
            self.btn_skip.configure(state="disabled", fg_color="transparent", text="")

        if status == "running":
            self.lbl_status.configure(text="⏳ Loading...", text_color="#E0A800")
        elif status == "done":
            self.lbl_status.configure(text="✅ Done", text_color="#2CC985")
            self.progress_bar.set(1.0)
        elif status == "error":
            self.lbl_status.configure(text="❌ Error", text_color="#FF4D4D")
        elif status == "skipped":
            self.lbl_status.configure(text="⏭ Skipped", text_color="#D0A13A")

class ErrorWindow(ctk.CTkToplevel):
    def __init__(self, master, failed_jobs, retry_callback):
        super().__init__(master)
        self.title("Failed Downloads")
        self.geometry("600x400")
        self.retry_callback = retry_callback
        self.failed_jobs = failed_jobs

        ctk.CTkLabel(self, text=f"{len(failed_jobs)} downloads failed", font=("Arial", 16, "bold")).pack(pady=10)

        self.textbox = ctk.CTkTextbox(self)
        self.textbox.pack(fill="both", expand=True, padx=20, pady=10)

        text_content = ""
        for job in failed_jobs:
            # job ist tuple (url, mode, section, quality, fmt, ratio, encoder)
            text_content += f"{job[0]} | {job[3]} | {job[4]} | {job[5]} | {job[6]}\n"
        
        self.textbox.insert("0.0", text_content)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=20, pady=20)

        ctk.CTkButton(btn_frame, text="📋 Copy", command=self.copy_to_clipboard).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="🔄 Retry", fg_color="green", command=self.retry_all).pack(side="right", padx=10)

    def copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.textbox.get("0.0", "end"))

    def retry_all(self):
        self.retry_callback(self.failed_jobs)
        self.destroy()

class SettingsWindow(ctk.CTkToplevel):
    """Settings window for all configurable paths and options."""
    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("Settings")
        self.geometry("650x580")
        self.resizable(False, False)

        # Main container with scroll
        main = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(main, text="⚙ Settings", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 15))

        # --- Paths ---
        ctk.CTkLabel(main, text="Paths", font=ctk.CTkFont(size=14, weight="bold"), text_color="#6EA4FF").pack(anchor="w", pady=(10, 5))

        # Default Output
        self.output_dir_var = ctk.StringVar(value=Config.OUTPUT_DIR)
        self._add_path_row(main, "Standard-Zielordner:", self.output_dir_var, is_dir=True)

        # Custom Output
        self.custom_output_var = ctk.StringVar(value=Config.CUSTOM_OUTPUT_DIR)
        self._add_path_row(main, "Eigener Zielordner:", self.custom_output_var, is_dir=True)

        # yt-dlp path
        self.ytdlp_var = ctk.StringVar(value=Config.YT_DLP_PATH)
        self._add_path_row(main, "yt-dlp Pfad:", self.ytdlp_var, filetypes=[("Executable", "*.exe"), ("All", "*.*")])

        # urls.txt path
        self.urls_var = ctk.StringVar(value=Config.URLS_FILE)
        self._add_path_row(main, "URLs-Datei:", self.urls_var, filetypes=[("Text", "*.txt"), ("All", "*.*")])

        # --- Cookies ---
        ctk.CTkLabel(main, text="Cookies / Authentication", font=ctk.CTkFont(size=14, weight="bold"), text_color="#6EA4FF").pack(anchor="w", pady=(20, 5))

        # Cookie Mode
        cookie_mode_frame = ctk.CTkFrame(main, fg_color="transparent")
        cookie_mode_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(cookie_mode_frame, text="Mode:", width=150, anchor="w").pack(side="left")
        self.cookie_mode_var = ctk.StringVar(value=Config.COOKIE_MODE)
        ctk.CTkComboBox(
            cookie_mode_frame, variable=self.cookie_mode_var, width=200,
            values=["none", "browser", "file"]
        ).pack(side="left", fill="x", expand=True)

        # Browser Name
        browser_frame = ctk.CTkFrame(main, fg_color="transparent")
        browser_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(browser_frame, text="Browser:", width=150, anchor="w").pack(side="left")
        self.cookie_browser_var = ctk.StringVar(value=Config.COOKIE_BROWSER)
        ctk.CTkComboBox(
            browser_frame, variable=self.cookie_browser_var, width=200,
            values=["firefox", "chrome", "edge", "brave", "opera", "vivaldi"]
        ).pack(side="left", fill="x", expand=True)

        # Browser Profile
        profile_frame = ctk.CTkFrame(main, fg_color="transparent")
        profile_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(profile_frame, text="Browser profile (optional):", width=150, anchor="w").pack(side="left")
        self.cookie_profile_var = ctk.StringVar(value=Config.COOKIE_BROWSER_PROFILE)
        ctk.CTkEntry(profile_frame, textvariable=self.cookie_profile_var, placeholder_text="e.g., Profile1 or leave empty").pack(side="left", fill="x", expand=True)

        # Cookie File
        self.cookie_file_var = ctk.StringVar(value=Config.COOKIE_FILE_PATH)
        self._add_path_row(main, "Cookie-Datei:", self.cookie_file_var, filetypes=[("Text", "*.txt"), ("All", "*.*")])

        # --- Buttons ---
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(25, 10))

        ctk.CTkButton(
            btn_frame, text="💾 Save", fg_color="green", hover_color="#228B22",
            font=ctk.CTkFont(size=13, weight="bold"), height=36,
            command=self.save_and_close
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            btn_frame, text="Cancel", fg_color="#555555", hover_color="#444444",
            height=36, command=self.destroy
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            btn_frame, text="🔄 Reset Defaults", fg_color="#8B4513", hover_color="#A0522D",
            height=36, command=self.reset_defaults
        ).pack(side="left", padx=5)

    def _add_path_row(self, parent, label, var, is_dir=False, filetypes=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=3)
        ctk.CTkLabel(frame, text=label, width=150, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(frame, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse():
            if is_dir:
                path = filedialog.askdirectory(title=label)
            else:
                path = filedialog.askopenfilename(title=label, filetypes=filetypes or [("All", "*.*")])
            if path:
                var.set(path)

        ctk.CTkButton(frame, text="📁", width=32, height=28, fg_color="#444444", hover_color="#555555", command=browse).pack(side="right")

    def save_and_close(self):
        Config.OUTPUT_DIR = self.output_dir_var.get()
        Config.CUSTOM_OUTPUT_DIR = self.custom_output_var.get()
        Config.YT_DLP_PATH = self.ytdlp_var.get()
        Config.URLS_FILE = self.urls_var.get()
        Config.COOKIE_MODE = self.cookie_mode_var.get()
        Config.COOKIE_BROWSER = self.cookie_browser_var.get()
        Config.COOKIE_BROWSER_PROFILE = self.cookie_profile_var.get()
        Config.COOKIE_FILE_PATH = self.cookie_file_var.get()
        Config.save_all()

        # Update UI
        if hasattr(self.master_app, 'output_dir_label'):
            display = self.master_app._short_path(Config.CUSTOM_OUTPUT_DIR) if Config.CUSTOM_OUTPUT_DIR else "(Default)"
            self.master_app.output_dir_label.configure(text=display)
        if hasattr(self.master_app, 'cookie_var'):
            self.master_app.cookie_var.set(self.master_app._cookie_setting_to_display())

        self.master_app.log("Settings saved.", "SYS")
        self.destroy()

    def reset_defaults(self):
        self.output_dir_var.set(DEFAULT_SETTINGS["output_dir"])
        self.custom_output_var.set("")
        self.ytdlp_var.set(DEFAULT_SETTINGS["yt_dlp_path"])
        self.urls_var.set(DEFAULT_SETTINGS["urls_file"])
        self.cookie_mode_var.set("none")
        self.cookie_browser_var.set("")
        self.cookie_profile_var.set("")
        self.cookie_file_var.set("")


if __name__ == "__main__":
    app = YtDlpUI()
    app.mainloop()
