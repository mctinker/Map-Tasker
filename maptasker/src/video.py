#! /usr/bin/env python3
"""
Process videos from YouTube and Dropbox/MP4s
"""

import contextlib
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import traceback
from io import BytesIO
from tkinter import TclError

import customtkinter as ctk
import requests
import yt_dlp
from PIL import Image, ImageTk

from maptasker.src.diagutil import width_and_height_calculator_in_pixel
from maptasker.src.error import rutroh_error
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems

# We will force a 480x480 resolution video.
TARGET_WIDTH = "640"
TARGET_HEIGHT = "640"


def handle_image(self: ctk, msg: str, start_idx: str) -> None:
    """
    Extracts an image URL from an HTML 'href' attribute and displays the image.

    This function searches for a URL embedded within an 'href' attribute
    in the provided message string. If a URL is found, it calls a helper
    function to display the image in a CustomTkinter text view widget.
    If no URL is found, it rutroh_errors an error message to the console.

    Args:
        self (ctk): The CustomTkinter object instance, which contains the
                    text view widget.
        msg (str): The string message containing the HTML-like 'href' attribute.
        start_idx (str): The starting index for the image display in the
                         text view widget (e.g., "end").
    """
    # Get the url for the image
    # This pattern looks for "href=" followed by a quote, then captures everything
    # that's not a quote, until it finds the closing quote.
    # (?:...) is a non-capturing group.
    # (.*?) is a non-greedy match for any character.
    pattern = r'href="(.*?)"'
    # Search for the pattern in the string

    match = re.search(pattern, msg)

    # Check if a match was found
    if match:
        # The URL is in the first captured group (index 1)
        url = match.group(1)
        _show_media(self, self.textview_textbox, url, start_idx)
    else:
        rutroh_error(f"No URL found in the href attribute: {msg}")


def _handle_video_click(self: object, event: object, media_url: str) -> None:  # noqa: ARG001
    """Callback function for the video link click event."""

    # Launch the VideoEmbedder. The self.root must be the main application window.
    # The VideoEmbedder instance is stored here, though it runs itself.
    _ = VideoEmbedder(self.root, media_url)


def _embed_video_placeholder(text_widget: ctk.CTkTextbox, media_url: str, index: str) -> None:
    """
    Displays a clickable video link in the textbox.
    """
    from maptasker.src.guiutils import get_appropriate_color  # noqa: PLC0415  Avoid circular import

    mygui = text_widget.master.master.master

    # Determine if we need ffmpeg (required for youtube), and if so, dp we have it in our runpath
    # We only want to do this once.  BUt if windows, then we don't embed videos at all.
    if PrimeItems.windows_system:
        rutroh_error("Note: On Windows, video hotlinks are not supported")
        have_ffmpeg = False
    elif mygui.checked_ffmpeg:
        have_ffmpeg = mygui.have_ffmpeg

    else:
        have_ffmpeg = True
        # Use the combination of both 'shutil' and 'subprocess' for a robust check
        is_present = check_ffmpeg_shutil()

        if is_present:
            # Only run the subprocess check if we know it's *in* the PATH
            have_ffmpeg = check_ffmpeg_subprocess()
        else:
            have_ffmpeg = False
            rutroh_error("\nSkipping subprocess check as executable was not found by shutil.which().")

            # Save our settings
            mygui.have_ffmpeg = have_ffmpeg
            mygui.checked_ffmpeg = True

    link_text = f"[▶️ VIDEO: {media_url}]"

    char_position = index.split(".")[1]

    # 0. Insert a blank line
    if char_position == "0":
        text_widget.insert("end", "\n")

    # 1. Set unique tag and insert the text
    tag_id = f"video_link-{index}"
    text_widget.insert(index, link_text, tag_id)

    # Only do the following if it is youtube and we have ffmpeg in our path, or it isn't youtube.
    if have_ffmpeg:
        # 2. Define the 'video_link' tag properties (usually done once at startup)
        text_widget.tag_config(
            tag_id,
            foreground=get_appropriate_color(text_widget.master.master.master, "blue"),
            underline=True,
        )

        # 3. Bind a click event to the tag
        # The lambda function passes the URL when the tagged text is clicked
        callback = lambda e: _handle_video_click(text_widget.master, e, media_url)
        text_widget.tag_bind(tag_id, "<Button-1>", callback)

        # 4. Store the tag reference (important if you clear and re-insert text)
        if not hasattr(text_widget, "video_tag_bindings"):
            text_widget.video_tag_bindings = {}
        text_widget.video_tag_bindings[media_url] = callback

    # 5. Insert a blank line
    if char_position == "0":
        text_widget.insert("end", "\n")


