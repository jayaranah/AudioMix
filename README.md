# 🎵 AudioMix

**AudioMix** is a desktop application built with **Python,
CustomTkinter, and SoundDevice** that allows you to play, mix, and
control multiple audio stems for songs. It also provides features for
managing lyrics/chords, applying audio effects, and fetching lyrics via
the Genius API.

------------------------------------------------------------------------

## ✨ Features

-   🎚️ **Multi-stem playback** -- Load a song folder containing separate
    stems (vocals, drums, bass, etc.) and control each one
    individually.\
-   🔊 **Volume & mute controls** per stem.\
-   ⏯ **Play / Pause / Stop All** buttons for synchronized control.\
-   ⏩ **Seek bar with time tracking** to jump through the track.\
-   🎶 **Audio effects:**
    -   Reverb\
    -   Delay\
    -   3-band Equalizer (Low, Mid, High)\
-   🎨 **Theme switching** -- Multiple Windows styles via
    `pywinstyles`.\
-   📑 **Lyrics & Chords viewer** -- Auto-scroll, font size adjustment,
    save edits.\
-   🔎 **Lyrics fetcher** -- Fetch lyrics directly from Genius API.\
-   🔍 **Search bar** -- Quickly find songs in your library.\
-   💾 **Persistent settings** -- Audio directory, theme, and window
    layout are saved.

------------------------------------------------------------------------

## 📂 Project Structure

    AudioMix/
    │── AudioMix.py        # Main application
    │── settings.json      # Auto-generated app settings
    │── audio/             # Default folder for song directories
    │     ├── Song1/
    │     │     ├── vocals.wav
    │     │     ├── drums.wav
    │     │     ├── bass.wav
    │     │     ├── lyrics.txt
    │     │     └── chords.txt
    │     └── Song2/ ...

Each song should be placed inside its own folder under `audio/`. Stems
can be in `.mp3`, `.wav`, `.flac`, or `.ogg` format.

------------------------------------------------------------------------

## ⚙️ Requirements

-   Python **3.8+**
-   Dependencies (install via pip):

``` bash
pip install customtkinter pywinstyles sounddevice soundfile numpy requests
```

------------------------------------------------------------------------

## 🚀 Usage

1.  Clone the repository:

    ``` bash
    git clone https://github.com/yourusername/AudioMix.git
    cd AudioMix
    ```

2.  Run the app:

    ``` bash
    python AudioMix.py
    ```

3.  Select your **audio directory** (or use the default `audio/`
    folder).\

4.  Double-click a song from the list to load its stems.\

5.  Use the controls to play, mute, and adjust effects.\

6.  Switch to **Lyrics/Chords** panel for text editing or fetching
    lyrics.

------------------------------------------------------------------------

## 🔑 Genius API Setup (Optional for Lyrics Fetching)

1.  Go to [Genius API Clients](https://genius.com/api-clients).\
2.  Create a new API client and copy your **Client Access Token**.\
3.  Run the app → When prompted, paste your API key.\
4.  Now you can fetch lyrics automatically.

------------------------------------------------------------------------

## 🖼 Screenshots (Optional)
<img width="1333" height="900" alt="2025-08-18_001744" src="https://github.com/user-attachments/assets/eb5e32bc-b382-4937-991c-c7e3da290ba8" />


------------------------------------------------------------------------

## 📜 License

MIT License (or whichever license you prefer).
