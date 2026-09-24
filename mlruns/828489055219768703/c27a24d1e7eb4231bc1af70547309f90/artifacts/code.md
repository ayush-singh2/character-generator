# v07_harmonize_img2img_sweep — all code snippets used

```python
# ---- [1] img2img_sweep -----------------------------------------------
for s in (0.4, 0.5, 0.6, 0.7):
    r = fal_client.subscribe('fal-ai/flux-general/image-to-image',
        arguments={'image_url': init_url, 'prompt': prompt,
                   'strength': s, 'num_inference_steps': 36,
                   'image_size': 'square_hd', 'num_images': 1})
    open(f'fal_harm_p23_s{int(s*100)}.png','wb').write(
        requests.get(r['images'][0]['url']).content)

```
