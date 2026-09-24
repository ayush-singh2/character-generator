"""Log the chimera-repair R&D journey to MLflow — one richly-documented RUN per
version, so a mentor can understand each version end-to-end.

Each version's own directory (mlruns/<exp>/<run>/) holds:
  params : version, family, backend, MODEL (the model used), mentor_suggested, status
  metrics: cost_usd, anatomy_score, characters_present / _expected
  artifacts/
      input/        input image(s) fed to the model
      output/       resulting image
      code/         EVERY code snippet/function that this version's pipeline used
                    (real source via inspect.getsource where it lives in a module)
      code.md       all those snippets combined, in order
      prompt.txt    exact prompt / instruction
      narrative.md  DEVLOG-level detail: goal, hypothesis, models, files, steps,
                    result, why it failed, what we learned, what it led to
  description : the narrative, shown on the MLflow UI run page

Run:  MLFLOW_ALLOW_FILE_STORE=true python -m pipeline.mlflow_journey
UI :  MLFLOW_ALLOW_FILE_STORE=true mlflow ui --backend-store-uri file:./mlruns
"""

import inspect
import os
import shutil
import tempfile

os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
import mlflow  # noqa: E402

from . import (anatomy_v8, blocking_v8, editor, fal_backend,  # noqa: E402
               fal_repair)

BK = "books/namaste-ferdinand/v3_kimi"
BLK = f"{BK}/output/blocking"
REFS = f"{BK}/refs"
ORIG = f"{BK}/output/art_prebodyplan/page_23.png"
EXPERIMENT = "namaste-chimera-repair"


def src(fn):
    """Real source of a function, as a labelled code snippet."""
    return (f"{fn.__module__}.{fn.__name__}", inspect.getsource(fn))


