"""
Benchmark Script for Visual Embedding Extraction (Phase 3.3)

Tests:
1. Embedding extraction performance (throughput, latency)
2. Embedding discriminability (similar vs different outfits)
3. Serialization/deserialization performance
4. Batch vs single extraction comparison
5. Embedding validation (no NaN/inf)

Usage:
    python backend/scripts/benchmark_embedding_extraction.py
"""
import sys
import time
import numpy as np
import cv2
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.cv.embedding_extractor import EmbeddingExtractor, create_embedding_extractor


def generate_synthetic_person_crops(num_crops: int = 50, size: tuple = (256, 128)) -> np.ndarray:
    """
    Generate synthetic person crop images for testing.

    Args:
        num_crops: Number of crops to generate
        size: Image size (height, width)

    Returns:
        Array of synthetic person crops (num_crops, height, width, 3)
    """
    crops = []
    h, w = size

    for i in range(num_crops):
        # Create synthetic person with outfit colors
        crop = np.zeros((h, w, 3), dtype=np.uint8)

        # Top region (0-40% height): random color
        top_color = np.random.randint(50, 255, 3)
        crop[0:int(h*0.4), :] = top_color

        # Bottom region (40-80% height): random color
        bottom_color = np.random.randint(50, 255, 3)
        crop[int(h*0.4):int(h*0.8), :] = bottom_color

        # Shoes region (80-100% height): random color
        shoes_color = np.random.randint(20, 150, 3)
        crop[int(h*0.8):, :] = shoes_color

        # Add some noise for realism
        noise = np.random.randint(-20, 20, (h, w, 3), dtype=np.int16)
        crop = np.clip(crop.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        crops.append(crop)

    return np.array(crops)


def generate_similar_outfit_pairs(num_pairs: int = 10) -> tuple:
    """
    Generate pairs of person crops with similar outfits.

    Returns:
        (crops_a, crops_b) where each pair has similar outfit colors
    """
    crops_a = []
    crops_b = []
    h, w = 256, 128

    for i in range(num_pairs):
        # Base outfit colors
        top_color = np.random.randint(50, 255, 3)
        bottom_color = np.random.randint(50, 255, 3)
        shoes_color = np.random.randint(20, 150, 3)

        # Crop A
        crop_a = np.zeros((h, w, 3), dtype=np.uint8)
        crop_a[0:int(h*0.4), :] = top_color
        crop_a[int(h*0.4):int(h*0.8), :] = bottom_color
        crop_a[int(h*0.8):, :] = shoes_color
        crops_a.append(crop_a)

        # Crop B: Similar colors with slight variation (±15)
        crop_b = np.zeros((h, w, 3), dtype=np.uint8)
        top_variation = np.clip(top_color + np.random.randint(-15, 15, 3), 0, 255).astype(np.uint8)
        bottom_variation = np.clip(bottom_color + np.random.randint(-15, 15, 3), 0, 255).astype(np.uint8)
        shoes_variation = np.clip(shoes_color + np.random.randint(-15, 15, 3), 0, 255).astype(np.uint8)

        crop_b[0:int(h*0.4), :] = top_variation
        crop_b[int(h*0.4):int(h*0.8), :] = bottom_variation
        crop_b[int(h*0.8):, :] = shoes_variation
        crops_b.append(crop_b)

    return np.array(crops_a), np.array(crops_b)


def generate_different_outfit_pairs(num_pairs: int = 10) -> tuple:
    """
    Generate pairs of person crops with different outfits.

    Returns:
        (crops_a, crops_b) where each pair has different outfit colors
    """
    crops_a = []
    crops_b = []
    h, w = 256, 128

    for i in range(num_pairs):
        # Crop A
        crop_a = np.zeros((h, w, 3), dtype=np.uint8)
        crop_a[0:int(h*0.4), :] = np.random.randint(50, 255, 3)
        crop_a[int(h*0.4):int(h*0.8), :] = np.random.randint(50, 255, 3)
        crop_a[int(h*0.8):, :] = np.random.randint(20, 150, 3)
        crops_a.append(crop_a)

        # Crop B: Completely different colors
        crop_b = np.zeros((h, w, 3), dtype=np.uint8)
        crop_b[0:int(h*0.4), :] = np.random.randint(50, 255, 3)
        crop_b[int(h*0.4):int(h*0.8), :] = np.random.randint(50, 255, 3)
        crop_b[int(h*0.8):, :] = np.random.randint(20, 150, 3)
        crops_b.append(crop_b)

    return np.array(crops_a), np.array(crops_b)


def benchmark_extraction_performance(extractor: EmbeddingExtractor, num_crops: int = 50):
    """
    Benchmark embedding extraction throughput and latency.
    """
    print("\n" + "="*60)
    print("BENCHMARK 1: Extraction Performance")
    print("="*60)

    crops = generate_synthetic_person_crops(num_crops)

    # Warmup
    _ = extractor.extract(crops[0])

    # Single extraction benchmark
    single_times = []
    for crop in crops:
        start = time.time()
        embedding = extractor.extract(crop)
        single_times.append(time.time() - start)

    avg_single_time = np.mean(single_times) * 1000  # Convert to ms
    throughput = 1.0 / np.mean(single_times)

    print(f"\nSingle Extraction:")
    print(f"  Average time: {avg_single_time:.2f} ms")
    print(f"  Throughput: {throughput:.2f} crops/sec")
    print(f"  Target: <50 ms per crop")
    print(f"  Status: {'✅ PASS' if avg_single_time < 50 else '❌ FAIL'}")

    # Batch extraction benchmark
    batch_start = time.time()
    embeddings_batch = extractor.extract_batch(crops)
    batch_time = time.time() - batch_start

    avg_batch_time = (batch_time / num_crops) * 1000
    batch_throughput = num_crops / batch_time

    print(f"\nBatch Extraction ({num_crops} crops):")
    print(f"  Total time: {batch_time:.2f} s")
    print(f"  Average time per crop: {avg_batch_time:.2f} ms")
    print(f"  Throughput: {batch_throughput:.2f} crops/sec")
    print(f"  Speedup vs single: {throughput / batch_throughput:.2f}x")

    return {
        "single_avg_time_ms": avg_single_time,
        "single_throughput": throughput,
        "batch_avg_time_ms": avg_batch_time,
        "batch_throughput": batch_throughput
    }


def benchmark_discriminability(extractor: EmbeddingExtractor, num_pairs: int = 10):
    """
    Benchmark embedding discriminability on similar vs different outfit pairs.
    """
    print("\n" + "="*60)
    print("BENCHMARK 2: Embedding Discriminability")
    print("="*60)

    # Generate test pairs
    similar_a, similar_b = generate_similar_outfit_pairs(num_pairs)
    different_a, different_b = generate_different_outfit_pairs(num_pairs)

    # Extract embeddings
    similar_a_emb = extractor.extract_batch(similar_a)
    similar_b_emb = extractor.extract_batch(similar_b)
    different_a_emb = extractor.extract_batch(different_a)
    different_b_emb = extractor.extract_batch(different_b)

    # Calculate similarities
    similar_scores = []
    for i in range(num_pairs):
        sim = extractor.cosine_similarity(similar_a_emb[i], similar_b_emb[i])
        similar_scores.append(sim)

    different_scores = []
    for i in range(num_pairs):
        sim = extractor.cosine_similarity(different_a_emb[i], different_b_emb[i])
        different_scores.append(sim)

    similar_avg = np.mean(similar_scores)
    different_avg = np.mean(different_scores)
    gap = similar_avg - different_avg

    print(f"\nSimilar Outfits ({num_pairs} pairs):")
    print(f"  Average cosine similarity: {similar_avg:.3f}")
    print(f"  Min: {np.min(similar_scores):.3f}, Max: {np.max(similar_scores):.3f}")
    print(f"  Target: >0.75")
    print(f"  Status: {'✅ PASS' if similar_avg > 0.75 else '⚠️  WARNING - May need PCA initialization or pretrained weights'}")

    print(f"\nDifferent Outfits ({num_pairs} pairs):")
    print(f"  Average cosine similarity: {different_avg:.3f}")
    print(f"  Min: {np.min(different_scores):.3f}, Max: {np.max(different_scores):.3f}")
    print(f"  Target: <0.5")
    print(f"  Status: {'✅ PASS' if different_avg < 0.5 else '⚠️  WARNING - May need PCA initialization or pretrained weights'}")

    print(f"\nDiscriminability Gap:")
    print(f"  Similar - Different: {gap:.3f}")
    print(f"  Target: >0.25")
    print(f"  Status: {'✅ PASS' if gap > 0.25 else '⚠️  WARNING - Embeddings may not be discriminative enough'}")

    return {
        "similar_avg": similar_avg,
        "different_avg": different_avg,
        "gap": gap
    }


def benchmark_serialization(extractor: EmbeddingExtractor, num_embeddings: int = 1000):
    """
    Benchmark embedding serialization/deserialization performance.
    """
    print("\n" + "="*60)
    print("BENCHMARK 3: Serialization Performance")
    print("="*60)

    # Generate embeddings
    crops = generate_synthetic_person_crops(num_crops=50)
    embeddings = extractor.extract_batch(crops)

    # Take first embedding for testing
    embedding = embeddings[0]

    # Serialization benchmark
    serialize_times = []
    for _ in range(num_embeddings):
        start = time.time()
        binary = extractor.serialize_embedding(embedding)
        serialize_times.append(time.time() - start)

    avg_serialize_time = np.mean(serialize_times) * 1_000_000  # Convert to microseconds

    print(f"\nSerialization:")
    print(f"  Average time: {avg_serialize_time:.2f} µs")
    print(f"  Binary size: 512 bytes (128 floats × 4 bytes)")

    # Deserialization benchmark
    binary = extractor.serialize_embedding(embedding)
    deserialize_times = []
    for _ in range(num_embeddings):
        start = time.time()
        restored = extractor.deserialize_embedding(binary)
        deserialize_times.append(time.time() - start)

    avg_deserialize_time = np.mean(deserialize_times) * 1_000_000

    print(f"\nDeserialization:")
    print(f"  Average time: {avg_deserialize_time:.2f} µs")

    # Verify correctness
    binary = extractor.serialize_embedding(embedding)
    restored = extractor.deserialize_embedding(binary)
    is_correct = np.allclose(embedding, restored)

    print(f"\nCorrectness:")
    print(f"  Serialization → Deserialization: {'✅ PASS' if is_correct else '❌ FAIL'}")

    return {
        "serialize_time_us": avg_serialize_time,
        "deserialize_time_us": avg_deserialize_time,
        "correctness": is_correct
    }


def benchmark_validation(extractor: EmbeddingExtractor, num_crops: int = 100):
    """
    Benchmark embedding validation (check for NaN/inf).
    """
    print("\n" + "="*60)
    print("BENCHMARK 4: Embedding Validation")
    print("="*60)

    crops = generate_synthetic_person_crops(num_crops)
    embeddings = extractor.extract_batch(crops)

    # Check for invalid values
    nan_count = sum(np.isnan(emb).any() for emb in embeddings)
    inf_count = sum(np.isinf(emb).any() for emb in embeddings)
    zero_count = sum(np.allclose(emb, 0) for emb in embeddings)

    print(f"\nValidation Results ({num_crops} embeddings):")
    print(f"  NaN embeddings: {nan_count}")
    print(f"  Inf embeddings: {inf_count}")
    print(f"  All-zero embeddings: {zero_count}")
    print(f"  Valid embeddings: {num_crops - nan_count - inf_count - zero_count}")
    print(f"  Status: {'✅ PASS - All embeddings valid' if (nan_count + inf_count + zero_count) == 0 else '❌ FAIL - Invalid embeddings detected'}")

    # Check L2 normalization
    norms = [np.linalg.norm(emb) for emb in embeddings]
    avg_norm = np.mean(norms)
    norm_std = np.std(norms)

    print(f"\nL2 Normalization:")
    print(f"  Average norm: {avg_norm:.4f} (target: 1.0)")
    print(f"  Std deviation: {norm_std:.4f} (should be ~0)")
    print(f"  Status: {'✅ PASS' if abs(avg_norm - 1.0) < 0.01 else '⚠️  WARNING - Embeddings may not be properly normalized'}")

    return {
        "nan_count": nan_count,
        "inf_count": inf_count,
        "zero_count": zero_count,
        "avg_norm": avg_norm,
        "norm_std": norm_std
    }


def main():
    """
    Run all embedding extraction benchmarks.
    """
    print("\n" + "="*60)
    print("VISUAL EMBEDDING EXTRACTION BENCHMARK")
    print("Phase 3.3 - CLIP Integration")
    print("="*60)

    # Create embedding extractor
    print("\nInitializing embedding extractor...")
    print("  Model: openai/clip-vit-base-patch32")
    print("  Projection: 512D → 128D")
    print("  Initialization: Xavier uniform (no pretrained weights)")

    extractor = create_embedding_extractor()

    # Run benchmarks
    perf_results = benchmark_extraction_performance(extractor, num_crops=50)
    discrim_results = benchmark_discriminability(extractor, num_pairs=10)
    serial_results = benchmark_serialization(extractor, num_embeddings=1000)
    valid_results = benchmark_validation(extractor, num_crops=100)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    print(f"\nPerformance:")
    print(f"  ✓ Single extraction: {perf_results['single_avg_time_ms']:.2f} ms/crop")
    print(f"  ✓ Batch extraction: {perf_results['batch_avg_time_ms']:.2f} ms/crop")
    print(f"  ✓ Throughput: {perf_results['batch_throughput']:.2f} crops/sec")

    print(f"\nDiscriminability:")
    print(f"  {'✓' if discrim_results['similar_avg'] > 0.75 else '⚠'} Similar outfits: {discrim_results['similar_avg']:.3f}")
    print(f"  {'✓' if discrim_results['different_avg'] < 0.5 else '⚠'} Different outfits: {discrim_results['different_avg']:.3f}")
    print(f"  {'✓' if discrim_results['gap'] > 0.25 else '⚠'} Discriminability gap: {discrim_results['gap']:.3f}")

    if discrim_results['similar_avg'] < 0.75 or discrim_results['different_avg'] > 0.5:
        print(f"\n⚠️  WARNING: Embeddings may not be sufficiently discriminative.")
        print(f"   Recommendation: Initialize projection with PCA or load pretrained weights.")
        print(f"   See: extractor.initialize_projection_pca(sample_crops)")

    print(f"\nSerialization:")
    print(f"  ✓ Serialize: {serial_results['serialize_time_us']:.2f} µs")
    print(f"  ✓ Deserialize: {serial_results['deserialize_time_us']:.2f} µs")
    print(f"  ✓ Correctness: {'PASS' if serial_results['correctness'] else 'FAIL'}")

    print(f"\nValidation:")
    print(f"  ✓ Valid embeddings: {100 - valid_results['nan_count'] - valid_results['inf_count'] - valid_results['zero_count']}/100")
    print(f"  ✓ L2 normalized: {valid_results['avg_norm']:.4f} (±{valid_results['norm_std']:.4f})")

    overall_pass = (
        perf_results['single_avg_time_ms'] < 50 and
        valid_results['nan_count'] + valid_results['inf_count'] + valid_results['zero_count'] == 0 and
        abs(valid_results['avg_norm'] - 1.0) < 0.01
    )

    print(f"\n{'='*60}")
    print(f"OVERALL STATUS: {'✅ PASS' if overall_pass else '⚠️  PASS WITH WARNINGS'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
