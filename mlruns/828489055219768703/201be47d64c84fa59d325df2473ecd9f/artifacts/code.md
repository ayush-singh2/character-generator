# v13_flux_kontext_instruction — all code snippets used

```python
# ---- [1] kontext_call ------------------------------------------------
err_url = fal_client.upload_file(original_page)
ref_url = fal_client.upload_file(f'{REFS}/twiggy.png')
r = fal_client.subscribe('fal-ai/flux-pro/kontext/max/multi',
    arguments={'prompt': 'Fix ONLY the striped zebra ... keep the rest unchanged',
               'image_urls': [err_url, ref_url],
               'num_images': 1, 'guidance_scale': 3.5})
open('kontext_fix_p23.png','wb').write(
    requests.get(r['images'][0]['url']).content)

```