# ------------------------------------------------------------------ the journey
# code: list of snippets, each either src(fn) (real module source) or
#       ("label", "literal code string") for inline scripts we ran.
M = [

dict(v="v00_original_gemini", title="One-shot Gemini render (the defect appears)",
     family="baseline", mentor=False, backend="gemini",
     model="google/gemini-3-pro-image",
     models="image: google/gemini-3-pro-image (via OpenRouter) | text: "
            "moonshotai/kimi-k2.6 | audit: anthropic/claude-sonnet-4.5",
     files=["generate_v7.generate", "editor.generate_with_refs"],
     cost=0.0, anatomy=0, chars=5, status="fail",
     inputs=[], output=ORIG,
     goal="Produce page 23 the normal way and see the defect.",
     hypothesis="The standard pipeline (multi-reference Gemini) can draw the whole "
                "page correctly from the scene text + character sheets.",
     steps=["generate_v7 builds a prompt from scene + character locked-specs",
            "Gemini renders the full page in ONE call from the reference sheets",
            "gate/audit scores the page"],
     prompt="(scene prompt) Yoga studio; Ferdinand, Boaris, Twiggy, Wooliam, Tallia "
            "doing poses; render faithfully from each character's reference sheet.",
     code=[("call", "from pipeline import generate_v7\n"
            "generate_v7.generate(only=['23'])   # -> output/art/page_23.png"),
           src(editor.generate_with_refs)],
     result="All 5 animals present and integrated, BUT the zebra is a chimera: a "
            "bipedal torso fused with a full four-legged zebra body ('6 legs').",
     why="The generator decides body layout itself; with 5 animals it fused two "
         "body plans. Text can't reliably constrain anatomy/counting.",
     learning="The base art is GOOD (integrated, not pasted) — only one localized "
              "defect. Reframes the problem: fix the defect, don't rebuild.",
     led_to="v01 — constrain layout with a blocking image."),

dict(v="v01_colored_blocking", title="Colored silhouette blocking (mentor #4)",
     family="A", mentor=True, backend="gemini", model="google/gemini-3-pro-image",
     models="image edit: google/gemini-3-pro-image (editor.edit / _openrouter_edit)",
     files=["blocking_v8.build_blocking", "blocking_v8._capsule", "editor.edit"],
     cost=0.4, anatomy=None, chars=5, status="fail",
     inputs=[f"{BLK}/page_23.png"], output=f"{BLK}/page_23_blocktest.png",
     goal="Stop the fusion by giving the model an explicit layout map.",
     hypothesis="If each character gets its own colored capsule at a fixed "
                "position, the model can't merge or duplicate bodies.",
     steps=["Draw one bold colored capsule per character from the layout boxes",
            "Add a text-band rectangle",
            "Feed blocking + character sheets to Gemini with 'follow the guide'"],
     prompt="Follow the color blocking image: each coloured capsule is ONE "
            "character standing upright; single upright body, two legs two arms, "
            "never a four-legged body.",
     code=[src(blocking_v8.build_blocking), src(blocking_v8._capsule),
           src(editor.edit), src(editor._openrouter_edit)],
     result="Chimera reduced, but bold capsule COLORS bled through as ghost-ovals.",
     why="Gemini is an editing model — it PRESERVES input content. Bold colors "
         "read as real objects to keep, not as hints.",
     learning="Layout idea works; colors are the problem — make them faint.",
     led_to="v02 — same map in faint grey."),

dict(v="v02_faint_blocking", title="Faint grey blocking (halos fixed)",
     family="A", mentor=True, backend="gemini", model="google/gemini-3-pro-image",
     models="image edit: google/gemini-3-pro-image",
     files=["blocking_v8.build_blocking", "blocking_v8._faint",
            "blocking_v8._min_size", "editor.edit"],
     cost=0.4, anatomy=100, chars=5, status="partial",
     inputs=[f"{BLK}/page_23_faint.png"], output=f"{BLK}/page_23_faint_test.png",
     goal="Keep layout guidance but stop the color halos.",
     hypothesis="Near-white grey capsules read as position HINTS to paint over, "
                "not colored objects to preserve.",
     steps=["build_blocking(faint=True) -> near-white grey capsules",
            "Feed to Gemini with 'grey shapes are a layout guide, paint over them'"],
     prompt="The grey capsules are a LAYOUT GUIDE; paint characters at those "
            "positions as single upright bodies; keep bottom band for text.",
     code=[src(blocking_v8._faint), src(blocking_v8._min_size),
           src(blocking_v8.build_blocking)],
     result="Halos gone, anatomy coherent (100) — but the studio BACKGROUND came "
            "out blank.",
     why="We fed only blocking + character sheets, not the room reference.",
     learning="Blocking fixes anatomy+layout but we must also supply the setting.",
     led_to="v03 — add the studio reference plate."),

dict(v="v03_faint_plus_setting", title="Faint blocking + setting reference",
     family="A", mentor=True, backend="gemini", model="google/gemini-3-pro-image",
     models="image edit: google/gemini-3-pro-image",
     files=["blocking_v8.generate_blocked", "blocking_v8._setting_ref",
            "editor.edit"],
     cost=0.4, anatomy=100, chars=4, status="partial",
     inputs=[f"{BLK}/page_23_faint.png", f"{REFS}/setting_yoga_studio.png"],
     output=f"{BLK}/page_23_setaware.png",
     goal="Restore the background while keeping the anatomy fix.",
     hypothesis="Feeding studio plate + blocking + character sheets gives where + "
                "who + scene, enough for a full correct page.",
     steps=["Look up the scene's setting_key -> setting_yoga_studio.png",
            "Feed [blocking, setting plate, character sheets] to Gemini"],
     prompt="Render the full setting from the setting reference behind the "
            "characters; follow the grey layout guide; single upright bodies.",
     code=[src(blocking_v8._setting_ref), src(blocking_v8.generate_blocked)],
     result="Background restored, anatomy 100 — but DROPPED Twiggy (zebra), 4/5.",
     why="Small/crowded capsules get under-rendered; the model skipped the "
         "smallest figure.",
     learning="Need minimum figure size + explicitly named cast.",
     led_to="v04 — min capsule size + named roster."),

dict(v="v04_setaware_minsize_namedcast", title="Min size + named cast (over-corrects)",
     family="A", mentor=True, backend="gemini", model="google/gemini-3-pro-image",
     models="image edit: google/gemini-3-pro-image",
     files=["blocking_v8._min_size", "blocking_v8.generate_blocked"],
     cost=0.4, anatomy=100, chars=6, status="fail",
     inputs=[f"{BLK}/page_23_faint.png"], output=f"{BLK}/page_23_setaware2.png",
     goal="Guarantee every character appears exactly once.",
     hypothesis="Minimum capsule size + explicit 'all 5 must appear' roster stops "
                "omissions.",
     steps=["_min_size grows tiny boxes to a floor (MIN_W/MIN_H)",
            "Instruction names all 5 and says 'do not omit or merge'"],
     prompt="ALL 5 characters MUST appear, each once: Ferdinand, Boaris, Twiggy, "
            "Wooliam, Tallia. Do not omit or merge any.",
     code=[src(blocking_v8._min_size), src(blocking_v8.generate_blocked)],
     result="All 5 appear, but ADDED a duplicate pig (6 figures); still pasted.",
     why="Prompt + blocking SUGGEST count; can't HARD-LOCK it on Gemini. Push on "
         "'missing' -> get 'duplicate'. Ceiling of Family A.",
     learning="Layout-forcing on Gemini can't guarantee exact cast or kill the "
              "pasted look. Try building in layers.",
     led_to="v05 — layered compositing on fal/Flux."),

dict(v="v05_fal_background_plate", title="fal/Flux background plate (mentor #3)",
     family="B", mentor=True, backend="fal-flux", model="fal-ai/flux/dev",
     models="text-to-image: fal-ai/flux/dev",
     files=["fal_backend.text_to_image"],
     cost=0.03, anatomy=None, chars=0, status="success",
     inputs=[], output=f"{BLK}/fal_plate_p23.png",
     goal="Build the empty room as a clean base; test Flux style vs approved look.",
     hypothesis="A character-free plate is easy and gives a correct background to "
                "place characters onto.",
     steps=["Call fal flux/dev with 'empty studio, no characters'",
            "Download the plate"],
     prompt="Empty bright yoga studio: wooden floor, windows, plants, candle "
            "shelf, mats. NO characters. Soft watercolour, calm floor for text.",
     code=[src(fal_backend.text_to_image)],
     result="Excellent empty studio; Flux watercolour matches the approved style "
            "(style risk LOW).",
     why="No failure — solid foundation.",
     learning="fal/Flux is viable style-wise; the plate step is reliable.",
     led_to="v06 — place a character into the plate with IP-Adapter."),

dict(v="v06_plate_ipadapter_inpaint", title="IP-Adapter inpaint into plate (mentor #1)",
     family="B", mentor=True, backend="fal-flux",
     model="fal-ai/flux-general/inpainting + InstantX/FLUX.1-dev-IP-Adapter",
     models="inpaint: fal-ai/flux-general/inpainting | IP-Adapter: "
            "InstantX/FLUX.1-dev-IP-Adapter | encoder: google/siglip-so400m-patch14-384",
     files=["fal_backend.inpaint", "fal_backend.make_mask"],
     cost=0.15, anatomy=None, chars=0, status="fail",
     inputs=[f"{BLK}/fal_plate_p23.png", f"{REFS}/ferdinand.png"],
     output=f"{BLK}/fal_inpaint_fer_p23.png",
     goal="Paint ONE character into its box, identity locked by IP-Adapter.",
     hypothesis="IP-Adapter conditions the masked region on a reference image, so "
                "one-at-a-time placement avoids cross-character bleed.",
     steps=["Mask over the character's layout box on the plate",
            "flux-general/inpainting with ip_adapters = Ferdinand's sheet"],
     prompt="A cream goat standing upright in his box; IP-Adapter on ferdinand.png; "
            "inpaint the masked region only.",
     code=[src(fal_backend.make_mask), src(fal_backend.inpaint)],
     result="Masked region came back a WHITE BLOCK / no coherent character.",
     why="Inpainting into an EMPTY plate region gives no surrounding context to "
         "build a figure on; IP-Adapter conditions identity but can't conjure a "
         "body from blank space.",
     learning="Inpainting works best repairing WITHIN existing content, not into a "
              "void.",
     led_to="v07 — paste then harmonize instead."),

dict(v="v07_harmonize_img2img_sweep", title="img2img harmonization sweep (mentor #3)",
     family="B", mentor=True, backend="fal-flux",
     model="fal-ai/flux-general/image-to-image",
     models="img2img: fal-ai/flux-general/image-to-image (strength sweep 0.4-0.7)",
     files=["fal_client.subscribe (inline sweep)"],
     cost=0.30, anatomy=None, chars=5, status="fail",
     inputs=[f"{BLK}/page_23_setaware2.png"], output=f"{BLK}/fal_harm_p23_s60.png",
     goal="Blend the pasted composite into one cohesive painting.",
     hypothesis="A low-denoise img2img pass unifies lighting/grain (removes pasted "
                "look) while keeping the characters.",
     steps=["Take the pasted Gemini composite as init",
            "Run flux img2img at strength 0.4 / 0.5 / 0.6 / 0.7"],
     prompt="One cohesive watercolour yoga-studio scene, five upright animal "
            "friends, unified lighting, not pasted. (denoise sweep 0.4-0.7)",
     code=[("img2img_sweep",
            "for s in (0.4, 0.5, 0.6, 0.7):\n"
            "    r = fal_client.subscribe('fal-ai/flux-general/image-to-image',\n"
            "        arguments={'image_url': init_url, 'prompt': prompt,\n"
            "                   'strength': s, 'num_inference_steps': 36,\n"
            "                   'image_size': 'square_hd', 'num_images': 1})\n"
            "    open(f'fal_harm_p23_s{int(s*100)}.png','wb').write(\n"
            "        requests.get(r['images'][0]['url']).content)")],
     result="0.4-0.5 still pasted; 0.6 cohesive but shifting; 0.7 beautiful but "
            "characters re-invented into generic animals.",
     why="Denoise<->identity tension: without an identity anchor, 'blend more' = "
         "'drift more'. No strength both blends AND preserves identity.",
     learning="Rebuilding/harmonizing the whole page trades away consistency. Fix "
              "ONLY the defect instead.",
     led_to="v08 — surgical masked repair of just the zebra."),

dict(v="v08_masked_inpaint_plain", title="Masked repair of the zebra (safety glitch)",
     family="C", mentor=True, backend="fal-flux",
     model="fal-ai/flux-general/inpainting",
     models="inpaint: fal-ai/flux-general/inpainting (strength 0.9)",
     files=["fal_backend.make_mask", "fal_backend.inpaint"],
     cost=0.05, anatomy=None, chars=None, status="fail",
     inputs=[ORIG], output=f"{BLK}/fal_fixzebra_s90.png",
     goal="Fix only the zebra region of the GOOD original, freeze the rest.",
     hypothesis="A mask over the zebra lets the model repaint only that area; the "
                "rest is preserved pixel-for-pixel.",
     steps=["Mask the zebra region (white=repaint, black=keep)",
            "fal flux-general/inpainting, strength 0.9"],
     prompt="A striped zebra standing upright, two legs two arms, watercolour; "
            "inpaint the masked zebra region.",
     code=[src(fal_backend.make_mask), src(fal_backend.inpaint)],
     result="Returned an ALL-BLACK image.",
     why="fal's safety checker intermittently blacks out benign images.",
     learning="Disable safety checker + guard on mean-pixel<8.",
     led_to="v09 — retry with safety off."),

dict(v="v09_masked_inpaint_safetyoff", title="Masked repair, safety off (text-only)",
     family="C", mentor=True, backend="fal-flux",
     model="fal-ai/flux-general/inpainting",
     models="inpaint: fal-ai/flux-general/inpainting (enable_safety_checker=False)",
     files=["fal_backend.inpaint"],
     cost=0.05, anatomy=None, chars=None, status="fail",
     inputs=[ORIG], output=f"{BLK}/fal_fixzebra_safeoff.png",
     goal="Get a real (non-black) inpaint of the zebra region.",
     hypothesis="With the checker off, a text prompt 'a zebra' repaints the region "
                "correctly.",
     steps=["Same mask", "inpaint with enable_safety_checker=False, text prompt"],
     prompt="A striped zebra standing upright in yoga clothes; inpaint masked "
            "region. enable_safety_checker=False.",
     code=[src(fal_backend.inpaint)],
     result="Real image, but the region became a blank EASEL, not a zebra.",
     why="A bare text prompt can't reconstruct the SPECIFIC character; studio "
         "context hijacked the fill into furniture.",
     learning="Need identity conditioning (IP-Adapter on the zebra's sheet).",
     led_to="v10 — add IP-Adapter."),

dict(v="v10_masked_inpaint_ipadapter", title="Masked repair + IP-Adapter (erases neighbour)",
     family="C", mentor=True, backend="fal-flux",
     model="fal-ai/flux-general/inpainting + InstantX/FLUX.1-dev-IP-Adapter",
     models="inpaint: fal-ai/flux-general/inpainting | IP-Adapter: "
            "InstantX/FLUX.1-dev-IP-Adapter (twiggy sheet, scale 0.9)",
     files=["fal_backend.make_mask", "fal_backend.inpaint"],
     cost=0.07, anatomy=100, chars=4, status="fail",
     inputs=[ORIG, f"{REFS}/twiggy.png"], output=f"{BLK}/fal_fixzebra_ip.png",
     goal="Repair the zebra region AS Twiggy (mask=where, IP-Adapter=who).",
     hypothesis="Mask + IP-Adapter on Twiggy's sheet paints the right zebra in the "
                "right place.",
     steps=["Mask box [0.60-0.97]", "inpaint + ip_adapters=twiggy, strength 0.85"],
     prompt="A single upright striped zebra like the reference; IP-Adapter on "
            "twiggy.png; inpaint masked zebra region.",
     code=[("call",
            "zebra_box = [0.60, 0.33, 0.97, 0.90]        # TOO WIDE\n"
            "mask = fal_backend.make_mask((W,H), zebra_box)\n"
            "fal_backend.inpaint(original, mask, prompt,\n"
            "    ip_adapter_ref=open(f'{REFS}/twiggy.png','rb').read(),\n"
            "    ip_scale=0.9, strength=0.85)   # box overlapped giraffe -> erased"),
           src(fal_backend.inpaint)],
     result="Zebra fixed, but the giraffe (Tallia) VANISHED — 4/5 cast.",
     why="Mask box too wide — overlapped the giraffe's region, so the inpaint "
         "repainted (deleted) Tallia.",
     learning="Masks must be NEIGHBOUR-SAFE.",
     led_to="v11 — tight hand-placed mask on only the extra part."),

dict(v="v11_erase_extra_body_manual", title="ERASE only the extra body (best masked result)",
     family="C", mentor=True, backend="fal-flux",
     model="fal-ai/flux-general/inpainting",
     models="inpaint: fal-ai/flux-general/inpainting (strength 0.95, no IP-Adapter)",
     files=["fal_backend.make_mask", "fal_backend.inpaint"],
     cost=0.05, anatomy=100, chars=5, status="success",
     inputs=[ORIG], output=f"{BLK}/fal_erase_extrabody.png",
     goal="Remove the anomaly while keeping the real zebra 100% intact.",
     hypothesis="The zebra = good bipedal front + separate extra hindquarters. Mask "
                "ONLY the extra hindquarters, fill with background -> real zebra "
                "untouched (zero drift).",
     steps=["Hand-draw a TIGHT mask over only the extra hindquarters [0.86-0.99]",
            "inpaint that region to 'floor + plant' background"],
     prompt="Clean empty wooden studio floor + plant, no animal here (inpaint ONLY "
            "the tight extra-hindquarters box).",
     code=[("call",
            "extra_box = [0.86, 0.42, 0.99, 0.88]        # ONLY the extra part\n"
            "mask = fal_backend.make_mask((W,H), extra_box, feather=6)\n"
            "fal_backend.inpaint(original, mask,\n"
            "    'clean wooden studio floor and plant, no animal, no extra legs',\n"
            "    strength=0.95)"),
           src(fal_backend.make_mask), src(fal_backend.inpaint)],
     result="Chimera gone, zebra AND giraffe preserved, 5/5, anatomy 100. Best "
            "masked result.",
     why="Worked — but required a HUMAN to place the precise mask on the separable "
         "extra part. Not automatic.",
     learning="ERASE-the-separable-part is identity-safe; blocker is AUTO-locating "
              "that part.",
     led_to="v12 — automate detect -> mask -> repair."),

dict(v="v12_auto_mask_wrapper", title="Auto-mask + repair wrapper (fused case fails)",
     family="C", mentor=True, backend="fal-flux",
     model="fal-ai/flux-general/inpainting (+ anthropic/claude-sonnet-4.5 detect)",
     models="inpaint: fal-ai/flux-general/inpainting | detection/anomaly-locate: "
            "anthropic/claude-sonnet-4.5 (VISION_MODEL) | IP-Adapter on REDRAW",
     files=["fal_repair.repair_page", "fal_repair.repair_defect",
            "fal_repair._clip_to_neighbors", "fal_repair._is_erase",
            "anatomy_v8.locate_anomaly"],
     cost=1.0, anatomy=100, chars=4, status="fail",
     inputs=[ORIG], output=f"{BK}/output/art_repaired/page_23.png",
     goal="Turn v10/v11 into an automatic, reusable repair pass.",
     hypothesis="Detect defect box -> auto neighbour-safe mask -> classify ERASE vs "
                "REDRAW -> inpaint -> re-audit -> revert if worse.",
     steps=["Multi-pass anatomy detection (stochastic, so retry)",
            "locate_anomaly boxes the extra part; _clip_to_neighbors shrinks it",
            "ERASE to background or REDRAW with IP-Adapter",
            "re-audit; revert if defect count rises"],
     prompt="(auto) ERASE extra part to background, OR REDRAW single upright "
            "{species} with IP-Adapter, per classification.",
     code=[src(fal_repair._is_erase), src(fal_repair._clip_to_neighbors),
           src(anatomy_v8.locate_anomaly), src(fal_repair.repair_defect),
           src(fal_repair.repair_page)],
     result="Ran end-to-end; on the FUSED chimera it either erased the whole zebra "
            "(->plant) or redrew it into a 'cat'. 4/5 cast.",
     why="A fused chimera has NO clean seam; locate_anomaly boxes the whole figure. "
         "Masking needs a separable defect.",
     learning="Masking is the wrong tool for a FUSED defect. Need an editor that "
              "localizes by MEANING.",
     led_to="v13 — instruction-based editing (FLUX Kontext)."),

dict(v="v13_flux_kontext_instruction", title="FLUX Kontext instruction edit (our idea; best overall)",
     family="C", mentor=False, backend="fal-kontext",
     model="fal-ai/flux-pro/kontext/max/multi",
     models="instruction editor: fal-ai/flux-pro/kontext/max/multi (image + "
            "reference + written edit instruction)",
     files=["fal_client.subscribe (Kontext, inline)"],
     cost=0.05, anatomy=None, chars=5, status="partial",
     inputs=[ORIG, f"{REFS}/twiggy.png"], output=f"{BLK}/kontext_fix_p23.png",
     goal="Fix the fused chimera without a mask or denoise dial.",
     hypothesis="An instruction-based editor (image + reference + written fix) "
                "localizes by UNDERSTANDING, so no clean mask seam or strength "
                "setting is needed.",
     steps=["Feed [error page, Twiggy reference] to FLUX Kontext multi",
            "Written instruction: fix only the zebra, keep the rest"],
     prompt="Fix ONLY the striped zebra (chimera with an extra body/legs): make it "
            "a single upright bipedal zebra like the reference; keep the giraffe, "
            "pig, goat, sheep and studio unchanged.",
     code=[("kontext_call",
            "err_url = fal_client.upload_file(original_page)\n"
            "ref_url = fal_client.upload_file(f'{REFS}/twiggy.png')\n"
            "r = fal_client.subscribe('fal-ai/flux-pro/kontext/max/multi',\n"
            "    arguments={'prompt': 'Fix ONLY the striped zebra ... keep the rest "
            "unchanged',\n"
            "               'image_urls': [err_url, ref_url],\n"
            "               'num_images': 1, 'guidance_scale': 3.5})\n"
            "open('kontext_fix_p23.png','wb').write(\n"
            "    requests.get(r['images'][0]['url']).content)")],
     result="BEST result: cohesive, NOT pasted, all 5 present, correct watercolour "
            "style, 14s / ~$0.05.",
     why="Redrew the WHOLE scene (composition/poses changed) and the zebra came out "
         "half-cut at the frame edge — a framing/instruction issue, far more "
         "fixable than the fundamental walls the other methods hit.",
     learning="Instruction-based editing is the RIGHT class of tool; remaining "
              "issues are prompt/framing tuning.",
     led_to="v14 — tune Kontext for framing + composition preservation."),

dict(v="v14_next_kontext_tuned", title="NEXT: tuned Kontext (planned)",
     family="C", mentor=False, backend="fal-kontext",
     model="fal-ai/flux-pro/kontext/max/multi (planned)",
     models="instruction editor: fal-ai/flux-pro/kontext/max/multi | verify: "
            "anthropic/claude-sonnet-4.5 (anatomy/cast detector)",
     files=["(planned) fal_client.subscribe (Kontext)", "anatomy_v8.audit_anatomy"],
     cost=0.0, anatomy=None, chars=None, status="planned",
     inputs=[], output=None,
     goal="Make Kontext keep all cast fully in-frame + preserve composition, then "
          "verify cross-page consistency and wire it into the pipeline.",
     hypothesis="A tighter instruction (keep all in-frame, preserve composition, "
                "change only the zebra) + verification turns v13's near-miss into a "
                "shippable page.",
     steps=["Kontext edit with framing + preservation constraints",
            "Re-verify with the anatomy/cast detector once the vision API recovers",
            "Wire Kontext as the repair engine inside fal_repair",
            "Test cross-page consistency with shared references"],
     prompt="(planned) Fix the defect only; keep composition and ALL characters "
            "fully within the frame; do not crop any character.",
     code=[("planned",
            "# fal_client.subscribe('fal-ai/flux-pro/kontext/max/multi', arguments={\n"
            "#   'prompt': '... keep all characters fully in frame, preserve "
            "composition ...',\n"
            "#   'image_urls': [page, ref]})\n"
            "# then verify:"),
           src(anatomy_v8.audit_anatomy)],
     result="(planned — not yet run)",
     why="(planned — not yet run)",
     learning="(pending)",
     led_to="(the shippable repair pass)"),
]


