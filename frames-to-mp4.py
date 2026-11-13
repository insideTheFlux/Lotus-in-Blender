"""Joins frame_###.png files into an MP4 with Blender's video sequencer: up through the frames, then back down.

    blender --background --python frames-to-mp4.py -- <frames folder> <out.mp4> <fps>
"""
import bpy, sys, glob, os
args = sys.argv[sys.argv.index('--') + 1:]
folder, out, fps = args[0], args[1], int(args[2])
files = sorted(glob.glob(os.path.join(folder, 'frame_*.png')))
seq = files + files[-2:0:-1]           # up, then back down without repeating the ends
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.sequence_editor_create()
for i, f in enumerate(seq):
    sc.sequence_editor.strips.new_image(name=f'f{i}', filepath=f, channel=1, frame_start=i + 1)
sc.frame_start = 1
sc.frame_end = len(seq)
sc.render.fps = fps
sc.render.resolution_x = 800
sc.render.resolution_y = 500
sc.render.image_settings.media_type = 'VIDEO'
sc.render.image_settings.file_format = 'FFMPEG'
sc.render.ffmpeg.format = 'MPEG4'
sc.render.ffmpeg.codec = 'H264'
sc.render.ffmpeg.constant_rate_factor = 'HIGH'
sc.render.filepath = out
bpy.ops.render.render(animation=True)
print('DONE', out)
