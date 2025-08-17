import os
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, Scale, filedialog
from tkinter import messagebox, filedialog
import pywinstyles
import json
import threading
import sounddevice as sd
import soundfile as sf
import numpy as np
import requests
import re
from urllib.parse import quote

SETTINGS_FILE = "settings.json"
DEFAULT_AUDIO_DIR = "audio"
styles = ["Choose Style", "dark", "mica", "aero", "transparent", "acrylic", "win7",
          "inverse", "popup", "native", "optimised", "light"]

class TaggedCTkTextbox(ctk.CTkTextbox):
    def tag_configure(self, tagname, **options):
        self._textbox.tag_configure(tagname, **options)
        
    def insert(self, index, text, tags=None):
        if tags:
            self._textbox.insert(index, text, tags)
        else:
            super().insert(index, text)


class SoundDevice:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data, self.samplerate = sf.read(file_path, always_2d=True)
        self.playing = False
        self.paused = False
        self.volume = 1.0
        self.stream = None
        self.position = 0
        self.thread = None
        # Total duration in seconds
        self.duration = len(self.data) / self.samplerate
        # For effects
        self.reverb_amount = 0.0
        self.delay_amount = 0.0
        self.eq_low = 1.0
        self.eq_mid = 1.0
        self.eq_high = 1.0
        self.effects_enabled = True  # Default to off
        self.eq_enabled = True       # Default to off

    def play(self):
        if self.paused:
            self.paused = False
            self.playing = True
            return

        if self.playing:
            return

        self.playing = True
        self.thread = threading.Thread(target=self._play_audio)
        self.thread.daemon = True
        self.thread.start()

    # Add this new method for seeking

    def seek(self, position_percent):
        """Seek to a position in the audio file based on percentage (0.0-1.0)"""
        if position_percent < 0.0:
            position_percent = 0.0
        elif position_percent > 1.0:
            position_percent = 1.0

        # Convert percentage to frames
        new_position = int(len(self.data) * position_percent)
        self.position = new_position

    # Add this method to get current position in seconds
    def get_position_seconds(self):
        """Get current playback position in seconds"""
        return self.position / self.samplerate

    # Add this method to get duration in seconds
    def get_duration_seconds(self):
        """Get total duration in seconds"""
        return self.duration

    # Add this method to format time as MM:SS
    def format_time(self, seconds):
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    # Update the _play_audio method to apply effects
    def _play_audio(self):
        chunk_size = 2048  # You can adjust this for performance
        # At initialization, pre-allocate buffers
        self.reverb_buffer = np.zeros_like(self.data[:chunk_size])
        self.delay_buffer = np.zeros_like(self.data[:chunk_size])

        def callback(outdata, frames, time, status):
            if self.paused:
                outdata.fill(0)
                return

            if self.position >= len(self.data):
                self.playing = False
                self.position = 0
                raise sd.CallbackStop

            end_pos = min(self.position + frames, len(self.data))
            current_chunk = self.data[self.position:end_pos]

            # Apply effects if enabled
            if self.effects_enabled:
                # Simple reverb effect (very basic)
                if self.reverb_amount > 0:
                    # 100ms reverb tail
                    reverb_frames = int(0.1 * self.samplerate)
                    if self.position > reverb_frames:
                        reverb_pos = self.position - reverb_frames
                        reverb_end = min(reverb_pos + frames, len(self.data))
                        reverb_chunk = self.data[reverb_pos:reverb_end]

                        if len(reverb_chunk) == len(current_chunk):
                            current_chunk = current_chunk + \
                                (reverb_chunk * self.reverb_amount)

                # Simple delay effect
                if self.delay_amount > 0:
                    delay_frames = int(0.3 * self.samplerate)  # 300ms delay
                    if self.position > delay_frames:
                        delay_pos = self.position - delay_frames
                        delay_end = min(delay_pos + frames, len(self.data))
                        delay_chunk = self.data[delay_pos:delay_end]

                        if len(delay_chunk) == len(current_chunk):
                            current_chunk = current_chunk + \
                                (delay_chunk * self.delay_amount)

            # Apply EQ if enabled
            if self.eq_enabled:
                if self.eq_low != 1.0 or self.eq_mid != 1.0 or self.eq_high != 1.0:
                    if current_chunk.shape[1] >= 2:  # Stereo
                        current_chunk[:, 0] *= self.eq_low
                        current_chunk[:, 1] *= self.eq_high
                    current_chunk *= self.eq_mid

            # Pad if we're at the end of the file
            if len(current_chunk) < frames:
                outdata[:len(current_chunk)] = current_chunk * self.volume
                outdata[len(current_chunk):].fill(0)
                self.playing = False
                self.position = 0
                raise sd.CallbackStop
            else:
                outdata[:] = current_chunk * self.volume
                self.position += frames

        try:
            stream = sd.OutputStream(
                samplerate=self.samplerate,
                blocksize=chunk_size,
                channels=self.data.shape[1],
                callback=callback
            )
            stream.start()

            # Use an Event to wait instead of polling
            finished = threading.Event()
            while self.playing and not finished.is_set():
                finished.wait(0.1)  # More efficient waiting

            stream.stop()
            stream.close()
        except Exception as e:
            print(f"Audio playback error: {e}")
            self.playing = False
            self.position = 0

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def stop(self):
        self.playing = False
        self.paused = False
        self.position = 0

    def set_volume(self, volume):
        self.volume = float(volume)

    def get_volume(self):
        return self.volume

    # Add methods for effects
    def set_reverb(self, amount):
        """Set reverb amount (0.0 - 1.0)"""
        self.reverb_amount = max(0.0, min(1.0, amount))

    def set_delay(self, amount):
        """Set delay amount (0.0 - 1.0)"""
        self.delay_amount = max(0.0, min(1.0, amount))

    def set_eq(self, low=None, mid=None, high=None):
        """Set EQ bands (0.0 - 2.0 for each band)"""
        if low is not None:
            self.eq_low = max(0.0, min(2.0, low))
        if mid is not None:
            self.eq_mid = max(0.0, min(2.0, mid))
        if high is not None:
            self.eq_high = max(0.0, min(2.0, high))



class AudioMixerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.geometry("500x200")
        self.title("Audio Mixer")
        self.audio_files = []
        self.audio_controls = {}
        self.is_paused = False
        self.genius_api_key = ""
        self.current_theme = tk.StringVar(value="Choose Style")
        
        
        
        self.auto_scroll_active = False
        self.current_file = "lyrics.txt"  # Default file type

        self.effects_enabled = True  # Default to off
        self.eq_enabled = True       # Default to off

        # Genius API configuration - you'll need to update these values with your actual API key
        self.genius_api_key = ""  # Will store in settings
        self.genius_api_url = "https://api.genius.com"



        # Nav Bar
        self.navbar = ctk.CTkFrame(self)
        self.navbar.pack(fill="x", padx=1, pady=1)
        self.navbar_label = ctk.CTkLabel(self.navbar, text="Audio Mixer", font=("Arial", 16, "bold"))
        self.navbar_label.pack(side="left", padx=10)

        self.theme_label = ctk.CTkLabel(self.navbar, text="Themes")
        self.theme_label.pack(side="left", pady=5)
        self.theme_menu = ctk.CTkOptionMenu(self.navbar, values=styles, variable=self.current_theme, command=self.change_style)
        self.theme_menu.pack(side="left", padx=10, pady=10)
    
        # Main PanedWindow
        self.main_pane = tk.PanedWindow(self, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True, padx=5, pady=5)

        # Left Frame
        self.left_frame = ctk.CTkFrame(self.main_pane)
        # Right Frame or Lyrics Frame
        self.lyrics_frame = ctk.CTkFrame(self.main_pane)

        self.main_pane.add(self.left_frame, minsize=100)  # Minimum size for the left pane
        self.main_pane.add(self.lyrics_frame, minsize=100)  # Minimum size for the right pane

        self.load_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.dir_frame = ctk.CTkFrame(self.left_frame)
        self.dir_frame.pack(fill="x", pady=5)

        self.dir_label = ctk.CTkLabel(self.dir_frame, text=f"Audio Directory: {self.audio_dir}")
        self.dir_label.pack(side="left", padx=5)

        self.select_dir_button = ctk.CTkButton(self.dir_frame, text="Select Directory", command=self.select_directory)
        self.select_dir_button.pack(side="right", padx=5)

        self.controls_frame = ctk.CTkFrame(self.left_frame)
        self.controls_frame.pack(fill="x", pady=5)

        self.master_play_button = ctk.CTkButton(self.controls_frame, width=30, text="Play All", command=self.play_all)
        self.master_pause_button = ctk.CTkButton(self.controls_frame, width=30, text="Pause All", command=self.pause_all)
        self.master_stop_button = ctk.CTkButton(self.controls_frame, width=30, text="Stop All", command=self.stop_all)

        self.master_play_button.pack(side="left", padx=5)
        self.master_pause_button.pack(side="left", padx=5)
        self.master_stop_button.pack(side="left", padx=5)


        self.master_seekbar_frame = ctk.CTkFrame(self.left_frame)
        self.master_seekbar_frame.pack(fill=tk.X, pady=5)

        self.current_time_label = ctk.CTkLabel(self.master_seekbar_frame, text="00:00")
        self.current_time_label.pack(side=tk.LEFT, padx=5)

        self.seekbar = ctk.CTkSlider(self.master_seekbar_frame,  from_=0, to=100, command=self.seek_position, orientation="horizontal") #use ctk slider
        self.seekbar.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=5) #use ctk side and fill

        self.total_time_label = ctk.CTkLabel(self.master_seekbar_frame, text="00:00")
        self.total_time_label.pack(side=tk.RIGHT, padx=5)

        self.update_timer = None



        self.effects_frame = ctk.CTkFrame(self.left_frame) #ctk frame
        self.effects_frame.pack(fill=ctk.X, pady=5, padx=5)

        self.reverb_frame = ctk.CTkFrame(self.effects_frame) #ctk frame
        self.reverb_frame.pack(fill=ctk.X, pady=2)

        self.reverb_label = ctk.CTkLabel(self.reverb_frame, text="Reverb:") #ctk label
        self.reverb_label.pack(side=ctk.LEFT, padx=5)

        self.reverb_slider = ctk.CTkSlider(self.reverb_frame, from_=0, to=1, width=80, orientation="horizontal",
                                            command=self.set_reverb_all) #ctk slider
        self.reverb_slider.pack(side=ctk.LEFT, fill=ctk.X, padx=5)

        # self.delay_frame = ctk.CTkFrame(self.effects_frame) #ctk frame
        # self.delay_frame.pack(fill=ctk.X, pady=2)

        self.delay_label = ctk.CTkLabel(self.reverb_frame, text="Delay:") #ctk label
        self.delay_label.pack(side=ctk.LEFT, padx=5)

        self.delay_slider = ctk.CTkSlider(self.reverb_frame, from_=0, to=1, width=80, orientation="horizontal",
                                           command=self.set_delay_all) #ctk slider
        self.delay_slider.pack(side=ctk.LEFT, fill=ctk.X, padx=5)

        self.eq_frame = ctk.CTkFrame(self.effects_frame) #ctk frame
        self.eq_frame.pack(fill=ctk.X, pady=2)

        self.eq_low_label = ctk.CTkLabel(self.eq_frame, text="Low:") #ctk label
        self.eq_low_label.pack(side=ctk.LEFT, padx=5)

        self.eq_low_slider = ctk.CTkSlider(self.eq_frame, from_=0, to=2, width=80, orientation="horizontal",
                                             command=self.set_eq_low_all) #ctk slider
        self.eq_low_slider.set(1.0)  # Default value
        self.eq_low_slider.pack(side=ctk.LEFT, fill=ctk.X, padx=5)

        self.eq_mid_label = ctk.CTkLabel(self.eq_frame, text="Mid:") #ctk label
        self.eq_mid_label.pack(side=ctk.LEFT, padx=5)

        self.eq_mid_slider = ctk.CTkSlider(self.eq_frame, from_=0, to=2, width=80, orientation="horizontal",
                                             command=self.set_eq_mid_all) #ctk slider
        self.eq_mid_slider.set(1.0)  # Default value
        self.eq_mid_slider.pack(side=ctk.LEFT, padx=5)

        self.eq_high_label = ctk.CTkLabel(self.eq_frame, text="High:") #ctk label
        self.eq_high_label.pack(side=ctk.LEFT, padx=5)

        self.eq_high_slider = ctk.CTkSlider(self.eq_frame, from_=0, to=2, width=80, orientation="horizontal",
                                              command=self.set_eq_high_all) #ctk slider
        self.eq_high_slider.set(1.0)  # Default value
        self.eq_high_slider.pack(side=ctk.LEFT, padx=5)

        self.effects_toggle = ctk.CTkCheckBox(self.effects_frame, text="Enable Effects",
                                                 command=self.toggle_effects) #ctk checkbutton
        self.effects_toggle.pack(side=ctk.LEFT, padx=5)

        self.eq_toggle = ctk.CTkCheckBox(self.effects_frame, text="Enable EQ",
                                            command=self.toggle_eq) #ctk checkbutton
        self.eq_toggle.pack(side=ctk.LEFT, padx=5)

        self.stem_controls_frame = ctk.CTkFrame(self.left_frame, height=160)  # Set a fixed height (in pixels) #ctk frame
        self.stem_controls_frame.pack(fill=ctk.X, pady=5)
        # Important! Prevents the frame from shrinking
        self.stem_controls_frame.pack_propagate(False)

        # Search Bar
        self.search_frame = ctk.CTkFrame(self.left_frame) #ctk frame
        self.search_frame.pack(fill=ctk.X, pady=5)

        self.search_entry = ctk.CTkEntry(self.search_frame) #ctk Entry
        self.search_entry.pack(side=ctk.LEFT, expand=True, fill=ctk.X, padx=5)
        self.search_entry.insert(0, "Search...")  # Placeholder text
        self.search_entry.bind("<KeyRelease>", self.search_tracks)

        self.clear_search_button = ctk.CTkButton(
            self.search_frame, text="X", command=self.clear_search) #ctk button
        self.clear_search_button.pack(side=ctk.RIGHT, padx=5)

        # Create a Treeview with three columns: Track Name, Lyrics, Chords
        self.track_list = ttk.Treeview(self.left_frame, columns=(
            "Track", "Lyrics", "Chords"), show="headings", height=10)
        self.track_list.pack(pady=0, fill=tk.BOTH, expand=True)

        # Set column headings
        self.track_list.heading("Track", text="Track Name")
        self.track_list.heading("Lyrics", text="Lyrics")
        self.track_list.heading("Chords", text="Chords")

        # Adjust column widths
        self.track_list.column("Track", width=200)
        self.track_list.column("Lyrics", width=80, anchor="center")
        self.track_list.column("Chords", width=80, anchor="center")

        self.load_tracks()
        # Bind double-click to load_stems
        self.track_list.bind("<Double-Button-1>", self.load_stems)

        self.text_size = 16  # Default font size
        self.text_font = "Monaco"


        # self.lyrics_text = ctk.CTkTextbox(self.lyrics_frame, wrap=tk.WORD, height=10, font=(
        #     self.text_font, self.text_size))
        # self.lyrics_text.pack(fill="both", expand=True, padx=5, pady=5)
        # self.lyrics_text.tag_configure("margin", lmargin1=20, lmargin2=20)
        # self.lyrics_text.insert("1.0", "", "margin")
        
        # Create the CTkTextbox
        self.lyrics_text = ctk.CTkTextbox(self.lyrics_frame, wrap=tk.WORD, height=10)
        self.lyrics_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Access the underlying Tkinter Text widget
        self.text_widget = self.lyrics_text._textbox
        self.text_widget.tag_configure("margin", lmargin1=20, lmargin2=20)
        self.text_widget.insert("1.0", "", "margin")

        # Create a container frame for buttons to ensure they stay in one row
        self.lyrics_controls_frame = ctk.CTkFrame(self.lyrics_frame) #ctk frame
        self.lyrics_controls_frame.pack(fill=ctk.X, pady=5)

        # Add buttons inside this frame
        self.increase_font_button = ctk.CTkButton(
            self.lyrics_controls_frame, width=20, text="A+", command=self.increase_font_size) #ctk Button
        self.increase_font_button.pack(side=ctk.LEFT, padx=5)

        self.decrease_font_button = ctk.CTkButton(
            self.lyrics_controls_frame, width=20, text="A-", command=self.decrease_font_size)
        self.decrease_font_button.pack(side=ctk.LEFT, padx=5)


        # Add the Genius API button
        self.fetch_lyrics_button = ctk.CTkButton(
            self.lyrics_controls_frame,  width=50, text="Fetch Lyrics", command=self.fetch_lyrics)
        self.fetch_lyrics_button.pack(side=tk.LEFT, padx=5)

        
        self.scroll_speed = tk.DoubleVar()
        self.scroll_speed.set(0.10)  # Default slow speed
        self.speed_slider = ctk.CTkSlider(self.lyrics_controls_frame, from_=0.01, to=1, width=80,
                                orientation="horizontal",  # Hide the default value display
                                command=self.update_scroll_speed, variable=self.scroll_speed)
        self.speed_slider.set(0.01)
        self.speed_slider.pack(side=tk.LEFT, padx=0)
     
     
        self.scroll_button = ctk.CTkButton(
            self.lyrics_controls_frame, width=50, text="Start Auto-Scroll", command=self.toggle_auto_scroll)
        self.scroll_button.pack(side=tk.LEFT, padx=5)

        self.toggle_button = ctk.CTkButton(
            self.lyrics_controls_frame,  width=50, text="Switch to Chords", command=self.toggle_lyrics_chords)
        self.toggle_button.pack(side=tk.LEFT, padx=5)

        self.save_button = ctk.CTkButton(
            self.lyrics_controls_frame, width=30, text="Save", command=self.save_text)
        self.save_button.pack(side=tk.RIGHT, padx=5)

        # Add this after creating the speed_slider
        self.speed_slider.bind("<MouseWheel>", self.on_mouse_wheel)  # For Windows

    def on_resize(self, event):
        self.settings["window_size"] = (self.winfo_width(), self.winfo_height())
        self.settings["column_widths"] = [self.left_frame.winfo_width(), self.lyrics_frame.winfo_width()]
        self.save_settings()

    def save_column_widths(self):
        # Get sash position (the position of the draggable separator)
        sash_pos = self.main_pane.sash_coord(0)[0]  # Get X-coordinate of the first sash
        self.settings["column_widths"] = [sash_pos, self.winfo_width() - sash_pos]
        self.save_settings()

    def change_style(self, style):
        if style == "Choose Style":
            return
        try:
            pywinstyles.apply_style(self, style)
            self.current_theme.set(style)
            self.save_settings()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply theme {style}: {e}")
            
        ttk.Style().configure("Treeview", background="#242728", foreground="#e2e5e9", fieldbackground="black")
            
    def load_settings(self):
        self.audio_dir = DEFAULT_AUDIO_DIR
        self.settings = {}

        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    settings = json.load(f)
                    self.settings = settings
                    
                    if "column_widths" in settings:
                        sash_pos = settings["column_widths"][0]
                        self.main_pane.sash_place(0, sash_pos, 0)  # Move the sash to the saved position

                    
                    if "genius_api_key" in settings:
                        self.genius_api_key = settings.get("genius_api_key")

                    stored_dir = settings.get("audio_dir")
                    if stored_dir and os.path.exists(stored_dir):
                        self.audio_dir = stored_dir
                        # self.dir_label.configure(text=f"Audio Directory: {self.audio_dir}")

                    # Load window size
                    window_size = settings.get("window_size", (500, 200))
                    self.geometry(f"{window_size[0]}x{window_size[1]}")

                    # Load column widths
                    column_widths = settings.get("column_widths", [250, 250])
                    # self.left_frame.configure(width=column_widths[0])
                    # self.lyrics_frame.configure(width=column_widths[1])

                    if column_widths:
                            self.main_pane.paneconfig(
                                self.left_frame, minsize=200, width=column_widths[0])
                            self.main_pane.paneconfig(
                                self.lyrics_frame, minsize=200, width=column_widths[1])


                    # Load and apply saved theme
                    theme_to_apply = settings.get("theme", "System")
                    if theme_to_apply != "Choose Style":
                        self.current_theme.set(theme_to_apply)
                        self.change_style(theme_to_apply)

            except Exception as e:
                messagebox.showwarning(
                    "Settings Error", f"Error loading settings: {e}\nUsing default settings.")

        if not os.path.exists(self.audio_dir):
            try:
                os.makedirs(self.audio_dir)
                messagebox.showinfo(
                    "Directory Created", f"Created audio directory: {self.audio_dir}")
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to create audio directory: {e}")

        # Check if Genius API key is set
        if not hasattr(self, 'genius_api_key') or not self.genius_api_key:
            self.request_genius_api_key()

    def request_genius_api_key(self):
        messagebox.showinfo("Genius API", "No Genius API key found in settings. Lyrics functionality will be limited.")
    
    def load_tracks(self):
        print(f"Loading tracks from {self.audio_dir}")

    def select_directory(self):
        directory = filedialog.askdirectory(title="Select Audio Directory")
        if directory:
            self.audio_dir = directory
            self.dir_label.configure(text=f"Audio Directory: {self.audio_dir}")
            self.save_settings()
            self.load_tracks()

    def save_settings(self):
        settings = {
            "audio_dir": self.audio_dir,
            "genius_api_key": self.genius_api_key if hasattr(self, 'genius_api_key') else "",
            "theme": self.current_theme.get(),
            "window_size": (self.winfo_width(), self.winfo_height()),
            "column_widths": [self.left_frame.winfo_width(), self.lyrics_frame.winfo_width()]
        }
        
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def play_all(self):
        if not self.audio_files:
            return

        for audio in self.audio_files:
            audio.play()
        self.is_paused = False

        # Start updating the seekbar
        if self.update_timer is None:
            self.update_seekbar()

    def stop_all(self):
        for audio in self.audio_files:
            audio.stop()
        self.is_paused = False

        # Reset seekbar and time labels
        self.seekbar.set(0)
        self.current_time_label.configure(text="00:00")

        # Cancel update timer
        if self.update_timer is not None:
            self.after_cancel(self.update_timer)
            self.update_timer = None

    def pause_all(self):
        if not self.audio_files:
            return

        if self.is_paused:
            for audio in self.audio_files:
                audio.unpause()
            self.is_paused = False
        else:
            for audio in self.audio_files:
                audio.pause()
            self.is_paused = True


    # def play_all(self):
    #     if not self.audio_files:
    #         return

    #     for audio in self.audio_files:
    #         audio.play()
    #     self.is_paused = False

    # def stop_all(self):
    #     for audio in self.audio_files:
    #         audio.stop()
    #     self.is_paused = False

        
        
    def toggle_mute(self, audio, button):
        if audio.get_volume() > 0:
            audio.set_volume(0)
            button.configure(text="Unmute")
        else:
            # Restore to slider value
            slider = self.audio_controls[audio]["volume_slider"]
            audio.set_volume(slider.get())
            button.configure(text="Mute")

    def set_volume(self, audio, value, label=None):
        audio.set_volume(float(value))
        if label:
            label.configure(text=f"{float(value):.1f}")

    def scroll_volume(self, event, slider, audio, label):
        delta = event.delta / 120
        new_volume = max(0, min(1, slider.get() + (delta * 0.1)))
        slider.set(new_volume)
        audio.set_volume(new_volume)
        label.configure(text=f"{new_volume:.1f}")
        
        
    def update_seekbar(self):
        """Update the seekbar and time labels based on current playback position"""
        if not self.audio_files or not self.audio_files[0].playing:
            # Cancel timer if not playing
            self.update_timer = None
            return False

        # Use the first audio file as a reference for position
        audio = self.audio_files[0]
        current_pos = audio.get_position_seconds()
        total_duration = audio.get_duration_seconds()

        # Check if the position has changed significantly (e.g., 1-second interval)
        if int(current_pos) != int(getattr(self, "last_update_position", -1)):
            self.last_update_position = int(current_pos)

            # Update labels with formatted time
            self.current_time_label.configure(text=audio.format_time(current_pos))
            self.total_time_label.configure(
                text=audio.format_time(total_duration))

            # Update seekbar position without triggering the callback
            if total_duration > 0:
                position_percent = (current_pos / total_duration) * 100
                self.seekbar.set(position_percent)

        # Schedule the next update
        self.update_timer = self.after(100, self.update_seekbar)
        return True
        
        
    def seek_position(self, position):
        """Handle seekbar movement"""
        if not self.audio_files:
            return

        position_percent = float(position) / 100.0
        for audio in self.audio_files:
            audio.seek(position_percent)
        
    # Replace the load_stems method to use SoundDevice instead of pygame:
    def load_stems(self, event):
        selected_item = self.track_list.selection()  # Get selected item
        if not selected_item:
            return
        song_name = self.track_list.item(selected_item[0], "values")[0]  # Get track name
        self.current_song_path = os.path.join(self.audio_dir, song_name)
        self.current_song_name = song_name  # Store the song name for use with API

        if self.audio_files:
            if self.audio_files[0].playing:
                loadfile = messagebox.askyesno(
                    "Load Steam", "Load the selected song and stop the current steam?")
                if loadfile:
                    self.stop_all()
                else:
                    return
                
        if not os.path.exists(self.current_song_path):
            messagebox.showerror("Error", "Song directory not found!")
            return

        # Clear lyrics
        self.lyrics_text.delete("1.0", tk.END)
        self.load_text()  # Load the selected file (lyrics or chords)

        # Reset seekbar and time labels
        self.seekbar.set(0)
        self.current_time_label.configure(text="00:00")
        self.total_time_label.configure(text="00:00")

        # Clear previous stems
        for widget in self.stem_controls_frame.winfo_children():
            widget.destroy()

        self.audio_files = []
        self.audio_controls = {}

        # Reset effects sliders
        self.reverb_slider.set(0)
        self.delay_slider.set(0)
        self.eq_low_slider.set(1.0)
        self.eq_mid_slider.set(1.0)
        self.eq_high_slider.set(1.0)

        for stem in os.listdir(self.current_song_path):
            if stem.lower().endswith((".mp3", ".wav", ".flac", ".ogg")):
                file_path = os.path.join(self.current_song_path, stem)
                audio = SoundDevice(file_path)
                self.audio_files.append(audio)

                # If this is the first file, update the total time display
                if len(self.audio_files) == 1:
                    self.total_time_label.configure(
                        text=audio.format_time(audio.get_duration_seconds()))

                stem_frame = ctk.CTkFrame(self.stem_controls_frame)
                stem_frame.pack(pady=2, fill="x")

                play_button = ctk.CTkButton(stem_frame, width=30, height=15, text="Play", command=lambda a=audio: a.play())
                play_button.pack(side=ctk.LEFT, padx=5)

                mute_button = ctk.CTkButton(stem_frame, width=30, height=15, text="Mute")
                mute_button.configure(command=lambda a=audio,b=mute_button: self.toggle_mute(a, b))
                mute_button.pack(side=ctk.LEFT, padx=5)

                # Create a frame to hold the slider and its label
                slider_frame = ctk.CTkFrame(stem_frame)
                slider_frame.pack(side="left", padx=5,
                                  fill="x", expand=False)

                # Create the volume slider without showing its value
                volume_slider = ctk.CTkSlider(slider_frame, from_=0, to=1, width=60, height=15,
                                      orientation="horizontal",  # Hide the default value display
                                      command=lambda v, a=audio: self.set_volume(a, v))
                volume_slider.set(1.0)
                volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

                # Create a label to show the value on the right
                volume_label = ctk.CTkLabel(slider_frame, text="1.0", height=15)
                volume_label.pack(side="right", padx=(0, 5))

                # Update the label when slider changes
                def update_volume(v, a=audio, lbl=volume_label):
                    lbl.configure(text=f"{float(v):.1f}")
                    a.set_volume(float(v))

                # Replace the original command with our new function
                volume_slider.configure(command=update_volume)

                # Bind mouse wheel for volume control with label update
                volume_slider.bind("<MouseWheel>", lambda event, s=volume_slider, a=audio, l=volume_label:
                                   self.scroll_volume(event, s, a, l))

                self.audio_controls[audio] = {
                    "mute_button": mute_button,
                    "volume_slider": volume_slider
                }

                label = ctk.CTkLabel(stem_frame, text=stem, height=15)
                label.pack(side="left", padx=5)
    
    # Effect methods
    def set_reverb_all(self, value):
        """Set reverb for all audio tracks"""
        for audio in self.audio_files:
            audio.set_reverb(float(value))

    def set_delay_all(self, value):
        """Set delay for all audio tracks"""
        for audio in self.audio_files:
            audio.set_delay(float(value))

    def set_eq_low_all(self, value):
        """Set low EQ for all audio tracks"""
        for audio in self.audio_files:
            audio.set_eq(low=float(value))

    def set_eq_mid_all(self, value):
        """Set mid EQ for all audio tracks"""
        for audio in self.audio_files:
            audio.set_eq(mid=float(value))

    def set_eq_high_all(self, value):
        """Set high EQ for all audio tracks"""
        for audio in self.audio_files:
            audio.set_eq(high=float(value))

    def toggle_effects(self):
        """Toggle enabling or disabling effects."""
        self.effects_enabled = not self.effects_enabled

    def toggle_eq(self):
        """Toggle enabling or disabling EQ."""
        self.eq_enabled = not self.eq_enabled

    def load_tracks(self):
        if not os.path.exists(self.audio_dir):
            messagebox.showerror("Error", "Audio directory not found!")
            return

        self.all_tracks = [song for song in os.listdir(
            self.audio_dir) if os.path.isdir(os.path.join(self.audio_dir, song))]
        self.track_list.delete(
            *self.track_list.get_children())  # Clear Treeview

        for track in self.all_tracks:
            track_path = os.path.join(self.audio_dir, track)
            has_lyrics = "✔" if os.path.exists(
                os.path.join(track_path, "lyrics.txt")) else "✘"
            has_chords = "✔" if os.path.exists(
                os.path.join(track_path, "chords.txt")) else "✘"

            self.track_list.insert("", tk.END, values=(
                track, has_lyrics, has_chords))  # Insert row
        
    def search_tracks(self, event):
        """Filter playlist based on search input."""
        query = self.search_entry.get().strip().lower()

        # Clear the Treeview (correct way)
        for item in self.track_list.get_children():
            self.track_list.delete(item)

        if query == "":
            # Restore original list
            for track in self.all_tracks:
                track_path = os.path.join(self.audio_dir, track)
                has_lyrics = "✔" if os.path.exists(
                    os.path.join(track_path, "lyrics.txt")) else "✘"
                has_chords = "✔" if os.path.exists(
                    os.path.join(track_path, "chords.txt")) else "✘"
                self.track_list.insert("", tk.END, values=(
                    track, has_lyrics, has_chords))
        else:
            filtered_tracks = [
                track for track in self.all_tracks if query in track.lower()]
            for track in filtered_tracks:
                track_path = os.path.join(self.audio_dir, track)
                has_lyrics = "✔" if os.path.exists(
                    os.path.join(track_path, "lyrics.txt")) else "✘"
                has_chords = "✔" if os.path.exists(
                    os.path.join(track_path, "chords.txt")) else "✘"
                self.track_list.insert("", tk.END, values=(
                    track, has_lyrics, has_chords))

    def request_genius_api_key(self):
        """Prompt the user to enter their Genius API key"""
        # Create a simple dialog to input the API key
        dialog = tk.Toplevel(self)
        dialog.title("Genius API Configuration")
        dialog.geometry("400x200")
        dialog.transient(self)  # Make dialog modal
        dialog.grab_set()

        # Instructions
        instructions = ttk.Label(dialog, text=(
            "To use the Lyrics fetching feature, you need a Genius API key.\n"
            "1. Go to https://genius.com/api-clients to create an account\n"
            "2. Create a new API client\n"
            "3. Copy your Client Access Token"
        ), wraplength=380)
        instructions.pack(pady=10, padx=10)

        # API key entry
        key_frame = ttk.Frame(dialog)
        key_frame.pack(fill=tk.X, padx=10, pady=5)

        key_label = ttk.Label(key_frame, text="API Key:")
        key_label.pack(side=tk.LEFT, padx=5)

        key_entry = ttk.Entry(key_frame, width=40)
        key_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Save button
        def save_key():
            key = key_entry.get().strip()
            if key:
                self.genius_api_key = key
                self.save_settings()
                messagebox.showinfo(
                    "Success", "Genius API key saved successfully!")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Please enter a valid API key")

        # Skip button
        def skip():
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        save_button = ttk.Button(button_frame, text="Save", command=save_key)
        save_button.pack(side=tk.LEFT, padx=5)

        skip_button = ttk.Button(button_frame, text="Skip", command=skip)
        skip_button.pack(side=tk.RIGHT, padx=5)
           
    def fetch_lyrics(self):
        """Fetch lyrics from Genius API for the currently selected song"""
        # Check if a song is selected
        if not hasattr(self, 'current_song_name'):
            messagebox.showerror("Error", "Please select a song first")
            return

        # Check if API key is set
        if not hasattr(self, 'genius_api_key') or not self.genius_api_key:
            self.request_genius_api_key()
            return

        # Try to parse artist and song title from directory name
        song_info = self.parse_song_info(self.current_song_name)

        # If we couldn't parse, ask user to enter manually
        if not song_info:
            song_info = self.ask_song_details()
            if not song_info:  # User canceled
                return

        artist, title = song_info
        self.search_genius_lyrics(artist, title)

    def parse_song_info(self, song_name):
        """Try to extract artist and title from directory name"""
        # Common patterns: "Artist - Title", "Artist_-_Title", "Artist__Title"
        patterns = [
            r"(.+)\s*-\s*(.+)",    # Artist - Title
            r"(.+)_-_(.+)",        # Artist_-_Title
            r"(.+)__(.+)",         # Artist__Title
            r"(.+)–(.+)",          # Artist–Title (en dash)
            r"(.+)—(.+)"           # Artist—Title (em dash)
        ]

        for pattern in patterns:
            match = re.match(pattern, song_name)
            if match:
                return match.group(1).strip(), match.group(2).strip()

        # If no patterns match, return None
        return None

    def ask_song_details(self):
        """Prompt user to enter artist and song title manually"""
        dialog = tk.Toplevel(self)
        dialog.title("Enter Song Details")
        dialog.transient(self)
        dialog.grab_set()

        result = [None, None]  # Will store [artist, title]

        # Artist entry
        artist_frame = ttk.Frame(dialog)
        artist_frame.pack(fill=tk.X, padx=10, pady=5)

        artist_label = ttk.Label(artist_frame, text="Artist:")
        artist_label.pack(side=tk.LEFT, padx=5)

        artist_entry = ttk.Entry(artist_frame, width=30)
        artist_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Title entry
        title_frame = ttk.Frame(dialog)
        title_frame.pack(fill=tk.X, padx=10, pady=5)

        title_label = ttk.Label(title_frame, text="Title:")
        title_label.pack(side=tk.LEFT, padx=5)

        title_entry = ttk.Entry(title_frame, width=30)
        title_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Pre-fill with directory name
        if hasattr(self, 'current_song_name'):
            title_entry.insert(0, self.current_song_name)

        def save_details():
            artist = artist_entry.get().strip()
            title = title_entry.get().strip()
            if artist and title:
                result[0] = artist
                result[1] = title
                dialog.destroy()
            else:
                messagebox.showerror(
                    "Error", "Please enter both artist and title")

        def cancel():
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        save_button = ttk.Button(
            button_frame, text="Search", command=save_details)
        save_button.pack(side=tk.LEFT, padx=5)

        cancel_button = ttk.Button(button_frame, text="Cancel", command=cancel)
        cancel_button.pack(side=tk.RIGHT, padx=5)

        # Wait for dialog to close
        self.wait_window(dialog)

        if result[0] and result[1]:
            return result
        return None

    def search_genius_lyrics(self, artist, title):
        """Search Genius API for lyrics"""
        search_term = f"{artist} {title}"
        encoded_term = quote(search_term)

        search_url = f"{self.genius_api_url}/search?q={encoded_term}"
        headers = {"Authorization": f"Bearer {self.genius_api_key}"}

        try:
            # Display loading indication
            self.lyrics_text.delete("1.0", tk.END)
            self.lyrics_text.insert("1.0", "Searching for lyrics...", "margin")
            self.lyrics_text.update()

            response = requests.get(search_url, headers=headers)
            if response.status_code != 200:
                messagebox.showerror(
                    "API Error", f"Error contacting Genius API: {response.status_code}")
                return

            data = response.json()
            hits = data.get("response", {}).get("hits", [])

            if not hits:
                messagebox.showinfo(
                    "Not Found", f"No lyrics found for {artist} - {title}")
                return

            # Find the best match
            best_match = None
            for hit in hits:
                hit_type = hit.get("type")
                result = hit.get("result", {})

                if hit_type == "song":
                    best_match = result
                    break

            if not best_match:
                messagebox.showinfo(
                    "Not Found", f"No song match found for {artist} - {title}")
                return

            # Get the song URL and extract lyrics
            song_url = best_match.get("url")
            if not song_url:
                messagebox.showerror("Error", "Couldn't find song URL")
                return

            self.extract_lyrics_from_url(song_url)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to search lyrics: {str(e)}")

    def extract_lyrics_from_url(self, url):
        """Extract lyrics from a Genius song page"""
        try:
            # Display loading message
            self.lyrics_text.delete("1.0", tk.END)
            self.lyrics_text.insert("1.0", "Extracting lyrics...", "margin")
            self.lyrics_text.update()

            # Make request to the song page
            response = requests.get(url)
            if response.status_code != 200:
                messagebox.showerror(
                    "Error", f"Failed to access lyrics page: {response.status_code}")
                return

            # Extract lyrics using regex
            html_content = response.text

            # Extract song metadata - improved patterns
            # Title pattern
            title_pattern = r'<title>(.+?) Lyrics \|'
            title_match = re.search(title_pattern, html_content)
            title = title_match.group(1) if title_match else "Unknown Title"

            # Add source link at the bottom
            lyrics_source = f"Source: {url}"

            # Prepare metadata header
            metadata = f"Title: {title}\n{lyrics_source}\n\n"

            # Rest of the function remains the same
            lyrics_pattern = r'<div class="Lyrics__Container-sc-\w+\s+">(.+?)</div>'
            lyrics_matches = re.findall(
                lyrics_pattern, html_content, re.DOTALL)

            if not lyrics_matches:
                # Try alternate pattern
                lyrics_pattern = r'<div data-lyrics-container="true"[^>]*>(.+?)</div>'
                lyrics_matches = re.findall(
                    lyrics_pattern, html_content, re.DOTALL)

            if not lyrics_matches:
                messagebox.showerror(
                    "Error", "Could not extract lyrics from the page")
                return

            # Combine all lyrics sections
            raw_lyrics = "".join(lyrics_matches)

            # Clean up HTML
            # Remove HTML tags
            clean_lyrics = re.sub(r'<[^>]+>', '\n', raw_lyrics)

            # Fix common issues
            # Remove excessive newlines
            clean_lyrics = re.sub(r'\n{3,}', '\n\n', clean_lyrics)
            # Replace &amp; with &
            clean_lyrics = re.sub(r'&amp;', '&', clean_lyrics)
            # Replace &quot; with "
            clean_lyrics = re.sub(r'&quot;', '"', clean_lyrics)
            # Replace &#x27; with apostrophe
            clean_lyrics = re.sub(r'&#x27;', "'", clean_lyrics)

            # Combine metadata, lyrics and footer
            full_content = metadata + clean_lyrics

            # Display lyrics in the text widget
            self.lyrics_text.delete("1.0", tk.END)
            self.lyrics_text.insert("1.0", full_content, "margin")

            # Offer to save the lyrics
            save = messagebox.askyesno(
                "Save Lyrics", "Save these lyrics to file?")
            if save:
                self.current_file = "lyrics.txt"
                self.save_text()

        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to extract lyrics: {str(e)}")

    def on_mouse_wheel(self, event):
        # Determine the direction and amount to scroll
        if event.num == 5 or event.delta < 0:  # Scroll down
            change = -0.01
        else:  # Scroll up
            change = 0.01

        # Get current value and calculate new value
        new_value = self.scroll_speed.get() + change

        # Ensure the new value is within bounds
        if new_value < 0.01:
            new_value = 0.01
        elif new_value > 1.0:
            new_value = 1.0

        # Set the new value
        self.scroll_speed.set(new_value)

        # If you have an update function, call it
        self.update_scroll_speed(new_value)

    def update_scroll_speed(self, value):
        """Updates the scroll speed while adjusting the slider."""
        if self.auto_scroll_active:
            self.auto_scroll_lyrics()  # Restart scrolling with new speed

    def auto_scroll_lyrics(self):
        if self.auto_scroll_active:
            speed = self.scroll_speed.get()  # Get speed from slider (0.1 to 5)

            # Convert speed into a smooth movement value
            scroll_amount = speed / 200  # Adjust for fine control
            # Scroll by a small fraction of the text height
            self.lyrics_text.yview_moveto(
                self.lyrics_text.yview()[0] + scroll_amount)

            # Adjust timing dynamically for smooth effect
            # 30ms for smoother motion
            self.after(3000, self.auto_scroll_lyrics)

    def toggle_auto_scroll(self):
        if self.auto_scroll_active:
            self.auto_scroll_active = False
            self.scroll_button.configure(text="Start Auto-Scroll")
        else:
            self.auto_scroll_active = True
            self.scroll_button.configure(text="Stop Auto-Scroll")
            self.auto_scroll_lyrics()  # Start scrolling

    def clear_search(self):
        """Reset search and restore full track list."""
        self.search_entry.delete(0, tk.END)

        # Clear the Treeview (correct way)
        for item in self.track_list.get_children():
            self.track_list.delete(item)

        # Restore all tracks
        for track in self.all_tracks:
            track_path = os.path.join(self.audio_dir, track)
            has_lyrics = "✔" if os.path.exists(
                os.path.join(track_path, "lyrics.txt")) else "✘"
            has_chords = "✔" if os.path.exists(
                os.path.join(track_path, "chords.txt")) else "✘"
            self.track_list.insert("", tk.END, values=(
                track, has_lyrics, has_chords))


    def toggle_lyrics_chords(self):
        if self.current_file == "lyrics.txt":
            self.current_file = "chords.txt"
            self.toggle_button.configure(text="Switch to Lyrics")
        else:
            self.current_file = "lyrics.txt"
            self.toggle_button.configure(text="Switch to Chords")

        self.load_text()  # Reload the text after switching

    def set_font_size(self):
        """Set the font size for lyrics, chords, and sections consistently."""
        font_config = (self.text_font, self.text_size)

        # Update the default font size for the lyrics text
        self.lyrics_text.configure(font=font_config)
        # Update font size for chords and sections to be identical to lyrics
        self.text_widget.tag_configure("chord", font=font_config, foreground="lime green")
        self.text_widget.tag_configure("section", font=font_config, foreground="yellow")
        
        bg_color = self.lyrics_text.cget("fg_color")

        # Convert the bg_color to a string and check for dark theme colors
        if "1D1E1E" in str(bg_color) or "black" in str(bg_color) or "#000000" in str(bg_color):
            lyrics_color = "#F5F5F5"
        else:
            lyrics_color = "black"

        self.text_widget.tag_configure("lyrics", font=font_config, foreground=lyrics_color)

    def increase_font_size(self):
        self.text_size += 2  # Increase font size
        self.set_font_size()

    def decrease_font_size(self):
        if self.text_size > 8:  # Prevent text from becoming too small
            self.text_size -= 2
            self.set_font_size()


    def load_text(self):
        self.lyrics_text.delete("1.0", tk.END)
        file_path = os.path.join(self.current_song_path, self.current_file)
        self.set_font_size()  # Ensure font size is consistent

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                lines = file.readlines()
                for line in lines:
                    # Check if the line is a chord line using regex
                    chord_line_pattern = r"^\s*([A-G][#b]?(m7|M7|m|dim|aug|sus2|sus4|add9|6|7|9|11|13|/|2| - )?(\s*\(x\))?(\s*\(4x\))?(\s*\(4x\))?(\s*\(hold\))?\s*)+$"
                    if re.match(chord_line_pattern, line):
                        self.text_widget.insert(tk.END, line, "chord")
                    elif any(keyword.lower() in line.strip().lower() for keyword in ["chorus", "intro", "outro", "verse", "adlib", "instrumental", "interlude", "refrain", "bridge", "coda"]):
                        self.text_widget.insert(tk.END, line, "section")
                    else:
                        self.lyrics_text.insert(tk.END, line, "lyrics")

    def save_text(self):
        if not hasattr(self, 'current_song_path') or not os.path.exists(self.current_song_path):
            messagebox.showerror("Error", "No song selected to save!")
            return

        text_content = self.lyrics_text.get("1.0", tk.END).strip()
        file_path = os.path.join(self.current_song_path, self.current_file)

        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(text_content)
            messagebox.showinfo(
                "Success", f"{self.current_file} saved successfully!")
            self.load_tracks()
            self.load_text()
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to save {self.current_file}: {e}")

        
    def on_close(self):
        self.save_column_widths()
        self.save_settings()
        self.destroy()

if __name__ == "__main__":
    app = AudioMixerApp()
    app.mainloop()