"""Open a file made when the add-on was called Retargetor (retargetor_setup.py): the character state, the rig
profile, the scene's character and bands toggle, the model's armature and its collection must come back under
Interpose's names, and work: the model's armature reused by a new generation, Clear Generated Keys finding what the
old version recorded.

    blender -b --factory-startup --python tests/blender/test_rename_migration.py -- <dir with retargetor.blend/.json>
"""
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

OLD_NAMES = {"objects": ("retargetor",), "armatures": ("retargetor_profile",),
             "scenes": ("retargetor_target", "retargetor_show_segments")}


def keys(rig):
    from interpose import generation
    return {f"{fc.data_path}[{fc.array_index}]": [[p.co.x, p.co.y, p.type] for p in fc.keyframe_points]
            for fc in generation.channelbag(rig).fcurves}


def same_keys(a, b, tolerance=1e-5):
    return a.keys() == b.keys() and all(
        len(a[k]) == len(b[k]) and all(abs(p[0] - q[0]) <= tolerance and abs(p[1] - q[1]) <= tolerance and p[2] == q[2]
                                       for p, q in zip(a[k], b[k])) for k in a)


def main(out_dir):
    checks = bootstrap.Checks("test_rename_migration")
    bootstrap.register_addon()
    bootstrap.set_backend("interpolate", developer=True)
    with open(os.path.join(out_dir, "retargetor.json")) as f:
        expected = json.load(f)
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "retargetor.blend"))
    from interpose import generated_keys, generation, migration

    scene = bpy.context.scene
    rig = bpy.data.objects[expected["rig"]]
    state = rig.interpose
    checks.check(scene.interpose_target == rig, "the scene's character kept")
    checks.check(scene.interpose_show_segments is False, "the bands toggle kept (hidden)")
    profile = rig.data.interpose_profile.to_core().to_dict()
    old_profile = dict(expected["profile"], format=profile["format"])
    checks.check(profile == old_profile, "the rig profile kept, every role")
    checks.check((state.prompt, state.seed) == (expected["prompt"], expected["seed"]), "prompt and seed kept")
    segments = [[s.frame_start, s.frame_end, s.prompt, s.seed] for s in state.segments]
    checks.check(segments == expected["segments"], f"the prompt segments kept ({segments})")
    checks.check(same_keys(keys(rig), expected["keys"], 0.0), "the keys unchanged")
    checks.check(generated_keys.has_record(rig), "the record of the Generated keys kept")

    model = state.model_armature
    checks.check(model is not None and model.name == expected["model_armature"], "the model's armature kept")
    checks.check(generation.armature_backend(model) == "interpolate" and generation.armature_skeleton(model) is not None,
                 "the model's armature still says which skeleton it was built from")
    checks.check(generation.MODELS_COLLECTION in bpy.data.collections
                 and "Retargetor Models" not in bpy.data.collections, "the models' collection renamed")
    left = [(collection, name) for collection, names in OLD_NAMES.items()
            for block in getattr(bpy.data, collection) for name in names
            if name in (block.bl_system_properties_get() or {})]
    left += [("armatures", n) for a in bpy.data.armatures for n in ("retargetor_skeleton", "retargetor_backend")
             if n in a]
    checks.check(not left, f"nothing left under the old names ({left})")
    checks.check(migration.migrate_all() == [], "the migration runs only once")

    # The data works: a new generation of segment 1 reuses the model's armature
    armatures = len([o for o in bpy.data.objects if o.type == 'ARMATURE'])
    scene.frame_set(1)
    checks.check(bpy.ops.interpose.regenerate_segment('EXEC_DEFAULT', index=0) == {'FINISHED'},
                 "segment 1 generated again")
    checks.check(state.model_armature == model and len([o for o in bpy.data.objects if o.type == 'ARMATURE']) == armatures,
                 "the model's armature reused, not rebuilt")
    checks.check(same_keys(keys(rig), expected["keys"]), "the same keys (same seed, same key poses)")
    checks.check(bpy.ops.interpose.clear_generated_keys('EXEC_DEFAULT') == {'FINISHED'}, "Clear Generated Keys")
    types = {p.type for fc in generation.channelbag(rig).fcurves for p in fc.keyframe_points}
    checks.check('GENERATED' not in types and 'KEYFRAME' in types, "the Generated keys removed, the key poses kept")
    checks.finish()


if __name__ == "__main__":
    main(*bootstrap.script_args())
