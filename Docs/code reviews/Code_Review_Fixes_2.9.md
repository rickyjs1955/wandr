# Phase 2.9 Code Review Fixes

## Issues Addressed

### HIGH Priority Issue 1: Video Playback State Loss During URL Refresh
**Location**: `frontend/src/components/VideoPlayer.jsx:61-69`

**Problem**: When the signed URL expired and the `useSignedUrl` hook automatically refreshed it (every 55 minutes by default), the VideoPlayer component immediately reset the video element's source without preserving the current playback position or play state. This caused:
- Video to jump back to 0:00 (start)
- Playback to stop completely
- Operators forced to manually re-seek to their previous position
- Disruptive user experience during long monitoring sessions

**Root Cause**: The `useEffect` that watches for URL changes simply set `videoRef.current.src = url` without capturing the current `currentTime` or checking if the video was playing (`paused` state). When the browser loads a new source, it resets all playback state to defaults.

**Fix**: Implemented state preservation and restoration logic:

```javascript
// Before (lines 61-69):
useEffect(() => {
  if (url && videoRef.current) {
    videoRef.current.src = url;
    if (autoPlay) {
      videoRef.current.play().catch(err => {
        console.error('Autoplay failed:', err);
      });
    }
  }
}, [url, autoPlay]);

// After (lines 61-91):
useEffect(() => {
  if (url && videoRef.current) {
    // Preserve current playback state before changing source
    const savedTime = videoRef.current.currentTime;
    const wasPlaying = !videoRef.current.paused;

    // Update source
    videoRef.current.src = url;

    // Restore playback state after metadata loads
    const handleLoadedMetadataForRestore = () => {
      if (videoRef.current) {
        // Restore time position
        videoRef.current.currentTime = savedTime;

        // Restore play state
        if (wasPlaying || autoPlay) {
          videoRef.current.play().catch(err => {
            console.error('Playback restoration failed:', err);
          });
        }
      }

      // Remove the one-time listener
      videoRef.current?.removeEventListener('loadedmetadata', handleLoadedMetadataForRestore);
    };

    // Listen for metadata load to restore state
    videoRef.current.addEventListener('loadedmetadata', handleLoadedMetadataForRestore);
  }
}, [url, autoPlay]);
```

**Implementation Details**:
1. **Capture state before change**: Save `currentTime` and `paused` state before updating `src`
2. **Wait for metadata load**: Use `loadedmetadata` event to know when new source is ready
3. **Restore position**: Set `currentTime` to saved value once metadata is loaded
4. **Restore play state**: Resume playback if video was playing before refresh
5. **Clean up listener**: Remove the one-time event listener after restoration

**Benefits**:
- Seamless URL refresh without interrupting playback
- Operators don't notice when URLs are refreshed in background
- Continuous monitoring sessions work smoothly
- Better user experience for long video review sessions

**Files Modified**:
- `frontend/src/components/VideoPlayer.jsx` (lines 61-91)

---

### MEDIUM Priority Issue 2: Memory Leak from Uncleaned Countdown Intervals
**Location**: `frontend/src/hooks/useSignedUrl.js:97-111`

**Problem**: The `useSignedUrl` hook started a new countdown interval every time it refreshed the signed URL (via `fetchSignedUrl()`), but never cleared the previous interval before assigning the new one. This caused:
- After first auto-refresh, stale intervals continued running in background
- Multiple intervals competing to update `secondsUntilExpiry` state
- UI showing "Expired" even though URL was successfully refreshed
- Memory leak as intervals accumulated over time
- Potential performance degradation in long-running sessions

**Root Cause**: Line 98 assigned `countdownIntervalRef.current = setInterval(...)` without first clearing any existing interval. When `fetchSignedUrl()` was called recursively during auto-refresh, it created a new interval while the old one kept running.

