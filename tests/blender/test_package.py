"""The extension's package, installed in a Blender whose user folder is a scratch one: it installs, registers, lists
its backends, generates with the interpolation backend (its worker started from the installed folder), holds only
the add-on (no tests, spikes or project notes), and disables cleanly.

    blender --command extension build --output-dir <dist>
    BLENDER_USER_RESOURCES=<scratch folder> blender -b --factory-startup --python tests/blender/test_package.py -- <dist>/interpose-<version>.zip

run_tests.py builds the package and points BLENDER_USER_RESOURCES to a scratch folder: never run it on your own.
"""
import importlib
import math
import os
import sys

import addon_utils
import bpy
from mathutils import Euler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "fixtures"))
import bootstrap  # noqa: E402  (Checks only: the add-on comes from the package)
import humanoids  # noqa: E402

MODULE = "bl_ext.user_default.interpose"
PREFIX = "mixamorig:"


def build_skeleton(name):
    arm = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for bone, parent, head, tail in humanoids.skeleton("mixamo", PREFIX):
        edit_bone = arm.edit_bones.new(bone)
        edit_bone.head = head
        edit_bone.tail = tail if head != tail else (head[0], head[1] - 0.03, head[2])
        if parent:
            edit_bone.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def main(zip_path):
    checks = bootstrap.Checks("test_package")
    user = bpy.utils.resource_path('USER')
    checks.check(os.environ.get("BLENDER_USER_RESOURCES") and os.path.samefile(user, os.environ["BLENDER_USER_RESOURCES"]),
                 f"Blender's user folder is the scratch one ({user})")
    if checks.failures:
        checks.finish()

    result = bpy.ops.extensions.package_install_files(filepath=zip_path, repo="user_default", enable_on_install=True)
    checks.check(result == {'FINISHED'}, f"package installed ({result})")
    checks.check(addon_utils.check(MODULE)[1], f"{MODULE} enabled")
    checks.check(hasattr(bpy.types.Object, "interpose") and hasattr(bpy.types.Armature, "interpose_profile")
                 and hasattr(bpy.types.Scene, "interpose_target"), "properties registered")
    checks.check(hasattr(bpy.ops.interpose, "generate_inbetweens") and hasattr(bpy.types, "INTERPOSE_PT_GeneratePanel"),
                 "operators and panels registered")
    prefs = bpy.context.preferences.addons.get(MODULE)
    checks.check(prefs is not None and prefs.preferences is not None, "preferences available")
    registry = importlib.import_module(MODULE + ".backends.registry")
    backends = {b.id for b in registry.visible(developer=True)}
    checks.check({"kimodo", "ardy", "interpolate"} <= backends, f"every backend listed ({sorted(backends)})")

    folder = os.path.dirname(sys.modules[MODULE].__file__)
    files = set(os.listdir(folder))
    checks.check(not files & {"tests", "spikes", "CLAUDE.md", "CLAUDE.local.md", "ROADMAP.md", "DESIGN.md", ".git"},
                 f"no tests, spikes or project notes in the package ({sorted(files)})")
    checks.check({"LICENSE", "README.md", "presets", "blender_manifest.toml"} <= files,
                 "LICENSE, README, presets and manifest packaged")

    # A generation from the installed package: the interpolation backend's worker runs from its folder
    prefs.preferences.developer = True
    prefs.preferences.backend = "interpolate"
    rig = build_skeleton("mixamo")
    bpy.context.scene.interpose_target = rig
    checks.check(len(rig.data.interpose_profile.roles) > 0,
                 f"the skeleton set itself up ({len(rig.data.interpose_profile.roles)} roles)")
    for frame, angle in ((1, 0.0), (31, 70.0)):
        pose_bone = rig.pose.bones[PREFIX + "LeftArm"]
        pose_bone.rotation_mode = 'QUATERNION'
        pose_bone.rotation_quaternion = Euler((math.radians(angle), 0.0, 0.0)).to_quaternion()
        pose_bone.keyframe_insert("rotation_quaternion", frame=frame)
    bpy.context.scene.frame_set(1)
    result = bpy.ops.interpose.generate_inbetweens('EXEC_DEFAULT')
    generation = importlib.import_module(MODULE + ".generation")
    types = {p.type for fc in generation.channelbag(rig).fcurves for p in fc.keyframe_points}
    checks.check(result == {'FINISHED'} and 'GENERATED' in types, f"generated with the interpolation backend ({result})")
    registry.stop_all()

    addon_utils.disable(MODULE)
    checks.check(not addon_utils.check(MODULE)[1] and not hasattr(bpy.types.Object, "interpose"), "disabled cleanly")
    checks.finish()


if __name__ == "__main__":
    main(bootstrap.script_args()[0])
