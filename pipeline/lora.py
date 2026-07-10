"""Per-character LoRA fine-tuning on fal.ai — consistent AND naturally painted.

Diffusion redraws characters freehand (inconsistent); compositing reuses pixels
(consistent but pasted-looking). A LoRA fine-tuned per character gives BOTH: the
model actually LEARNS the character's identity, then paints it naturally into any
scene/pose. Needs a training service — this uses fal.ai (set FAL_KEY in .env).

Pipeline:
    prepare(name)  -> zip of that character's training images (atlas + refs)
    train(name)    -> fal flux-lora-fast-training -> LoRA weights url (cached in
                      data/loras.json with a unique trigger word)
    generate(prompt, [(name, scale), ...]) -> fal flux-lora inference with the
                      character LoRA(s) active + trigger words in the prompt
"""

import glob
import io
import json
import os
import zipfile

from PIL import Image

TRAIN_DIR = "output/lora_train"
MANIFEST = "data/loras.json"

# Unique, rare trigger tokens the LoRA binds the character identity to.
TRIGGERS = {
    "Bilbo": "bilbogldn",
    "Obi":   "obiamber",
    "Homer": "homerdrgn",
    "Mom":   "momchar",
    "Dad":   "dadchar",
}


def _training_images(name):
    slug = name.lower()
    imgs = []
    # Prefer the raw (pre-cutout) sprites — full character on a clean bg.
    imgs += sorted(glob.glob(f"output/assets/{slug}/*.raw.png"))
    # Plus the approved reference sheets (portrait + full body turnaround).
    for k in ("portrait", "full_body"):
        p = f"output/refs/{slug}/{k}.png"
        if os.path.exists(p):
            imgs.append(p)
    return imgs


def prepare(name):
    """Build a training-image zip for one character; returns the zip path."""
    os.makedirs(TRAIN_DIR, exist_ok=True)
    imgs = _training_images(name)
    if not imgs:
        raise RuntimeError(f"no training images for {name}")
    zip_path = os.path.join(TRAIN_DIR, f"{name.lower()}.zip")
    with zipfile.ZipFile(zip_path, "w") as z:
        for i, p in enumerate(imgs):
            im = Image.open(p).convert("RGB")            # flatten alpha on white
            buf = io.BytesIO()
            im.save(buf, "PNG")
            z.writestr(f"{name.lower()}_{i:02d}.png", buf.getvalue())
    print(f"   [lora] {name}: {len(imgs)} training images -> {zip_path}")
    return zip_path


def _load_manifest():
    return json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}


def _save_manifest(m):
    json.dump(m, open(MANIFEST, "w"), indent=2)


def train(name, steps=1000, force=False):
    """Fine-tune a LoRA for one character on fal.ai. Caches the weights url."""
    import fal_client
    man = _load_manifest()
    if name in man and not force:
        print(f"   [lora] {name}: already trained ({man[name]['url'][:60]}…)")
        return man[name]
    zip_path = prepare(name)
    url = fal_client.upload_file(zip_path)
    trigger = TRIGGERS.get(name, name.lower())
    print(f"   [lora] {name}: training (trigger='{trigger}', {steps} steps)…")
    res = fal_client.subscribe(
        "fal-ai/flux-lora-fast-training",
        arguments={"images_data_url": url, "trigger_word": trigger, "steps": steps},
    )
    lora_url = res["diffusers_lora_file"]["url"]
    man[name] = {"url": lora_url, "trigger": trigger}
    _save_manifest(man)
    print(f"   [lora] {name}: DONE -> {lora_url[:70]}…")
    return man[name]


def triggers_for(names):
    man = _load_manifest()
    return {n: man[n]["trigger"] for n in names if n in man}


def generate(prompt, loras, *, image_size="square_hd", steps=28, out_path=None):
    """fal flux-lora inference with one or more character LoRAs.

    loras: list of (character_name, scale). Trigger words must already be in the
    prompt. Returns PNG bytes (and writes out_path if given).
    """
    import fal_client
    import requests
    man = _load_manifest()
    specs = [{"path": man[n]["url"], "scale": s} for n, s in loras if n in man]
    res = fal_client.subscribe(
        "fal-ai/flux-lora",
        arguments={"prompt": prompt, "loras": specs, "image_size": image_size,
                   "num_inference_steps": steps, "num_images": 1},
    )
    img_url = res["images"][0]["url"]
    data = requests.get(img_url, timeout=120).content
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        open(out_path, "wb").write(data)
    return data


def train_all(names=("Bilbo", "Obi", "Homer", "Mom", "Dad"), force=False):
    for n in names:
        train(n, force=force)
    print("ALL LORAS TRAINED")
    return _load_manifest()
