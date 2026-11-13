# blender-lotus

A procedural lotus for [Blender](https://www.blender.org/), drawn entirely in code: no models, textures or other
assets. It renders with Cycles on the CPU, in a black space with three lamps and a dark glossy floor.

One number drives it, `openness`, from 0 (a closed bud) to 1 (fully open):

- the four petal rings fall outwards as it rises, and the gold stamens and seed pod appear past about 35 %;
- every petal is slightly different (length, width, lean, curl, cup), seeded so the same flower renders every time;
- past 55 % the whole flower turns on its pivot to face the camera, and at 1 it looks straight at it.

```
blender --background --python lotus.py -- <out.png> [openness 0..1] [samples] [resolution scale]
blender --background --python lotus.py -- lotus.png 0.8 64 1
```

| Argument | Meaning | Default |
|---|---|---|
| `out.png` | the image to write | required |
| `openness` | 0 to 1 | 0.8 |
| `samples` | Cycles samples (denoised) | 96 |
| `resolution scale` | 1 is 1600x1000 | 1 |

A full 1600x1000 frame at 80 samples takes about 6 to 8 minutes on a recent CPU; 800x500 at 16 samples takes under
half a minute.

## A looping video
```powershell
.\render-cycle.ps1 -Blender 'C:\Program Files\Blender Foundation\Blender 5.3\blender.exe' -Out lotus.mp4
```
Renders a frame every 2.5 % of openness (`-Step`), joins them with `frames-to-mp4.py` (Blender's own video
sequencer, no other tools), and plays up and then back down. The turn happens over the last 45 %, so a finer `-Step`
such as `0.005` makes it smoother.

## Tested with
Blender 5.3 on Windows. Written against the 5.x Python API (the Principled BSDF socket names and the video media type).

## Licence
GPL-3.0-or-later, see `LICENSE`. Scripts that use Blender's Python API are generally treated as GPL, so this repo
follows Blender's own licence.