def _combined_code(m):
    parts = []
    for i, (label, code) in enumerate(m["code"], 1):
        parts.append(f"# ---- [{i}] {label} " + "-" * (60 - len(label)) + "\n"
                     + code.rstrip() + "\n")
    return "\n".join(parts)


def _narrative(m):
    def block(t, b):
        return f"## {t}\n{b}\n\n"
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(m["steps"], 1)) or "-"
    files = "\n".join(f"- `{f}`" for f in m["files"]) or "-"
    head = (f"# {m['v']} — {m['title']}\n\n"
            f"**status:** {m['status']}  |  **family:** {m['family']}  |  "
            f"**mentor-suggested:** {m['mentor']}  |  **model:** `{m['model']}`  |  "
            f"**cost:** ~${m['cost']:.2f}  |  **anatomy:** {m['anatomy']}  |  "
            f"**cast:** {m['chars']}/5\n\n")
    return (head
            + block("Goal", m["goal"])
            + block("Hypothesis (why we thought it would work)", m["hypothesis"])
            + block("Models used", m["models"])
            + block("Source files / functions involved", files)
            + block("What we did", steps)
            + block("Prompt / instruction", m["prompt"])
            + block("Code — all snippets this pipeline used",
                    "```python\n" + _combined_code(m) + "\n```")
            + block("Result", m["result"])
            + block("Why it fails / caveat", m["why"])
            + block("What we learned", m["learning"])
            + block("Led to", m["led_to"]))


