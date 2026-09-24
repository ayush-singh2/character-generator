zebra_box = [0.60, 0.33, 0.97, 0.90]        # TOO WIDE
mask = fal_backend.make_mask((W,H), zebra_box)
fal_backend.inpaint(original, mask, prompt,
    ip_adapter_ref=open(f'{REFS}/twiggy.png','rb').read(),
    ip_scale=0.9, strength=0.85)   # box overlapped giraffe -> erased