def check_ffmpeg_shutil() -> bool:
    """
    Method 1: Uses shutil.which() to check if 'ffmpeg' is in the system PATH.
    This is generally the fastest and most direct check.
    """
    rutroh_error("--- Method 1: Using shutil.which() ---")
    if shutil.which("ffmpeg"):
        rutroh_error("✅ FFmpeg executable found in PATH.")
        return True
    rutroh_error("❌ FFmpeg executable NOT found in PATH.")
    return False


def check_ffmpeg_subprocess() -> bool:
    """
    Method 2: Uses subprocess.run() to execute 'ffmpeg -version' and check
    the return code. This confirms the executable is not just present but also runs.
    """

    rutroh_error("\n--- Method 2: Using subprocess.run() ---")
    try:
        # Execute the command.
        # capture_output=True prevents output pollution.
        # check=True raises a CalledProcessError if the return code is non-zero.
        result = subprocess.run(
            ["ffmpeg", "-version"],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,  # Decode output as text
        )

        # If no exception was raised, the command ran successfully.
        rutroh_error("✅ FFmpeg executable found and ran successfully.")

        # Optionally, rutroh_error the version information
        first_line = result.stdout.split("\n")[0]
        rutroh_error(f"   Version Info: {first_line}")
        return True  # noqa: TRY300

    except subprocess.CalledProcessError:
        # This occurs if the 'ffmpeg' command itself failed to run (e.g., bad arguments)
        # but not typically if the file is missing.
        rutroh_error("❌ FFmpeg command failed to run correctly (CalledProcessError).")
        return False

    except FileNotFoundError:
        # This is the most common error if the 'ffmpeg' executable isn't found.
        rutroh_error("❌ FFmpeg executable NOT found (FileNotFoundError).")
        rutroh_error("   Please ensure FFmpeg is installed and added to your system's PATH.")
        return False
    except Exception as e:  # noqa: BLE001
        rutroh_error(f"❌ An unexpected error occurred: {e}")
        return False


def _show_media(self: object, text_widget: ctk.CTkTextbox, media_url: str, index: str) -> None:  # noqa: ARG001
    """
    Downloads media (image or video) from a URL and displays it in a CTkTextbox widget.

    (Same as before, but with the updated video handler call)
    """

    # Check if the URL indicates a video file
    is_video = any(ext in media_url for ext in ["mp4", "youtu.", "youtube."])

    if is_video:
        # --- VIDEO HANDLING ---
        _embed_video_placeholder(text_widget, media_url, index)
        return

    # --- IMAGE HANDLING (remains the same) ---
    try:
        # 1. Download the image
        response = requests.get(media_url, timeout=5, headers={"User-agent": "your bot 0.1"})
        if response.status_code == 429:
            text_widget.insert(index, "[!!! Image server too many requests !!!]", "error")
            return

        response.raise_for_status()

        # 2. Open the image using Pillow.
        img_data = BytesIO(response.content)

        # This is where image opening would fail for video formats,
        # but the 'is_video' check above now prevents this.
        pil_image = Image.open(img_data)

        # 3. Use thumbnail() to resize while preserving the aspect ratio.
        pil_image.thumbnail((300, 200), Image.LANCZOS)

        # 4. Create a standard Tkinter PhotoImage from the Pillow image.
        tk_image = ImageTk.PhotoImage(pil_image)

        text_widget.insert("end", "\n")

        # 5. Embed the image in the internal Tkinter Text widget.
        text_widget._textbox.image_create(index, image=tk_image)  # noqa: SLF001

        # 6. Store a reference to prevent garbage collection.
        if not hasattr(text_widget, "image_references"):
            text_widget.image_references = []
        text_widget.image_references.append(tk_image)

        text_widget.insert("end", "\n")

    except requests.exceptions.RequestException as e:
        rutroh_error(f"Failed to download image: {e}")
    except Exception as e:  # noqa: BLE001
        rutroh_error(f"guiutil2 _show_media: An error occurred for image URL: {media_url}. Error: {e}")


