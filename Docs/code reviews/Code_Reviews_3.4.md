Findings:
- `backend/app/cv/tracklet_generator.py:222-241` – `garment_analyzer.analyze(...)` is called with `extract_embeddings=self.extract_embeddings`, but `GarmentAnalyzer.analyze` only accepts the image parameter. This raises a `TypeError: analyze() got an unexpected keyword argument 'extract_embeddings'` the moment we hit a track, so the pipeline never makes it past the first frame. Drop the extra argument or plumb the flag through the analyzer API.
- `backend/app/cv/tracklet_generator.py:301-309` – Tracklet timing is bogus: `duration_sec` uses `track.time_since_update`, which is just the number of frames since the last detection, and both `t_in` and `t_out` are set to `current_timestamp`. Every finalized tracklet reports zero-length duration and identical in/out times. You need to derive timestamps from `track.frame_history` (scaled by the sample rate and anchored on the provided frame times) or pass the real timestamps through the appearance cache.

Questions:
- Do we already have a plan to persist per-frame timestamps so `t_in/t_out` can reflect real clock times, or should the generator take the sample rate and frame IDs to compute them for now?

---SEPARATOR---
Fix Review:
- `backend/app/cv/tracklet_generator.py:231` – ✅ removed the bad kwarg; analyzer runs without blowing up and still honors its internal `extract_embeddings` flag.
- `backend/app/cv/tracklet_generator.py:216-305` – ✅ appearance cache now keeps parallel `frame_ids` and real `timestamps`, and `_create_tracklet` derives `t_in/t_out/duration` from those values. Tracklets carry meaningful timing metadata again.

Nothing else blocking.
---END---
