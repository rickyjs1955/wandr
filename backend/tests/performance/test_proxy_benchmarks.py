"""
Performance Benchmark Tests for Video Processing Pipeline

Tests processing speed and resource usage for proxy generation.

Target Performance:
- 10-minute 1080p/30fps clip: <20 minutes processing time (2x real-time)
- 30-minute 1080p/30fps clip: <1 hour processing time (2x real-time)
- Memory usage: <4GB per worker
- Proxy file size: 10-15% of original

Run with: pytest backend/tests/performance/test_proxy_benchmarks.py -v --benchmark
"""

import pytest
import time
import psutil
import os
from pathlib import Path
from datetime import datetime

from app.services.ffmpeg_service import get_ffmpeg_service


@pytest.fixture
def generate_test_video():
    """
    Generate test videos of various durations using FFmpeg.

    Returns a function that creates videos on demand.
    """
    def _generate(duration_seconds, width=1920, height=1080, fps=30, output_path=None):
        """Generate test video with specified parameters."""
        import subprocess

        if output_path is None:
            output_path = f"/tmp/test_video_{duration_seconds}s_{width}x{height}_{fps}fps.mp4"

        # Check if video already exists (cache for repeated tests)
        if os.path.exists(output_path):
            return output_path

        # Generate test video with color bars and audio
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"testsrc=duration={duration_seconds}:size={width}x{height}:rate={fps}",
            "-f", "lavfi",
            "-i", f"sine=frequency=1000:duration={duration_seconds}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            output_path
        ]

        try:
            print(f"Generating test video: {duration_seconds}s, {width}x{height}, {fps}fps...")
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"Test video generated: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            pytest.skip(f"FFmpeg test video generation failed: {e}")

    return _generate


@pytest.fixture
def measure_performance():
    """
    Context manager for measuring performance metrics.
    """
    class PerformanceMeasure:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.start_memory = None
            self.peak_memory = None
            self.process = psutil.Process()

        def __enter__(self):
            self.start_time = time.time()
            self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            return self

        def __exit__(self, *args):
            self.end_time = time.time()
            current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            self.peak_memory = max(self.start_memory, current_memory)

        @property
        def elapsed_seconds(self):
            return self.end_time - self.start_time if self.end_time else 0

        @property
        def elapsed_minutes(self):
            return self.elapsed_seconds / 60

        @property
        def memory_used_mb(self):
            return self.peak_memory - self.start_memory if self.peak_memory else 0

    return PerformanceMeasure


