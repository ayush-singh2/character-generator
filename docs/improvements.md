# Development Improvements — Picture-Book Generator

The `DEVLOG.md` reveals a classic progression in applied generative AI, moving from prompt engineering to pixel-level compositing, and finally to an agentic validation loop.

## Current state of the Pipeline

* **The "Generate, Audit, Repair" Trap:** The current state (`v8.3`) relies on a multi-reference Gemini generator backed by an expensive Vision Language Model (VLM) audit loop. While this brute-forces consistency through majority-vote VLM probes and zoom crops, scaling it to a full book causes API costs and latency to explode.

## Analysis of the Pipeline Trajectory

The pipeline's evolution highlights the fundamental tension between consistency and generation cost:

* **The Contamination Problem:** Early text-to-image attempts (`v1.x`) suffered from cross-character contamination. Diffusion models averaged multiple subjects, resulting in Bilbo and Obi losing their distinct traits.
* **The Rigidity Trade-off:** Layered compositing (`v2.0`) solved identity drift by reusing exact sprites. However, it failed because the resulting illustrations looked rigidly "pasted" rather than naturally painted.
* **The LoRA Ceiling:** Training individual character LoRAs (`v6.0`) worked in isolation but broke down in multi-character scenes. This failure was due to weight interference and prompt dilution.

## State-of-the-Art in Multi-Subject Consistency (2024–2026)

Recent research has shifted away from post-generation repair and LoRA stacking, focusing instead on training-free attention-steering at inference time:

* **Consistent Self-Attention (e.g., StoryDiffusion):** These methods batch-generate images and share self-attention maps across frames. A character established in the first frame maintains exact features in subsequent frames without fine-tuning.
* **Shared Subject Activations (e.g., ConsiStory):** This approach isolates subject patches and injects correspondence-based features across the generation batch. It prevents the layout collapse typical of naive attention-sharing and naturally extends to multi-subject scenarios without optimization.
* **Regional Adapters (e.g., Character-Adapter, IP-Adapter):** Instead of passing a single "stitched" reference image that the model might average, modern adapters inject visual features from multiple reference images strictly into targeted spatial bounding boxes during the diffusion process.

## Recommended Engineering Approach

To achieve scalable consistency while driving down regeneration costs, the architecture must transition from *post-hoc repair* to *correct-by-construction* generation.

* **Decouple Identity via Regional Prompting:** Replace lengthy textual identity locks and stitched reference sheets with an image-prompt adapter (like IP-Adapter) paired with Regional Prompting. By feeding the layout boxes from your `stage_v3.py` director into the cross-attention layers as spatial masks, you physically prevent cross-character feature bleed at the tensor level.
* **Implement Cross-Frame Attention Sharing:** Process book pages in overlapping batches using a Consistent Self-Attention mechanism. Inject the key/value pairs from your established `v8.0` "canon crops" directly into the current page's diffusion step, allowing the model to natively render character details without relying on the VLM to catch drifts later.
* **Pre-Gate with Deterministic Classifiers:** The `v8.3` audit runs a costly VLM call per character per axis. Introduce a zero-shot local classifier (e.g., SigLIP) as a pre-gate to verify bounding box occupancy, color histograms, and silhouette matches. Only escalate pages that pass this cheap local filter to the expensive Gemini multi-axis audit.

## Cost Optimization Strategy

* **Proactive Negative Space:** The edge-energy search (`v1.4`) and `_locate_figures` (`v7.8`) require generating the full art before checking text placement. Instead, use a layout ControlNet to pass the text bounding box as a negative mask during the initial noise generation. This forces the model to leave that area diegetically calm on the first try, eliminating "band occupied" VLM retries.
* **Latent Inpainting over Rerolling:** Rerolling an entire image for a missing watch (`v1.3`) or headband wastes compute. Ensure the diagnostic repair uses localized latent inpainting with the regional adapter to fix point-defects, strictly masking the area defined by the VLM zoom crop.

## Architectural Boundaries

Integrating advanced diffusion controls requires acknowledging a hard architectural boundary.

To execute this on a scalable platform, you must split the control plane from the image plane. Keep OpenRouter for the cognitive tasks: manuscript parsing, layout staging via `stage_v3.py`, and the VLM audit loops. Route the actual pixel generation to a Diffusers-based backend where you have absolute control over the inference pipeline.

Spinning up dedicated GPU hardware—such as those Hetzner bare-metal servers—running a containerized ComfyUI or FastAPI Diffusers wrapper is the most cost-effective path for high-volume book production. You can wire this new worker into your existing GitHub Actions CI gates to manage automated package updates and deployments.

Here is the exact path to integrate these two systems.

1. **Deploy the Image Worker:** Infrastructure.
Containerize a Diffusers pipeline with IP-Adapter and ControlNet loaded into memory. Expose a `/generate` endpoint that accepts layout coordinates, reference images, and prompt text. Verify this step by sending a mock layout JSON from your main app and ensuring the GPU worker returns a generated image within expected latency limits.

2. **Implement Regional IP-Adapters:** Consistency.
Instead of appending dense textual locks to a Gemini prompt, map the bounding boxes from your layout director directly to spatial masks. Pass the approved character sheets (`group0.png`, etc.) into the IP-Adapter, binding their visual embeddings exclusively to their respective layout masks. Check the output tensor shapes in the logs to verify that the image features are strictly isolated to the correct coordinates.

3. **Enforce Negative Space via Masking:** Composition.
Convert the text zones defined by `compose_v3.py` into a binary mask. Pass this mask to a ControlNet or use latent noise manipulation during the initial diffusion steps to force low-frequency, calm generation in those specific areas. Verify success by running your existing `_band_occupied` edge-energy check on the output; the flag rate should drop to near zero on the first pass.

4. **Wire the Audit to Inpainting:** Cost Optimization.
When the OpenRouter VLM audit fails a specific attribute, take the bounding box from `audit_v8._zoom_crop` and send it back to the GPU worker's `/inpaint` endpoint alongside the targeted correction text. Verify success by re-running the VLM audit strictly on the newly inpainted crop to confirm the point-defect is resolved without altering the surrounding background.