# --- VIDEO EMBEDDER CLASS ---
class VideoEmbedder:
    """
    Manages video playback by creating a new Toplevel window to display
    a video stream using the 'cv3' (OpenCV) library.

    Video processing and frame updates run in a separate thread to prevent
    the main CustomTkinter application from freezing.

    It supports direct video URLs (e.g., .mp4) and automatically fetches
    stream URLs for YouTube links using the 'pytube' library.

    :param master_root: The main application's root window (CTk or Tk).
                        The Toplevel window will be attached to this master.
    :type master_root: ctk.CTk or tk.Tk
    :param media_url: The URL of the video file or YouTube link to be played.
    :type media_url: str

    :ivar media_url: The original URL of the media.
    :ivar is_playing: A boolean flag controlling the video playback loop.
    :ivar cap: The video capture object from the cv3 library.
    :ivar thread: The thread used to handle the video loading and loop.
    :ivar width: The width of the video display label (determined by the video file).
    :ivar height: The height of the video display label (determined by the video file).
    :ivar window: The Toplevel window instance used for displaying the video.
    :ivar video_label: The CTkLabel widget inside the window that displays the current frame.
    :ivar delay: The time delay (in seconds) between frames, calculated from the video's FPS.
    :ivar tk_image: Reference to the current Tkinter PhotoImage to prevent garbage collection.
    """

    def __init__(self, master_root: ctk.CTk, media_url: str) -> None:
        """
        Initializes the video player window.
        """
        self.mygui = master_root.master
        self.media_url = media_url
        self.is_playing = True
        self.cap = None
        self.thread = None
        self.width = 640
        self.height = 480
        vid_win = "video_window"

        # Create new top-level window if it doesn't already exist
        if getattr(self.mygui, vid_win) is None or not getattr(self.mygui, vid_win).winfo_exists():
            self.window = ctk.CTkToplevel(master_root)
            self.window.title("Video Player")
            self.window.protocol("WM_DELETE_WINDOW", self.stop_playback)

            self.video_textbox = ctk.CTkTextbox(
                master=self.window,
                width=self.width,
                height=self.height,
                font=("Courier", 14),
            )
            # Set the window based on the Map view window, with width=500 and height=500
            self.window.geometry(self.convert_geometry(self.mygui.map_window_position, "500", "500"))
            setattr(self.mygui, vid_win, self.video_textbox)
        else:
            # The window already exists.  Reuse it.
            self.video_textbox = self.mygui.video_window
            self.window = self.video_textbox.master
            self.mygui.mapview_window.lower()
            self.video_textbox.focus()
            self.window.focus()

        self.video_textbox.insert("1.0", "Fetching the video.   Please stand by...")
        self.video_textbox.pack(padx=10, pady=10)
        # Start the video player as a separate thread
        self.thread = threading.Thread(target=self._load_and_play_video, daemon=True)
        self.thread.start()

    def _get_stream_source(self) -> str | None:
        """Determines the actual stream source, handling YouTube and Dropbox links."""
        media_url = self.media_url

        # If it's a local file, return it immediately
        if os.path.exists(media_url):
            return media_url

        # 1. Handle YouTube links using yt-dlp
        if any(ext in media_url for ext in ["youtu.", "youtube."]):
            return self.get_yt_dlp_stream_url(media_url)  # <-- Call the new function

        # 2. Handle Dropbox direct links.
        if media_url.endswith("?dl=0"):
            return media_url[:-1] + "1"

        return media_url

    def _load_and_play_video(self) -> None:
        """Loads the video capture and starts the display loop."""
        # Only import cv3 if not on Windows.
        if not PrimeItems.windows_system:
            import cv3  # noqa: PLC0415

        stream_url = self._get_stream_source()

        # Bail out if this is a Youtube video
        if "youtu.be" in self.media_url or "youtube.com" in self.media_url:
            # self.window.destroy()
            return

        if not stream_url:
            self._display_message("Failed to get video stream URL.")
            return

        # Grab the MP4 video
        try:
            self.cap = cv3.VideoCapture(stream_url)
        except OSError:
            self._display_message("Error trying to read the video!")
            return

        if not self.cap.isOpened():
            self._display_message("Could not open video stream.")
            return

        # Get width and height
        self.width = self.cap.width
        self.height = self.cap.height

        # Reconfigure the window for the width and height
        if ".mp4" in self.media_url:
            self.configure_window({}, self.width, self.height, url=stream_url)

        # Get our current window width and height
        temp = self.mygui.map_window_position.split("x")

        # If we have a huge video window, max it out to our main window dimensions.
        height = temp[1].split("+")[0]
        if int(self.width) > int(temp[0]) or int(self.height) > int(height):
            self.width = temp[0]
            self.height = height

        # Frames per second and delay
        fps = self.cap.fps
        self.delay = 1 / fps

        self.window.after(0, lambda: self.video_textbox.configure(width=self.width, height=self.height))

        self._update_frame()

    def _update_frame(self) -> None:
        """Reads a frames from MP4 video and updates the Tkinter Label."""
        if not self.is_playing or not self.cap:
            return

        try:
            frame = self.cap.read()

            pil_image = Image.fromarray(frame)

            # # 1. Convert BGR frame (OpenCV default) to RGB
            # cv3_image_rgb = cv3.color_spaces.bgr2rgb(frame)
            # # 2. Convert to PIL Image
            # pil_image = Image.fromarray(cv3_image_rgb)

            # 3. Convert to Tkinter PhotoImage
            self.tk_image = ImageTk.PhotoImage(pil_image)

            # 4. Update the label in the main thread.  Use _textbox to access tk rather than Ctk
            self.video_textbox._textbox.image_create("1.0", image=self.tk_image)  # noqa: SLF001

            # Continue looping through video frames
            self.window.after(int(self.delay * 1000), self._update_frame)
        except StopIteration:
            # --- Drop here if we are done ---
            # self.cap.set(cv3.CAP_PROP_POS_FRAMES, 0)
            # self._display_message("Video ended.")
            self.window.destroy()
            return

    def _display_message(self, message: str) -> None:
        """Displays an error message in the video window."""
        with contextlib.suppress(TclError):
            self.video_textbox.delete("1.0", "end")
            self.window.after(0, lambda: self.video_textbox.insert("1.0", message))

    def stop_playback(self) -> None:
        """Cleans up resources and closes the window."""
        self.is_playing = False
        if self.cap:
            self.cap.release()
        self.window.destroy()

    def get_yt_dlp_stream_url(self, url: str) -> str | None:
        """
        Fetches the direct stream (Youtube) URL for a video using the yt-dlp library.

        :param url: The YouTube URL.
        :returns: The direct stream URL (usually the highest quality available), or None on failure.
        :rtype: str | None
        """
        text = """Video keyboard shortcuts...

| Key           | Action                             |
| ------------- | ---------------------------------- |
|   Space / p   | Pause / resume                     |
|   q / ESC     | Quit                               |
|   ← / →       | Seek backward / forward 10 seconds |
|   ↓ / ↑       | Seek 1 minute backward / forward   |
|   m           | Mute                               |
|   0–9         | Seek to 0–90% of the video         |
"""  # noqa: RUF001
        # Download and scale the Youtube video and audio.
        final_file = self.download_and_scale_yt_video(url, TARGET_WIDTH, TARGET_HEIGHT)

        # Show the video playback controls.
        self._display_message(text)

        # Play the video
        self.play_with_ffplay(final_file)

        return final_file

    def download_and_scale_yt_video(
        self,
        url: str,
        target_width: int,
        target_height: int,
    ) -> str | None:
        """
        Downloads a specific YouTube stream (itag) and scales it to target dimensions.

        :param url: YouTube URL
        :param target_itag: The itag of the desired stream
        :param target_width: Target width in pixels
        :param target_height: Target height in pixels
        :return: Path to the final scaled MP4 file, or None on failure
        """

        class MyLogger:
            # self points to the class VideoEmbedder, and there is no reference outside of this logger.
            # Therefore, we have to use 'print' statements to show messages in the video window.
            def debug(self, msg: str) -> None:
                pass

            def info(self, msg: str) -> None:
                pass

            def warning(self, msg: str) -> None:
                # print(
                #     "Warning: There is a problem with the video.  Run in 'Debug' mode to capture the error.  Video may not play correctly.",
                # )
                rutroh_error(f"yt-dlp warning: {msg}")

            def error(self, msg: str) -> None:
                print(f"Error: {msg}.  Video will not play.")
                rutroh_error(f"yt-dlp error: {msg}")

        self._display_message("Processing YouTube video.  Please wait...")

        # Start the Youtube download...
        try:
            # Step 1: Extract metadata without downloading
            ydl_opts = {"quiet": True, "skip_download": True, "logger": MyLogger()}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                formats = info_dict.get("formats", [])

            # Step 2: Find the video that best matches our target width and height.
            mp4_videos = []
            for f in formats:
                language = f.get("language")
                if f["ext"] == "mp4" and (language is None or "en" in language):
                    temp = f["resolution"].split("x")
                    width = int(temp[0])
                    height = int(temp[1])
                    mp4_videos.append((width, height, f["format_id"]))

            if not mp4_videos:
                rutroh_error(f"Itag for '{url}' mp4 not found for this video")
                self._display_message("Error: No MP4 video formats found for this YouTube video.")
                for f in formats:
                    rutroh_error(f"Video format:{f}")
                return None
            # Calculate the closest width/height as measured by Euclidean distance in width/height space.
            t_width = int(target_width)
            t_height = int(target_height)
            our_mp4 = min(mp4_videos, key=lambda t: (t[0] - t_width) ** 2 + (t[1] - t_height) ** 2)
            video_itag = our_mp4[2]
            target_width = our_mp4[0]
            target_height = our_mp4[1]

            # Step 3: Prepare output filename
            title = info_dict.get("title", "video")
            temp_filename = f"{title}_{target_width}p.temp.%(ext)s"

            # Step 3.5: Reconfigure our video player (message) window
            self.configure_window(info_dict, target_width, target_height)

            # Step 4: Download the video with the specific itag with scaling
            ydl_opts = {
                "quiet": True,
                "format": str(video_itag),
                # "format": f"{video_itag}+{audio_itag}",  # <<< VIDEO + AUDIO!
                "outtmpl": temp_filename,
                "overwrites": True,
                "logger": MyLogger(),
                "postprocessors": [
                    {
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "mp4",
                    },
                ],
                "postprocessor_args": [
                    "-vf",
                    f"scale={target_width}:{target_height}",
                    "-crf",
                    "30",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    # "copy",
                    "aac",
                ],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)

            # Step 5: Get the postprocessed filename
            downloads = info_dict.get("requested_downloads", [])
            if downloads:
                final_file = downloads[0]["filepath"]
            else:
                final_file = ydl.prepare_filename(info_dict).replace(".webm", ".mp4")

            # Step 5.5: Setup the window to the proper dimension with the title
            # self.configure_window(info_dict, target_width, target_height)

            # Step 6: Rename temp file to remove .temp if present
            if final_file.endswith(".temp.mp4"):
                final_file_renamed = final_file.replace(".temp.mp4", ".mp4")
                os.replace(final_file, final_file_renamed)
                final_file = final_file_renamed

            # Let the user know (only for Youtube videos)
            text = translate_string("Video saved as")
            self.mygui.display_message_box(f"{text} '{final_file}'", "turquoise")

            return final_file  # noqa: TRY300

        except Exception as e:  # noqa: BLE001
            # 1. Get the traceback object
            _exc_type, _exc_obj, exc_tb = sys.exc_info()

            # 2. Extract the line number from the traceback object
            # exc_tb.tb_lineno gives the line number *in the traceback object's frame*
            # However, to get the last line where the error occurred,
            # we should walk the traceback stack to the last frame.

            # Standard practice is to get the last frame in the traceback
            f = traceback.extract_tb(exc_tb)[-1]

            # The line number from the traceback object
            line_number = f.lineno

            # The name of the file
            file_name = f.filename

            # The function name
            func_name = f.name
            print(
                f"Error downloading/scaling video! line_number:{line_number}, file_name:{file_name}, function:{func_name}, Error:{e}",
            )
            return None

    def convert_geometry(self, geometry_string: str, new_w: str, new_h: str) -> str:
        """
        Converts a Tkinter geometry string to a new one with specified
        width and height, preserving the original screen position.

        Args:
            geometry_string (str): The original geometry string (e.g., '1979x1264+475+52').
            new_w (str): The new width.
            new_h (str): The new height.

        Returns:
            str: The new geometry string (e.g., '480x480+475+52').
        """

        # The geometry string format is: <width>x<height>+<x_offset>+<y_offset>

        # 1. Find the position substring (+x_offset+y_offset)
        # The re.search finds the first '+' and captures everything from that point on.
        match = re.search(r"(\+\d+\+\d+)", geometry_string)

        if match:
            # Get the position part, e.g., '+475+52'
            position_string = match.group(0)
        else:
            # Handle the case where the position offsets are not included
            rutroh_error("Warning: Position offsets not found. Returning centered geometry.")
            position_string = ""

        # 2. Construct the new geometry string
        return f"{new_w}x{new_h}{position_string}"

    def normalize_dimensions(
        self,
        original_width: int,
        original_height: int,
        target_size: int = 480,
    ) -> tuple[int, int]:
        """
        Normalizes a set of dimensions to fit within a square boundary (e.g., 480x480)
        while preserving the original aspect ratio.

        Args:
            original_width (int): The original width (from info_dict.width).
            original_height (int): The original height (from info_dict.height).
            target_size (int): The size of the square bounding box (e.g., 480).

        Returns:
            tuple[int, int]: The new scaled width and height as integers.
        """

        # 1. Handle edge cases (shouldn't happen with valid video dimensions, but good practice)
        if original_width <= 0 or original_height <= 0:
            return 0, 0

        # 2. Calculate the scaling factors for width and height
        # How much do we need to scale the width to hit the target?
        scale_factor_w = target_size / original_width

        # How much do we need to scale the height to hit the target?
        scale_factor_h = target_size / original_height

        # 3. Choose the most restrictive (smallest) factor
        # This ensures BOTH new dimensions are less than or equal to the target size.
        # final_scale_factor = min(scale_factor_w, scale_factor_h)

        # 4. Apply the factor and round the results
        # We use round() to get the nearest integer dimensions.
        new_width = round(original_width * scale_factor_w)
        new_height = round(original_height * scale_factor_h)

        return new_width + 50, new_height + 50

    def configure_window(self, info_dict: dict, width: int, height: int, url: str | None = None) -> None:
        """
        Reconfigures the video window's title and dimensions based on
        the video's metadata and resolution.

        The window dimensions are calculated to fit the video aspect ratio while
        ensuring the width is large enough to display the full video title. The
        minimum window size is constrained to 500x500 pixels.

        Parameters
        ----------
        info_dict : dict
            A dictionary containing video metadata, typically returned by
            `yt-dlp.extract_info()`. Requires 'duration_string' and 'fulltitle' keys.
        width : int
            The width (in pixels) of the video file that has been downloaded
            (after any scaling post-processing).
        height : int
            The height (in pixels) of the video file that has been downloaded
            (after any scaling post-processing).

        Returns
        -------
        None

        Notes
        -----
        Uses the helper methods `width_and_height_calculator_in_pixel`,
        `normalize_dimensions`, and `convert_geometry` for size calculations
        and window dimension setting.
        """
        # Formulate the full title with video details
        duration = info_dict.get("duration_string", "N/A")
        title = info_dict.get("fulltitle", "")
        if url is not None and not title:
            title = url
        full_title = f"Video Player{' ' * 10}{title}{' ' * 10}Duration:{duration}"
        full_title_in_pixels = width_and_height_calculator_in_pixel(full_title, "Courier", 14)[0]
        self.window.title(full_title)

        # Expand our window if the full title is greater than our default window (500 pixelsx500 pixels).
        if full_title_in_pixels > width:
            # Take the original window size and normalize it to our new dimensions.
            normalized_width, normalized_height = self.normalize_dimensions(
                width,
                height,
                full_title_in_pixels,
            )
        else:
            normalized_width = width + 10
            normalized_height = height + 10

        # Reconfigure the window dimensions/size.
        rutroh_error(
            f"Window resizing.  Full title in pixels:{full_title_in_pixels} Normalized width/height:{normalized_width}x{height} Video width/height:{info_dict.get('width')}{info_dict.get('height')}",
        )
        self.window.geometry(
            self.convert_geometry(self.window.wm_geometry(), normalized_width, normalized_height),
        )

    def play_with_ffplay(self, path: str) -> None:
        """
        Plays a video (with audio) using ffplay in an external window.
        """
        # -autoexit: ffplay closes automatically at end of playback
        cmd = f'ffplay -autoexit -loglevel quiet "{path}"'
        p = subprocess.Popen(shlex.split(cmd))  # noqa: S603

        # Wait for it to finish.  Delete our video window when done.
        while True:
            if p.poll() is not None:
                self.window.destroy()
                break
            time.sleep(0.1)
