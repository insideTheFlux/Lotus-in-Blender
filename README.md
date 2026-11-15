# blender-lotus

A procedural lotus for [Blender](https://www.blender.org/), drawn entirely in code: no models, textures or other
assets. It renders with Cycles on the CPU or an NVIDIA GPU, in a black space with three lamps and a dark glossy floor.

One number drives it, `openness`, from 0 (a closed bud) to 1 (fully open):

- eight stacked petal layers wrap round the axis, so no petal cuts into another; the bud is a closed, rounded tulip shape
  and opens along one smooth curve;
- the centre is a flat receptacle with raised seed bumps, ringed by a dense fringe of orange stamens that stand upright
  in the bud and curve outwards as it opens, always inside the opening the inner petals leave;
- every petal is slightly different (length, width, lean, curl, cup), seeded so the same flower renders every time;
- from about 40 % the whole flower turns on its pivot to face the camera while the petals are still opening, and at 1 it
  looks straight at it; the camera backs off a little during the turn so the lowest petal stays in frame.

```
blender --background --python lotus.py -- <out.png> [openness 0..1] [samples] [resolution scale] [cpu|gpu]
blender --background --python lotus.py -- lotus.png 0.8 64 1 gpu
```

| Argument | Meaning | Default |
|---|---|---|
| `out.png` | the image to write | required |
| `openness` | 0 to 1 | 0.8 |
| `samples` | Cycles samples (denoised) | 96 |
| `resolution scale` | 1 is 1600x1000 | 1 |
| `cpu` or `gpu` | `gpu` uses CUDA on an NVIDIA card, and falls back to the CPU if none is found | cpu |

On a GTX 1070, 800x500 at 16 samples takes about 17 s with `gpu` and about 30 s on a 6-thread CPU.

## A looping video
```powershell
.\render-cycle.ps1 -Blender 'C:\Program Files\Blender Foundation\Blender 5.3\blender.exe' -Out lotus.mp4 -Device gpu
```
Renders a frame every 2.5 % of openness (`-Step`), joins them with `frames-to-mp4.py` (Blender's own video
sequencer, no other tools), and plays up and then back down. The turn runs over the last 60 %, so a finer `-Step`
such as `0.005` makes it smoother.

## Tested with
Blender 5.3 on Windows. Written against the 5.x Python API (the Principled BSDF socket names and the video media type).

## Licence
GPL-3.0-or-later, see `LICENSE`. Scripts that use Blender's Python API are generally treated as GPL, so this repo
follows Blender's own licence.

## Frames for PetalStat
`lotus-frames.py` renders one frame of a frame sequence (1920x1080 JPEG, `dim` or `bright`, with the floor hidden from
the camera so the backdrop is pure black). PetalStat's Lotus theme plays 241 such frames per light level, openness
`k/240`:
```powershell
blender --background --python lotus-frames.py -- k_100.jpg 0.4167 48 1 bright
```
