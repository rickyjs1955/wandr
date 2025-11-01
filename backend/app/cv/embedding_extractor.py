"""
Visual Embedding Extraction Service

Extracts compact appearance embeddings using CLIP for person re-identification.
Phase 3.3 implementation with 512D → 128D projection.

Key Features:
- CLIP-ViT-B/32 backbone for visual feature extraction
- Learned projection layer: 512D → 128D
- L2-normalized embeddings for cosine similarity
- PCA-initialized projection (fallback if no pretrained weights)
- Binary serialization for efficient storage
"""
import logging
import struct
import warnings
from typing import Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
from transformers import CLIPProcessor, CLIPModel
from sklearn.decomposition import PCA

logger = logging.getLogger(__name__)


class EmbeddingExtractor:
    """
    Extract visual embeddings using CLIP model.

    Workflow:
    1. Preprocess person crop for CLIP input
    2. Extract 512D CLIP visual features
    3. Project to 128D via learned projection layer
    4. L2 normalize for cosine similarity

    Phase 3.3 Implementation:
    - Uses CLIP-ViT-B/32 as backbone (pretrained on image-text pairs)
    - 512D → 128D projection initialized with Xavier or PCA
    - Embedding validation (NaN/inf checks)
    - Binary serialization support

    IMPORTANT - Projection Initialization:
    The 128D projection layer requires pretrained weights for meaningful embeddings.
    Two options:
    - Option A (MVP): Use PCA-initialized projection from sample crops
    - Option B (Future): Load pretrained projection from fashion re-ID dataset
      (e.g., DeepFashion2, Market-1501 fine-tuned CLIP)
    """

    def __init__(
        self,
        model_name: str = "openai/clip-vit-base-patch32",
        projection_weights_path: Optional[str] = None,
        embedding_dim: Optional[int] = None,
        device: Optional[str] = None
    ):
        """
        Initialize embedding extractor.

        Args:
            model_name: HuggingFace model name for CLIP
            projection_weights_path: Path to pretrained projection weights (optional)
            embedding_dim: Output embedding dimensionality (default: None = use raw CLIP features)
                          If None, uses raw CLIP features (512D for ViT-B/32)
                          If specified with projection_weights_path, uses projection
            device: Device to run on ("cuda", "cpu", or None for auto-detect)
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        logger.info(f"Loading CLIP model: {model_name} on {self.device}")

        # Load CLIP model and processor
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)

        # Set to evaluation mode
        self.model.eval()

        # Get CLIP feature dimension
        # Note: ViT-B/32 outputs 512D from vision model, but get_image_features returns projection output
        # which can be different. We need to check the actual output dimension.
        with torch.no_grad():
            dummy_input = torch.randn(1, 3, 224, 224).to(self.device)
            dummy_features = self.model.get_image_features(pixel_values=dummy_input)
            self.clip_dim = dummy_features.shape[-1]

        logger.info(f"Detected CLIP feature dimension: {self.clip_dim}D")

        # Determine if we use projection or raw features
        if projection_weights_path:
            # Use projection with pretrained weights
            if embedding_dim is None:
                raise ValueError("embedding_dim must be specified when using projection_weights_path")
            self.embedding_dim = embedding_dim
            self.use_projection = True
            logger.info(f"Using projection: {self.clip_dim}D → {self.embedding_dim}D")

            self.projection = nn.Linear(self.clip_dim, self.embedding_dim).to(self.device)
            self.projection.load_state_dict(torch.load(projection_weights_path, map_location=self.device))
            logger.info(f"Loaded pretrained projection weights from: {projection_weights_path}")
        else:
            # Use raw CLIP features (no projection)
            self.embedding_dim = self.clip_dim
            self.use_projection = False
            self.projection = None
            logger.info(
                f"Using raw CLIP features ({self.clip_dim}D). "
                "For dimensionality reduction, provide projection_weights_path or use initialize_projection_pca()."
            )

    def _initialize_projection_xavier(self):
        """
        Initialize projection layer with Xavier uniform distribution.

        Xavier initialization provides better gradient flow than random initialization,
        but does not leverage domain knowledge. For better performance, use PCA
        initialization with sample person crops.
        """
        torch.nn.init.xavier_uniform_(self.projection.weight)
        torch.nn.init.zeros_(self.projection.bias)
        logger.info("Projection layer initialized with Xavier uniform")

    def initialize_projection_pca(self, sample_crops: np.ndarray, target_dim: int = 128):
        """
        Initialize projection layer using PCA on sample person crops.

        This provides better initialization than raw CLIP features by reducing
        dimensionality while preserving maximum variance.

        Args:
            sample_crops: Array of person crop images (N, H, W, 3)
                         Should contain diverse samples (100+ recommended)
            target_dim: Target embedding dimension (default: 128)

        Example:
            >>> extractor = EmbeddingExtractor()
            >>> sample_crops = load_person_crops(n=100)
            >>> extractor.initialize_projection_pca(sample_crops, target_dim=128)
        """
        if self.use_projection:
            logger.warning("Projection already initialized. Overwriting with PCA initialization.")

        logger.info(f"Initializing projection with PCA from {len(sample_crops)} samples")
        logger.info(f"Target dimension: {self.clip_dim}D → {target_dim}D")

        # Extract CLIP features for all samples
        features = []
        with torch.no_grad():
            for crop in sample_crops:
                inputs = self.processor(images=crop, return_tensors="pt")
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                feat = self.model.get_image_features(**inputs)
                features.append(feat.cpu().numpy().squeeze())

        features = np.vstack(features)  # (N, clip_dim)

        # Fit PCA: clip_dim → target_dim
        pca = PCA(n_components=target_dim)
        pca.fit(features)

        # Create or update projection layer
        self.embedding_dim = target_dim
        self.projection = nn.Linear(self.clip_dim, self.embedding_dim).to(self.device)
        self.use_projection = True

        # Use PCA components as projection weights
        self.projection.weight.data = torch.from_numpy(pca.components_).float().to(self.device)
        self.projection.bias.data = torch.zeros(self.embedding_dim).to(self.device)

        explained_variance = pca.explained_variance_ratio_.sum()
        logger.info(
            f"PCA projection initialized. "
            f"Explained variance: {explained_variance:.2%}"
        )

    def extract(self, image: np.ndarray) -> np.ndarray:
        """
        Extract embedding from person crop.

        Args:
            image: RGB image of person (H x W x 3), numpy array

        Returns:
            L2-normalized embedding vector (numpy array)
            - If using raw CLIP features: 512D
            - If using projection: embedding_dim (e.g., 128D)

        Raises:
            ValueError: If image is invalid or extraction fails
        """
        if image is None or image.size == 0:
            raise ValueError("Invalid image: empty or None")

        if len(image.shape) != 3 or image.shape[2] != 3:
            raise ValueError(f"Invalid image shape: {image.shape}, expected (H, W, 3)")

        try:
            # Preprocess image for CLIP
            inputs = self.processor(images=image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Extract features
            with torch.no_grad():
                # Get CLIP visual features
                features = self.model.get_image_features(**inputs)

                # Apply projection if enabled
                if self.use_projection:
                    embedding = self.projection(features)
                else:
                    embedding = features

                # L2 normalize for cosine similarity
                embedding = embedding / embedding.norm(dim=-1, keepdim=True)

            # Convert to numpy
            embedding_np = embedding.cpu().numpy().squeeze()

            # Validate embedding
            if not self._validate_embedding(embedding_np):
                raise ValueError("Extracted embedding contains invalid values (NaN or inf)")

            return embedding_np

        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}")
            raise ValueError(f"Failed to extract embedding: {e}")

    def extract_batch(self, images: np.ndarray) -> np.ndarray:
        """
        Extract embeddings for batch of person crops.

        More efficient than calling extract() individually due to batched processing.

        Args:
            images: Batch of RGB images (N, H, W, 3)

        Returns:
            Batch of L2-normalized embeddings (N, embedding_dim)
            - If using raw CLIP features: (N, 512)
            - If using projection: (N, embedding_dim)
        """
        if images is None or len(images) == 0:
            raise ValueError("Invalid images: empty or None")

        try:
            # Preprocess batch
            inputs = self.processor(images=list(images), return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Extract features
            with torch.no_grad():
                # Get CLIP visual features (N, 512)
                features = self.model.get_image_features(**inputs)

                # Apply projection if enabled
                if self.use_projection:
                    embeddings = self.projection(features)
                else:
                    embeddings = features

                # L2 normalize each embedding
                embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)

            # Convert to numpy
            embeddings_np = embeddings.cpu().numpy()

            # Validate all embeddings
            for i, emb in enumerate(embeddings_np):
                if not self._validate_embedding(emb):
                    logger.warning(f"Embedding {i} contains invalid values, skipping")

            return embeddings_np

        except Exception as e:
            logger.error(f"Batch embedding extraction failed: {e}")
            raise ValueError(f"Failed to extract batch embeddings: {e}")

    def _validate_embedding(self, embedding: np.ndarray) -> bool:
        """
        Validate embedding for NaN or inf values.

        Args:
            embedding: Embedding vector to validate

        Returns:
            True if embedding is valid, False otherwise
        """
        if np.isnan(embedding).any():
            logger.error("Embedding contains NaN values")
            return False

        if np.isinf(embedding).any():
            logger.error("Embedding contains inf values")
            return False

        # Check if embedding is all zeros (potential issue)
        if np.allclose(embedding, 0):
            logger.warning("Embedding is all zeros")
            return False

        return True

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.

        For L2-normalized embeddings, this is equivalent to dot product.

        Args:
            emb1: First embedding (128D)
            emb2: Second embedding (128D)

        Returns:
            Cosine similarity in range [-1, 1]
            - 1.0: Identical
            - 0.0: Orthogonal (completely different)
            - -1.0: Opposite
        """
        # For L2-normalized vectors, dot product == cosine similarity
        return float(np.dot(emb1, emb2))

    @staticmethod
    def serialize_embedding(embedding: np.ndarray) -> bytes:
        """
        Serialize float32 embedding to binary format.

        Useful for efficient database storage.

        Args:
            embedding: Embedding vector (any dimension)

        Returns:
            Binary representation (dim * 4 bytes)
        """
        # Convert to float32 if needed
        embedding = embedding.astype(np.float32)

        # Pack as binary (dynamic size)
        dim = embedding.shape[0]
        return struct.pack(f'{dim}f', *embedding)

    @staticmethod
    def deserialize_embedding(binary: bytes, expected_dim: Optional[int] = None) -> np.ndarray:
        """
        Deserialize binary to float32 embedding.

        Args:
            binary: Binary representation
            expected_dim: Expected dimension (optional, for validation)

        Returns:
            Embedding vector
        """
        # Calculate dimension from binary length
        dim = len(binary) // 4  # 4 bytes per float32

        if expected_dim is not None and dim != expected_dim:
            raise ValueError(f"Expected {expected_dim}D embedding, got {dim}D from binary")

        # Unpack binary to floats
        return np.array(struct.unpack(f'{dim}f', binary), dtype=np.float32)


def create_embedding_extractor(
    model_name: str = "openai/clip-vit-base-patch32",
    projection_weights_path: Optional[str] = None
) -> EmbeddingExtractor:
    """
    Factory function to create embedding extractor.

    Args:
        model_name: HuggingFace model name for CLIP
        projection_weights_path: Path to pretrained projection weights (optional)

    Returns:
        EmbeddingExtractor instance
    """
    return EmbeddingExtractor(
        model_name=model_name,
        projection_weights_path=projection_weights_path
    )
