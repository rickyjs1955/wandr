"""
FFmpeg service for video processing.

Handles:
- Proxy video generation (480p, 10fps)
- Video metadata extraction (FFprobe)
- Thumbnail generation
"""
import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import timedelta

import ffmpeg

logger = logging.getLogger(__name__)


class FFmpegService:
    """Service for FFmpeg video processing operations."""

    def __init__(self):
        """Initialize FFmpeg service."""
        # Verify FFmpeg is installed
        try:
            ffmpeg.probe("dummy", cmd="ffmpeg")
        except ffmpeg.Error:
            pass  # Expected for dummy file
        except FileNotFoundError:
            logger.error("FFmpeg not found. Please install FFmpeg.")
            raise RuntimeError(
                "FFmpeg is not installed. Install with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
            )

    def extract_metadata(self, input_path: str) -> Dict[str, Any]:
        """
        Extract video metadata using FFprobe.

        Args:
            input_path: Path to video file

        Returns:
            Dict with metadata:
            - width: int
            - height: int
            - fps: float
            - duration_seconds: float
            - codec: str
            - bitrate: int (bps)
            - file_size_bytes: int

        Raises:
            FFmpegError: If FFprobe fails
            FileNotFoundError: If input file doesn't exist
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Video file not found: {input_path}")

        try:
            logger.info(f"Extracting metadata from: {input_path}")

            # Probe video file
            probe = ffmpeg.probe(input_path)

            # Get video stream
            video_stream = next(
                (s for s in probe["streams"] if s["codec_type"] == "video"), None
            )
            if not video_stream:
                raise ValueError("No video stream found in file")

            # Extract metadata
            metadata = {
                "width": int(video_stream["width"]),
                "height": int(video_stream["height"]),
                "codec": video_stream["codec_name"],
                "duration_seconds": float(probe["format"].get("duration", 0)),
                "bitrate": int(probe["format"].get("bit_rate", 0)),
                "file_size_bytes": int(probe["format"].get("size", 0)),
            }

            # Calculate FPS (handle variable frame rate)
            fps_str = video_stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, denom = fps_str.split("/")
                metadata["fps"] = float(num) / float(denom)
            else:
                metadata["fps"] = float(fps_str)

            logger.info(
                f"Metadata extracted: {metadata['width']}x{metadata['height']} @ {metadata['fps']:.2f}fps, "
                f"{metadata['duration_seconds']:.1f}s, codec={metadata['codec']}"
            )

            return metadata

        except ffmpeg.Error as e:
            logger.error(f"FFprobe error: {e.stderr.decode() if e.stderr else str(e)}")
            raise

    def generate_proxy(
        self,
        input_path: str,
        output_path: str,
        target_height: int = 480,
        target_fps: int = 10,
        preset: str = "medium",
        crf: int = 28,
    ) -> Dict[str, Any]:
        """
        Generate proxy video (low-res, low-fps for streaming).

        Args:
            input_path: Path to original video
            output_path: Path for proxy video
            target_height: Target height in pixels (default: 480)
            target_fps: Target frame rate (default: 10)
            preset: FFmpeg preset (ultrafast, fast, medium, slow) - default: medium
            crf: Constant Rate Factor for quality (18-28, lower=better) - default: 28

        Returns:
            Dict with proxy metadata:
            - width: int
            - height: int
            - fps: float
            - duration_seconds: float
            - file_size_bytes: int
            - codec: str

        Raises:
            FFmpegError: If encoding fails
            FileNotFoundError: If input file doesn't exist
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input video not found: {input_path}")

        try:
            logger.info(
                f"Generating proxy: {input_path} -> {output_path} "
                f"({target_height}p @ {target_fps}fps)"
            )

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Detect if input has audio stream (CCTV footage often doesn't)
            probe = ffmpeg.probe(input_path)
            has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
            logger.info(f"Input has audio stream: {has_audio}")

            # Build FFmpeg command
            stream = ffmpeg.input(input_path)

            # Scale video: maintain aspect ratio, set height
            stream = ffmpeg.filter(stream, "scale", -2, target_height)

            # Set frame rate
            stream = ffmpeg.filter(stream, "fps", fps=target_fps)

            # Build output parameters
            output_params = {
                "vcodec": "libx264",  # H.264 codec
                "preset": preset,  # Encoding speed/quality trade-off
                "crf": crf,  # Quality (18=high, 28=medium)
                "movflags": "faststart",  # Enable streaming
                "pix_fmt": "yuv420p",  # Compatibility
            }

            # Only add audio encoding if input has audio stream
            if has_audio:
                output_params["acodec"] = "aac"
                output_params["audio_bitrate"] = "64k"
            else:
                # Explicitly disable audio to prevent FFmpeg errors
                output_params["an"] = None

            # Output with H.264 codec
            stream = ffmpeg.output(stream, output_path, **output_params)

            # Run FFmpeg (overwrite output if exists)
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)

            logger.info(f"Proxy generated successfully: {output_path}")

            # Extract metadata from generated proxy
            proxy_metadata = self.extract_metadata(output_path)

            return proxy_metadata

        except ffmpeg.Error as e:
            logger.error(f"FFmpeg encoding error: {e.stderr.decode() if e.stderr else str(e)}")
            # Clean up partial output file
            if os.path.exists(output_path):
                os.remove(output_path)
            raise

    def generate_thumbnail(
        self,
        input_path: str,
        output_path: str,
        timestamp_seconds: float = 5.0,
        width: int = 320,
    ) -> Dict[str, Any]:
        """
        Generate thumbnail image from video.

        Args:
            input_path: Path to video file
            output_path: Path for thumbnail image (must end in .jpg or .png)
            timestamp_seconds: Which timestamp to capture (default: 5.0)
            width: Thumbnail width in pixels (default: 320, height auto-scaled)

        Returns:
            Dict with thumbnail info:
            - width: int
            - height: int
            - file_size_bytes: int
            - timestamp_seconds: float

        Raises:
            FFmpegError: If thumbnail generation fails
            FileNotFoundError: If input file doesn't exist
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input video not found: {input_path}")

        try:
            logger.info(
                f"Generating thumbnail: {input_path} -> {output_path} "
                f"(t={timestamp_seconds}s, width={width}px)"
            )

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Build FFmpeg command
            stream = ffmpeg.input(input_path, ss=timestamp_seconds)

            # Scale to target width (maintain aspect ratio)
            stream = ffmpeg.filter(stream, "scale", width, -1)

            # Output single frame
            stream = ffmpeg.output(
                stream,
                output_path,
                vframes=1,  # Single frame
                format="image2",
                qscale=2,  # High quality JPEG (1-31, lower=better)
            )

            # Run FFmpeg
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)

            logger.info(f"Thumbnail generated successfully: {output_path}")

            # Get file size
            file_size = os.path.getsize(output_path)

            # Get dimensions using FFprobe
            probe = ffmpeg.probe(output_path)
            video_stream = probe["streams"][0]

            return {
                "width": int(video_stream["width"]),
                "height": int(video_stream["height"]),
                "file_size_bytes": file_size,
                "timestamp_seconds": timestamp_seconds,
            }

        except ffmpeg.Error as e:
            logger.error(f"FFmpeg thumbnail error: {e.stderr.decode() if e.stderr else str(e)}")
            # Clean up partial output file
            if os.path.exists(output_path):
                os.remove(output_path)
            raise

    def validate_video(self, input_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that file is a valid video.

        Args:
            input_path: Path to video file

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if video is valid
            - error_message: None if valid, error string if invalid
        """
        try:
            if not os.path.exists(input_path):
                return False, "File does not exist"

            # Try to probe the file
            probe = ffmpeg.probe(input_path)

            # Check for video stream
            video_stream = next(
                (s for s in probe["streams"] if s["codec_type"] == "video"), None
            )
            if not video_stream:
                return False, "No video stream found"

            # Check duration
            duration = float(probe["format"].get("duration", 0))
            if duration <= 0:
                return False, "Invalid duration"

            return True, None

        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            return False, f"FFprobe error: {error_msg}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"


# Singleton instance
_ffmpeg_service: Optional[FFmpegService] = None


def get_ffmpeg_service() -> FFmpegService:
    """Get or create FFmpeg service singleton."""
    global _ffmpeg_service
    if _ffmpeg_service is None:
        _ffmpeg_service = FFmpegService()
    return _ffmpeg_service