class TestProxyGenerationPerformance:
    """Performance benchmarks for proxy generation."""

    @pytest.mark.benchmark
    def test_10min_1080p_30fps_benchmark(self, generate_test_video, measure_performance, tmp_path):
        """
        Benchmark: 10-minute 1080p/30fps clip

        Target: <20 minutes processing time (2x real-time)
        """
        ffmpeg_service = get_ffmpeg_service()

        # Generate 10-minute test video
        input_video = generate_test_video(
            duration_seconds=600,  # 10 minutes
            width=1920,
            height=1080,
            fps=30
        )

        output_path = tmp_path / "proxy_10min.mp4"

        # Measure performance
        with measure_performance() as perf:
            result = ffmpeg_service.generate_proxy(
                input_path=input_video,
                output_path=str(output_path),
                target_height=480,
                target_fps=10,
                preset="medium",
                crf=28
            )

        # Get file sizes
        original_size = os.path.getsize(input_video)
        proxy_size = os.path.getsize(str(output_path))
        compression_ratio = (proxy_size / original_size) * 100

        # Print results
        print("\n" + "="*60)
        print("10-MINUTE 1080p/30fps BENCHMARK RESULTS")
        print("="*60)
        print(f"Processing Time: {perf.elapsed_minutes:.2f} minutes ({perf.elapsed_seconds:.1f}s)")
        print(f"Target: <20 minutes (2x real-time)")
        print(f"Real-time Factor: {600 / perf.elapsed_seconds:.2f}x")
        print(f"Memory Used: {perf.memory_used_mb:.1f} MB")
        print(f"Original Size: {original_size / 1024 / 1024:.1f} MB")
        print(f"Proxy Size: {proxy_size / 1024 / 1024:.1f} MB")
        print(f"Compression: {compression_ratio:.1f}% of original")
        print(f"Target Compression: 10-15% of original")
        print("="*60)

        # Assertions
        assert result["success"] is True
        assert perf.elapsed_minutes < 20, f"Processing took {perf.elapsed_minutes:.1f} min (target: <20 min)"
        assert 5 <= compression_ratio <= 20, f"Compression ratio {compression_ratio:.1f}% out of range (5-20%)"
        assert perf.memory_used_mb < 4000, f"Memory usage {perf.memory_used_mb:.0f} MB exceeds 4GB limit"

    @pytest.mark.benchmark
    @pytest.mark.slow
    @pytest.mark.skipif(
        os.environ.get("RUN_HEAVY_BENCHMARKS") != "1",
        reason="Heavy benchmark test (30min video, multi-GB artifacts). Set RUN_HEAVY_BENCHMARKS=1 to run."
    )
    def test_30min_1080p_30fps_benchmark(self, generate_test_video, measure_performance, tmp_path):
        """
        Benchmark: 30-minute 1080p/30fps clip

        Target: <60 minutes processing time (2x real-time)

        NOTE: This test is skipped by default due to resource requirements.
        Run with: RUN_HEAVY_BENCHMARKS=1 pytest backend/tests/performance/test_proxy_benchmarks.py::TestProxyGeneration::test_30min_1080p_30fps_benchmark -v
        """
        ffmpeg_service = get_ffmpeg_service()

        # Generate 30-minute test video
        input_video = generate_test_video(
            duration_seconds=1800,  # 30 minutes
            width=1920,
            height=1080,
            fps=30
        )

        output_path = tmp_path / "proxy_30min.mp4"

        # Measure performance
        with measure_performance() as perf:
            result = ffmpeg_service.generate_proxy(
                input_path=input_video,
                output_path=str(output_path),
                target_height=480,
                target_fps=10,
                preset="medium",
                crf=28
            )

        # Get file sizes
        original_size = os.path.getsize(input_video)
        proxy_size = os.path.getsize(str(output_path))
        compression_ratio = (proxy_size / original_size) * 100

        # Print results
        print("\n" + "="*60)
        print("30-MINUTE 1080p/30fps BENCHMARK RESULTS")
        print("="*60)
        print(f"Processing Time: {perf.elapsed_minutes:.2f} minutes ({perf.elapsed_seconds:.1f}s)")
        print(f"Target: <60 minutes (2x real-time)")
        print(f"Real-time Factor: {1800 / perf.elapsed_seconds:.2f}x")
        print(f"Memory Used: {perf.memory_used_mb:.1f} MB")
        print(f"Original Size: {original_size / 1024 / 1024:.1f} MB")
        print(f"Proxy Size: {proxy_size / 1024 / 1024:.1f} MB")
        print(f"Compression: {compression_ratio:.1f}% of original")
        print("="*60)

        # Assertions
        assert result["success"] is True
        assert perf.elapsed_minutes < 60, f"Processing took {perf.elapsed_minutes:.1f} min (target: <60 min)"
        assert 5 <= compression_ratio <= 20, f"Compression ratio {compression_ratio:.1f}% out of range"
        assert perf.memory_used_mb < 4000, f"Memory usage exceeds 4GB limit"

    @pytest.mark.benchmark
    def test_proxy_quality_verification(self, generate_test_video, tmp_path):
        """
        Verify proxy video quality meets requirements:
        - Resolution: 480p (854x480)
        - Frame rate: 10 fps
        - Codec: H.264
        - Audio: AAC
        """
        ffmpeg_service = get_ffmpeg_service()

        # Generate 1-minute test video
        input_video = generate_test_video(
            duration_seconds=60,
            width=1920,
            height=1080,
            fps=30
        )

        output_path = tmp_path / "proxy_quality_test.mp4"

        # Generate proxy
        result = ffmpeg_service.generate_proxy(
            input_path=input_video,
            output_path=str(output_path),
            target_height=480,
            target_fps=10
        )

        assert result["success"] is True

        # Extract metadata from proxy
        proxy_metadata = ffmpeg_service.extract_metadata(str(output_path))

        print("\n" + "="*60)
        print("PROXY QUALITY VERIFICATION")
        print("="*60)
        print(f"Resolution: {proxy_metadata['width']}x{proxy_metadata['height']} (target: 854x480)")
        print(f"Frame Rate: {proxy_metadata['fps']:.1f} fps (target: 10 fps)")
        print(f"Codec: {proxy_metadata['codec']} (target: h264)")
        print(f"Duration: {proxy_metadata['duration_seconds']:.1f}s")
        print("="*60)

        # Assertions
        assert proxy_metadata["height"] == 480, "Height should be 480p"
        assert 850 <= proxy_metadata["width"] <= 858, "Width should be ~854 (16:9 aspect ratio)"
        assert abs(proxy_metadata["fps"] - 10) < 1, "Frame rate should be ~10 fps"
        assert proxy_metadata["codec"] == "h264", "Codec should be H.264"
        assert abs(proxy_metadata["duration_seconds"] - 60) < 2, "Duration should match original"

    @pytest.mark.benchmark
    def test_thumbnail_generation_performance(self, generate_test_video, measure_performance, tmp_path):
        """
        Benchmark thumbnail generation speed.

        Target: <5 seconds per thumbnail
        """
        ffmpeg_service = get_ffmpeg_service()

        # Generate test video
        input_video = generate_test_video(
            duration_seconds=600,  # 10 minutes
            width=1920,
            height=1080,
            fps=30
        )

        thumbnails = []
        timings = []

        # Generate thumbnails at different timestamps
        timestamps = [5, 30, 60, 180, 300]  # 5s, 30s, 1m, 3m, 5m

        for timestamp in timestamps:
            output_path = tmp_path / f"thumbnail_{timestamp}s.jpg"

            with measure_performance() as perf:
                result = ffmpeg_service.generate_thumbnail(
                    input_path=input_video,
                    output_path=str(output_path),
                    timestamp_seconds=float(timestamp),
                    width=320
                )

            thumbnails.append(output_path)
            timings.append(perf.elapsed_seconds)

            assert result["success"] is True
            assert output_path.exists()
            assert output_path.stat().st_size > 0

        avg_time = sum(timings) / len(timings)

        print("\n" + "="*60)
        print("THUMBNAIL GENERATION BENCHMARK")
        print("="*60)
        print(f"Thumbnails Generated: {len(thumbnails)}")
        print(f"Average Time: {avg_time:.2f}s per thumbnail")
        print(f"Target: <5 seconds per thumbnail")
        print(f"Times: {', '.join(f'{t:.2f}s' for t in timings)}")
        print("="*60)

        # Assertions
        assert all(t < 5 for t in timings), f"Some thumbnails took >5s: {timings}"
        assert avg_time < 3, f"Average time {avg_time:.2f}s exceeds 3s target"


