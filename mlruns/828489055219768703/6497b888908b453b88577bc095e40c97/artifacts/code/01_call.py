extra_box = [0.86, 0.42, 0.99, 0.88]        # ONLY the extra part
mask = fal_backend.make_mask((W,H), extra_box, feather=6)
fal_backend.inpaint(original, mask,
    'clean wooden studio floor and plant, no animal, no extra legs',
    strength=0.95)
