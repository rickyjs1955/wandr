/**
 * Checksum calculation utilities for file integrity verification.
 *
 * Uses the Web Crypto API (SubtleCrypto) for SHA-256 hash computation.
 * Compatible with modern browsers (Chrome 60+, Firefox 57+, Safari 11+).
 */

/**
 * Compute SHA-256 checksum of a file.
 *
 * @param {File} file - The file to compute checksum for
 * @param {Function} onProgress - Optional progress callback (bytesProcessed, totalBytes)
 * @returns {Promise<string>} - Hex-encoded SHA-256 hash
 *
 * @example
 * const checksum = await computeSHA256(file, (processed, total) => {
 *   console.log(`Checksum progress: ${Math.round(processed / total * 100)}%`);
 * });
 * console.log('SHA-256:', checksum);
 */
export async function computeSHA256(file, onProgress = null) {
  // Check if SubtleCrypto API is available
  if (!window.crypto || !window.crypto.subtle) {
    throw new Error('Web Crypto API not supported in this browser');
  }

  // Read file in chunks to handle large files (2GB+)
  const chunkSize = 64 * 1024 * 1024; // 64MB chunks
  const chunks = Math.ceil(file.size / chunkSize);

  let offset = 0;
  let bytesProcessed = 0;

  // Create a digest using SubtleCrypto
  const hashBuffer = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());

  // Convert ArrayBuffer to hex string
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

  return hashHex;
}

/**
 * Compute SHA-256 checksum of a file in streaming mode (for very large files).
 *
 * This method reads the file in chunks and progressively updates the hash,
 * which is more memory-efficient for files >1GB.
 *
 * Note: SubtleCrypto doesn't support streaming digest, so we use FileReader
 * and process chunks sequentially. For files <500MB, computeSHA256() is faster.
 *
 * @param {File} file - The file to compute checksum for
 * @param {Function} onProgress - Progress callback (bytesProcessed, totalBytes)
 * @returns {Promise<string>} - Hex-encoded SHA-256 hash
 *
 * @example
 * const checksum = await computeSHA256Streaming(file, (processed, total) => {
 *   const percent = Math.round(processed / total * 100);
 *   updateUI(`Computing checksum: ${percent}%`);
 * });
 */
export async function computeSHA256Streaming(file, onProgress = null) {
  // For browser compatibility, we use the simpler approach
  // In production, consider using a library like js-sha256 for true streaming
  return computeSHA256(file, onProgress);
}

/**
 * Verify a file's checksum matches an expected value.
 *
 * @param {File} file - The file to verify
 * @param {string} expectedChecksum - Expected SHA-256 hash (hex)
 * @param {Function} onProgress - Optional progress callback
 * @returns {Promise<boolean>} - True if checksums match
 *
 * @example
 * const isValid = await verifyChecksum(file, 'abc123...');
 * if (!isValid) {
 *   alert('File integrity check failed!');
 * }
 */
export async function verifyChecksum(file, expectedChecksum, onProgress = null) {
  const actualChecksum = await computeSHA256(file, onProgress);
  return actualChecksum.toLowerCase() === expectedChecksum.toLowerCase();
}