class TestConcurrentProcessing:
    """Tests for concurrent video processing."""

    @pytest.mark.benchmark
    def test_concurrent_upload_handling(self, generate_test_video, measure_performance, tmp_path):
        """
        Test system can handle multiple concurrent uploads.

        Simulates 5 simultaneous uploads to verify no resource contention.
        """
        import concurrent.futures

        # Generate 5 test videos (short for testing)
        test_videos = []
        for i in range(5):
            video = generate_test_video(
                duration_seconds=30,  # 30 seconds
                width=1920,
                height=1080,
                fps=30
            )
            test_videos.append(video)

        # Process all videos concurrently
        results = []
        errors = []

        with measure_performance() as perf:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for i, video in enumerate(test_videos):
                    output = tmp_path / f"proxy_concurrent_{i}.mp4"
                    future = executor.submit(
                        get_ffmpeg_service().generate_proxy,
                        video,
                        str(output),
                        480,
                        10
                    )
                    futures.append((i, future, output))

                for i, future, output in futures:
                    try:
                        result = future.result(timeout=120)
                        results.append((i, result, output))
                    except Exception as e:
                        errors.append((i, str(e)))

        print("\n" + "="*60)
        print("CONCURRENT UPLOAD BENCHMARK")
        print("="*60)
        print(f"Videos Processed: {len(results)}/{len(test_videos)}")
        print(f"Errors: {len(errors)}")
        print(f"Total Time: {perf.elapsed_seconds:.1f}s")
        print(f"Average Time per Video: {perf.elapsed_seconds / len(test_videos):.1f}s")
        print(f"Memory Used: {perf.memory_used_mb:.1f} MB")
        print("="*60)

        # Assertions
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == len(test_videos), "Not all videos processed"
        assert all(r[1]["success"] for r in results), "Some videos failed"

    @pytest.mark.benchmark
    def test_throughput_measurement(self, generate_test_video, measure_performance, tmp_path):
        """
        Measure processing throughput (GB/minute).

        Target: Process 2GB in <5 minutes (0.4 GB/min)
        """
        ffmpeg_service = get_ffmpeg_service()

        # Generate multiple test videos totaling ~500MB
        test_videos = []
        total_size = 0

        for i in range(3):
            video = generate_test_video(
                duration_seconds=120,  # 2 minutes each
                width=1920,
                height=1080,
                fps=30
            )
            size = os.path.getsize(video)
            test_videos.append((video, size))
            total_size += size

        # Process all videos
        with measure_performance() as perf:
            for video, size in test_videos:
                output = tmp_path / f"throughput_proxy_{test_videos.index((video, size))}.mp4"
                ffmpeg_service.generate_proxy(
                    input_path=video,
                    output_path=str(output),
                    target_height=480,
                    target_fps=10
                )

        throughput_gb_per_min = (total_size / 1024 / 1024 / 1024) / perf.elapsed_minutes

        print("\n" + "="*60)
        print("THROUGHPUT BENCHMARK")
        print("="*60)
        print(f"Total Data Processed: {total_size / 1024 / 1024:.1f} MB")
        print(f"Processing Time: {perf.elapsed_minutes:.2f} minutes")
        print(f"Throughput: {throughput_gb_per_min:.2f} GB/min")
        print(f"Target: >0.4 GB/min (2GB in 5 minutes)")
        print("="*60)

        # Assertion
        assert throughput_gb_per_min > 0.3, f"Throughput {throughput_gb_per_min:.2f} GB/min below minimum"


# Pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "benchmark: mark test as a performance benchmark"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
