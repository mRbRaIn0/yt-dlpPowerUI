# yt-dlp PowerUI

A simple dark-mode Windows GUI for `yt-dlp`.

The app lets you download videos or audio through a queue-based interface. It supports different formats, quality presets, optional time sections, cookie authentication, thumbnail previews and FFmpeg-based merging for multiple clips.

## Features

- Queue-based downloads
- Video and audio mode
- MP4, MKV and WEBM export
- MP3, M4A, WAV and FLAC export
- Quality presets such as Best, 4K, 1080p and 720p
- Optional time sections for cutting clips
- Multiple time sections with automatic FFmpeg merge
- Optional 9:16 vertical crop
- Cookie support via browser or cookie file
- Custom output folder
- Thumbnail preview
- Failed download overview with retry option

## Requirements

- Windows
- Python 3.10 or newer
- yt-dlp
- FFmpeg
- Python packages:
  - customtkinter
  - pillow

## Installation

Clone the repository:

```bash
git clone https://github.com/USERNAME/yt-dlp-powerui.git
cd yt-dlp-powerui
