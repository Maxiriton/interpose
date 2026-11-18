"""The panels on two small armatures: the character following the active armature, what keeps Generate from
starting (rig_problem), the rig profile panel and its JSON, and drawing the panels, the editors' header and the
Interpose menu (with a layout that checks every property and operator).

    blender -b --factory-startup --python tests/blender/test_panel.py -- <scratch dir>
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402


ICONS = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())


class CheckingLayout:
    """Stands in for a UILayout: every property, operator and icon the panel uses must exist."""

    def __init__(self, errors):
        self.errors = errors
        self.enabled = True

    def _sub(self, *_args, **_kwargs):
        return CheckingLayout(self.errors)

    row = column = box = split = _sub

    def _check_icon(self, kwargs):
        icon = kwargs.get("icon")
        if icon is not None and icon not in ICONS:
            self.errors.append(f"unknown icon {icon}")

    def label(self, **kwargs):
        self._check_icon(kwargs)

    def progress(self, **_kwargs):
        pass

    def menu(self, menu, **kwargs):
        self._check_icon(kwargs)
        if not hasattr(bpy.types, menu):
            self.errors.append(f"unknown menu {menu}")

    def separator(self, **_kwargs):
        pass

    def _check_prop(self, data, name):
        if data is None or name not in data.bl_rna.properties:
            self.errors.append(f"unknown property {name} on {data}")

    def prop(self, data, name, **kwargs):
        self._check_prop(data, name)
        self._check_icon(kwargs)

    def prop_search(self, data, name, search_data, search_name, **_kwargs):
        self._check_prop(data, name)
        self._check_prop(search_data, search_name)

    def operator(self, idname, **kwargs):
        self._check_icon(kwargs)
        module, name = idname.split(".")
        if not hasattr(getattr(bpy.ops, module), name) or getattr(getattr(bpy.ops, module), name).idname() is None:
            self.errors.append(f"unknown operator {idname}")
        return type("Props", (), {})()

    def template_list(self, list_type, _list_id, data, name, active_data, active_name, **_kwargs):
        if not hasattr(bpy.types, list_type):
            self.errors.append(f"unknown UIList {list_type}")
        self._check_prop(data, name)
        self._check_prop(active_data, active_name)
        ui_list = getattr(bpy.types, list_type)
        for index, item in enumerate(getattr(data, name)):
            ui_list.draw_item(None, bpy.context, CheckingLayout(self.errors), data, item, 0, active_data, active_name, index)


def draw_panels(panels=None):
    errors = []
    from interpose import ui
    for panel in panels or (ui.INTERPOSE_PT_RigProfilePanel, ui.INTERPOSE_PT_RigLimbsPanel,
                            ui.INTERPOSE_PT_RigAdvancedPanel, ui.INTERPOSE_MT_ProfileFiles,
                            ui.INTERPOSE_PT_GeneratePanel, ui.INTERPOSE_MT_EditorMenu):
        if hasattr(panel, "poll") and not panel.poll(bpy.context):
            continue
        fake = type("Panel", (), {"layout": CheckingLayout(errors)})()
        panel.draw(fake, bpy.context)
    fake = type("Header", (), {"layout": CheckingLayout(errors)})()
    ui.draw_editor_header(fake, bpy.context)
    return errors


def main(scratch):
    checks = bootstrap.Checks("test_panel")
    source, target = bootstrap.make_test_scene()
    bootstrap.register_addon()
    from interpose import ui
    from interpose.core.skeleton_io import SKELETON_PROPERTY
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    for obj in scene.objects:
        obj.select_set(False)
    view_layer.objects.active = None
    view_layer.update()
    scene.interpose_target = None

    checks.check(draw_panels() == [], "panels draw with no character")
    checks.check(ui.rig_problem(bpy.context) == ("Select the character's armature in Pose Mode", False),
                 f"no character: select one ({ui.rig_problem(bpy.context)})")

    # The character follows the active armature
    view_layer.objects.active = target
    view_layer.update()
    checks.check(scene.interpose_target == target, "the active armature becomes the character")
    checks.check(ui.rig_problem(bpy.context) == ("Enter Pose Mode to generate", False),
                 f"in Object Mode: enter Pose Mode ({ui.rig_problem(bpy.context)})")
    bpy.ops.object.mode_set(mode='POSE')
    problem = ui.rig_problem(bpy.context)
    checks.check(problem is not None and problem[1] and "rig" in problem[0],
                 f"a rig the add-on doesn't recognize: set it up ({problem})")
    checks.check(draw_panels() == [], "panels draw with a rig to set up")
    bpy.ops.object.mode_set(mode='OBJECT')

    view_layer.objects.active = source
    view_layer.update()
    checks.check(scene.interpose_target == source, "another active armature becomes the character")
    # A click on a band's name tag sets the character: it holds until the active object changes
    scene.interpose_target = target
    view_layer.update()
    checks.check(scene.interpose_target == target, "a character picked from its band holds while the active one stays")
    view_layer.objects.active = target
    view_layer.update()
    view_layer.objects.active = source
    view_layer.update()
    checks.check(scene.interpose_target == source, "and follows the active armature again when it changes")

    # A motion model's armature is never the character
    model = bootstrap.make_armature("MODEL", bootstrap.TARGET_BONES, location=(4.0, 0.0, 0.0))
    model.data[SKELETON_PROPERTY] = "{}"
    view_layer.objects.active = source  # make_armature left the model active, unmarked yet
    view_layer.update()
    scene.interpose_target = source
    view_layer.objects.active = model
    view_layer.update()
    checks.check(scene.interpose_target == source, "a model armature doesn't become the character")
    model.data.pop(SKELETON_PROPERTY)
    bpy.data.objects.remove(model)
    second = bootstrap.make_armature("TGT2", bootstrap.TARGET_BONES, location=(-2.0, 0.0, 0.0))

    # Rig profile panel on an armature with a profile
    view_layer.objects.active = target
    view_layer.update()
    target.data.interpose_profile.roles.clear()
    checks.check(bpy.ops.interpose.profile_add_roles() == {'FINISHED'}, "Add Roles")
    profile = target.data.interpose_profile
    checks.check(len(profile.roles) == 23, "every role added")
    bpy.ops.object.mode_set(mode='POSE')
    checks.check(ui.rig_problem(bpy.context) == ("TGT: rig setup incomplete", True),
                 f"required bones missing: the rig setup fixes it ({ui.rig_problem(bpy.context)})")
    bpy.ops.object.mode_set(mode='OBJECT')
    profile.limbs.add().name = "arm.L"
    checks.check(draw_panels() == [], "panels draw with a rig profile")
    path = os.path.join(scratch, "panel_profile.json")
    profile.roles[0].read_bone = "hips"
    checks.check(bpy.ops.interpose.profile_export_json(filepath=path) == {'FINISHED'}, "Export Profile")
    view_layer.objects.active = second
    checks.check(bpy.ops.interpose.profile_import_json(filepath=path) == {'FINISHED'}, "Import Profile")
    checks.check(second.data.interpose_profile.roles[0].read_bone == "hips", "profile imported on another armature")

    from interpose.profile_operators import parse_frames
    checks.check(parse_frames("1, 61,120") == [1, 61, 120] and parse_frames("3-5, -1") == [-1, 3, 4, 5],
                 "frame lists parsed")
    checks.finish()


if __name__ == "__main__":
    main(bootstrap.script_args()[0])
