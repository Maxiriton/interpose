"""Make a character with the add-on as it was when it was called Retargetor, and save it. test_rename_migration.py
then opens the file with Interpose.

    blender -b --factory-startup --python tests/blender/retargetor_setup.py -- <Retargetor add-on folder> <out dir>

<Retargetor add-on folder>: the add-on before the rename, for example extracted with
    git archive d55f116 | tar -x -C <folder>
A detected skeleton (Mixamo naming), two key poses, a generation with the interpolation backend (prompt segment 1,
its Generated keys, the model's armature), a second segment, the bands hidden. Writes <out dir>/retargetor.blend and
<out dir>/retargetor.json (what the new version must find).
"""
import importlib.util
import json
import math
import os
import sys

import bpy
from mathutils import Euler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "fixtures"))
import bootstrap  # noqa: E402  (make_armature only: it doesn't import the add-on)
import humanoids  # noqa: E402

MODULE = "retargetor"


def register_old_addon(folder):
    spec = importlib.util.spec_from_file_location(
        MODULE, os.path.join(folder, "__init__.py"), submodule_search_locations=[folder])
    package = importlib.util.module_from_spec(spec)
    sys.modules[MODULE] = package
    spec.loader.exec_module(package)
    package.register()
    if bpy.context.preferences.addons.get(MODULE) is None:
        bpy.context.preferences.addons.new().module = MODULE
    prefs = bpy.context.preferences.addons[MODULE].preferences
    prefs.developer = True
    prefs.backend = "interpolate"


def keys(rig):
    """Every key of the rig's action: {"data_path[index]": [[frame, value, type], ...]}"""
    from retargetor import generation
    return {f"{fc.data_path}[{fc.array_index}]": [[p.co.x, p.co.y, p.type] for p in fc.keyframe_points]
            for fc in generation.channelbag(rig).fcurves}


def main(folder, out_dir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    register_old_addon(folder)
    scene = bpy.context.scene

    bones = []
    for bone, parent, head, tail in humanoids.skeleton("mixamo", "mixamorig:"):
        if head == tail:
            tail = (head[0], head[1] - 0.03, head[2])
        bones.append((bone, head, tail, 0.0, parent))
    rig = bootstrap.make_armature("Character", bones)
    scene.retargetor_target = rig  # detects the skeleton
    if len(rig.data.retargetor_profile.roles) == 0:
        raise SystemExit("The old version didn't detect the skeleton")

    for frame, angle in ((1, 0.0), (31, 70.0)):
        for name in ("mixamorig:LeftArm", "mixamorig:RightUpLeg", "mixamorig:Spine1"):
            pb = rig.pose.bones[name]
            pb.rotation_quaternion = Euler((math.radians(angle), 0.0, math.radians(angle / 2)), 'XYZ').to_quaternion()
            pb.keyframe_insert("rotation_quaternion", frame=frame)
    state = rig.retargetor
    state.prompt, state.seed = "A person waves", 7
    scene.frame_set(1)
    if bpy.ops.retargetor.generate_inbetweens('EXEC_DEFAULT') != {'FINISHED'}:
        raise SystemExit("The old version didn't generate")
    print("segments after generating:", len(state.segments))
    while len(state.segments) < 2:
        bpy.ops.retargetor.segment_add("EXEC_DEFAULT")
    state.segments[1].prompt = "A person jumps"
    state.segments_active_index = 0
    scene.retargetor_show_segments = False

    from retargetor import generated_keys
    expected = {
        "rig": rig.name,
        "profile": rig.data.retargetor_profile.to_core().to_dict(),
        "prompt": state.prompt, "seed": state.seed,
        "segments": [[s.frame_start, s.frame_end, s.prompt, s.seed] for s in state.segments],
        "model_armature": state.model_armature.name if state.model_armature else None,
        "has_record": generated_keys.has_record(rig),
        "keys": keys(rig),
    }
    if expected["model_armature"] is None or not expected["has_record"]:
        raise SystemExit("The old version left no model armature or no record of its keys")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "retargetor.blend"))
    with open(os.path.join(out_dir, "retargetor.json"), "w") as f:
        json.dump(expected, f)
    print(f"Saved {out_dir}: segments {expected['segments']}, model armature {expected['model_armature']}")


if __name__ == "__main__":
    main(*bootstrap.script_args())