def _log_text(name, content, artifact_path=None):
    d = tempfile.mkdtemp()
    p = os.path.join(d, os.path.basename(name))
    with open(p, "w") as f:
        f.write(content)
    mlflow.log_artifact(p, artifact_path=artifact_path)


def main():
    tracking = f"file:{os.path.abspath('mlruns')}"
    mlflow.set_tracking_uri(tracking)
    client = mlflow.tracking.MlflowClient()
    exp = client.get_experiment_by_name(EXPERIMENT)
    if exp:
        client.delete_experiment(exp.experiment_id)
        for pth in (os.path.join("mlruns", ".trash", exp.experiment_id),
                    os.path.join("mlruns", exp.experiment_id)):
            if os.path.isdir(pth):
                shutil.rmtree(pth, ignore_errors=True)
    mlflow.set_experiment(EXPERIMENT)

    for m in M:
        with mlflow.start_run(run_name=m["v"]):
            mlflow.log_params({"version": m["v"], "family": m["family"],
                               "model": m["model"], "backend": m["backend"],
                               "mentor_suggested": m["mentor"],
                               "status": m["status"]})
            mlflow.log_metric("cost_usd", m["cost"])
            if m["anatomy"] is not None:
                mlflow.log_metric("anatomy_score", m["anatomy"])
            if m["chars"] is not None:
                mlflow.log_metric("characters_present", m["chars"])
                mlflow.log_metric("characters_expected", 5)
            mlflow.set_tag("core_idea", m["goal"])
            mlflow.set_tag("why_fails", m["why"])
            mlflow.set_tag("mlflow.note.content", _narrative(m))
            # images
            for s in m["inputs"]:
                if os.path.exists(s):
                    mlflow.log_artifact(s, artifact_path="input")
            if m["output"] and os.path.exists(m["output"]):
                mlflow.log_artifact(m["output"], artifact_path="output")
            # text artifacts
            _log_text("prompt.txt", m["prompt"])
            _log_text("narrative.md", _narrative(m))
            _log_text("code.md",
                      f"# {m['v']} — all code snippets used\n\n"
                      "```python\n" + _combined_code(m) + "\n```\n")
            # each snippet as its own file under code/
            for i, (label, code) in enumerate(m["code"], 1):
                safe = "".join(c if c.isalnum() else "_" for c in label)[:40]
                _log_text(f"{i:02d}_{safe}.py", code.rstrip() + "\n",
                          artifact_path="code")
            print(f"logged {m['v']:34s} model={m['model'][:28]:28s} "
                  f"${m['cost']:.2f} [{m['status']}]  {len(m['code'])} snippets")

    print(f"\nTotal image-gen cost (est): ${sum(x['cost'] for x in M):.2f}")
    print(f"UI: MLFLOW_ALLOW_FILE_STORE=true mlflow ui --backend-store-uri {tracking}")


if __name__ == "__main__":
    main()