**Example Timeline**:
```
T=0min:   Initial fetch � Interval A created (updates every 10s)
T=55min:  Auto-refresh � Interval B created, Interval A still running
T=110min: Auto-refresh � Interval C created, Intervals A & B still running
Result:   3 intervals fighting to update state, stale ones showing "expired"
```

**Fix**: Added interval cleanup before creating new interval:

```javascript
// Before (lines 97-105):
// Start countdown timer (update every 10 seconds)
countdownIntervalRef.current = setInterval(() => {
  if (!mountedRef.current) return;

  const expiryTime = new Date(response.expires_at).getTime();
  const now = Date.now();
  const seconds = Math.floor((expiryTime - now) / 1000);
  setSecondsUntilExpiry(seconds > 0 ? seconds : 0);
}, 10000); // Update every 10 seconds

// After (lines 97-111):
// Clear any existing countdown interval before starting a new one
if (countdownIntervalRef.current) {
  clearInterval(countdownIntervalRef.current);
  countdownIntervalRef.current = null;
}

// Start countdown timer (update every 10 seconds)
countdownIntervalRef.current = setInterval(() => {
  if (!mountedRef.current) return;

  const expiryTime = new Date(response.expires_at).getTime();
  const now = Date.now();
  const seconds = Math.floor((expiryTime - now) / 1000);
  setSecondsUntilExpiry(seconds > 0 ? seconds : 0);
}, 10000); // Update every 10 seconds
```

**Implementation Details**:
1. **Check for existing interval**: Test if `countdownIntervalRef.current` has a value
2. **Clear before creating**: Call `clearInterval()` on existing interval
3. **Reset ref**: Set ref to `null` for cleanliness
4. **Create new interval**: Assign new interval to ref

**Benefits**:
- Only one countdown interval runs at a time
- UI correctly shows time until expiry after auto-refresh
- No memory leaks from accumulated intervals
- Better performance in long-running sessions
- Prevents state thrashing from multiple intervals

**Files Modified**:
- `frontend/src/hooks/useSignedUrl.js` (lines 97-101)

---

## Summary

Both issues in Phase 2.9 have been resolved:

1.  **HIGH**: Fixed video playback state loss - URL refreshes now preserve playback position and play state
2.  **MEDIUM**: Fixed countdown interval memory leak - old intervals are properly cleaned before creating new ones

**Key Improvements**:
- **Seamless URL Refresh**: Operators can monitor video continuously without interruption when URLs auto-refresh
- **Accurate Expiry Countdown**: UI correctly shows time remaining until next refresh
- **Memory Management**: No interval leaks, better performance in long sessions
- **Better UX**: Video playback feels smooth and reliable during extended monitoring sessions

**Files Modified**: 2
- `frontend/src/components/VideoPlayer.jsx` (playback state preservation)
- `frontend/src/hooks/useSignedUrl.js` (interval cleanup)

**Testing Recommendation**:
- **Playback Preservation Test**:
  1. Start playing a video at 5:00 mark
  2. Wait for URL auto-refresh (or manually trigger via dev tools)
  3. Verify video continues playing at 5:00 mark without jumping to 0:00
  4. Repeat test while video is paused - verify it stays paused at same position

- **Countdown Interval Test**:
  1. Open video player and monitor "Expires in: X seconds" display
  2. Wait for first auto-refresh (55 minutes)
  3. Verify countdown resets to ~60 minutes and continues counting down
  4. Check browser dev tools for memory leaks (Performance > Memory)
  5. Verify only one countdown interval is running (use Performance profiler)

- **Long Session Test**:
  1. Leave video player open for 2+ hours
  2. Verify URL refreshes multiple times without issues
  3. Check browser memory usage remains stable
  4. Verify playback stays smooth throughout session

**Technical Notes**:
- Video `loadedmetadata` event fires when new source has loaded enough metadata for seeking
- `clearInterval()` is safe to call even if interval was already cleared
- Refs persist across renders, making them ideal for cleanup tracking
- Auto-refresh timing: Default 60min expiry with 5min refresh buffer = refresh at 55min mark

---END---
