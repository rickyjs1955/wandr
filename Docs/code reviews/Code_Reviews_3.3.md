Findings:
- `backend/app/cv/embedding_extractor.py:92-103` (also benchmark data in `backend/scripts/benchmark_embedding_extraction.py:198-235`) – The extractor still ships with a Xavier-initialized 512→128 projection and no mandatory PCA/pretrained weights. Benchmarks show “different outfit” similarity ≈ 0.89, far above the ≤ 0.50 target, so the embeddings barely separate identities. As-is we’re emitting vectors that won’t work for re-ID; please either enforce the PCA init path (e.g. require sample crops before use) or drop to the raw 512D CLIP features until a trained projection is in place.
- `backend/app/cv/garment_analyzer.py:205-228` – Because the analyzer calls the extractor unconditionally (default `extract_embeddings=True`), every worker will try to download and load CLIP weights at construction time. In our current restricted/no-network deploy environments that will fail outright, and even where downloads succeed we pay the GPU/CPU memory hit on every Celery worker, including ones that only need color/type data. Consider deferring initialization (toggle defaults, lazy load, or env guard) so we don’t brick non-networked workers.

Questions:
- What is the concrete plan to supply PCA/pretrained weights so we hit the discriminability numbers before Phase 4? Do we have a dataset identified and a ticket to run the init, or should we switch back to 512D CLIP features for now?

---SEPARATOR---
Fix Review:
- `backend/app/cv/embedding_extractor.py:68-124` – ✅ default now returns raw 512D CLIP vectors unless you pass pretrained weights; that addresses the discriminability concern.
- `backend/app/cv/garment_analyzer.py:100-148` – ✅ embedding extraction is off by default and lazily instantiated, so non-networked workers won’t choke on CLIP downloads.
- ✅ Question answered: plan is to stick with 512D CLIP until PCA/pretrained weights are sourced; optional PCA path remains available.

New Issues:
- `backend/app/cv/embedding_extractor.py:230-257` – `extract_batch` still unconditionally calls `self.projection(features)`. When we’re in the new raw-CLIP default (`self.projection` is `None`, `use_projection=False`), this throws `'NoneType' object is not callable`. Need to branch just like `extract()` and skip projection when it’s disabled.

---SEPARATOR---

Second Fix Review:
- `backend/app/cv/embedding_extractor.py:255-259` – ✅ `extract_batch` now conditionally applies projection, matching `extract()` behavior. Raw CLIP mode (projection=None) works correctly and returns (N, 512) embeddings.
- ✅ Docstring updated to reflect variable output dimensions based on mode.
- ✅ Tested: batch extraction works in both raw CLIP mode and projection mode.

**All Issues Resolved**: Phase 3.3 is now fully complete and ready for Phase 4.

---SEPARATOR---

- `backend/app/cv/embedding_extractor.py:200-259` – ✅ batch path now mirrors the single-image logic and returns 512D arrays in raw mode; no more `NoneType` crashes.
- ✅ Storage helpers were updated to handle variable-length embeddings (`serialize_embedding`/`deserialize_embedding` use dynamic format strings).

No additional issues spotted.

---END---