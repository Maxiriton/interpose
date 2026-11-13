# type: ignore
"""Bring what older versions saved up to date, on file load:
- data saved before the add-on was renamed from Retargetor to Interpose (RENAMED_PROPERTIES): the character state,
  the rig profile, the scene's character and bands toggle, the model armatures' skeleton, the models' collection.
  Each is moved to its new name, on the file's own data (a linked rig gets it when its own file is opened and saved).
- setups saved in scene.retarget_*, moved onto the target armature object. Older versions stored one setup per
  scene. The properties are no longer registered, but their values are still in the file, in the scene's system
  properties. Each scene's setup is copied into target_object.interpose (unless that object already has a bone
  list), then removed from the scene.
- rig profiles recording a preset by its old name ("Auto-Rig Pro (FK controls)"), given its current one. Linked
  armatures keep it: the panels show the current name anyway.
"""
import bpy
from bpy.app.handlers import persistent

from .profile_operators import RENAMED_PRESETS
from .properties import suspended_target_update

LEGACY_PROPERTIES = (
    "retarget_bones",
    "retarget_bones_active_index",
    "retarget_is_recording",
    "retarget_current_initial_rotation",
    "last_active_bone_name",
    "retarget_source_armature",
    "retarget_target_armature",
    "retarget_translation_scale",
)
# EnumProperty values are stored as integers
LEGACY_OFFSET_MODES = {0: 'ROLL', 1: 'REST_OFFSET'}

# Saved by Retargetor, the add-on's name before 0.1.0: (data collection, system property?, old name, new name).
# Registered properties are system properties; the model armatures' skeleton is a custom property of their data.
RENAMED_PROPERTIES = (
    ("objects", True, "retargetor", "interpose"),
    ("armatures", True, "retargetor_profile", "interpose_profile"),
    ("armatures", False, "retargetor_skeleton", "interpose_skeleton"),
    ("armatures", False, "retargetor_backend", "interpose_backend"),
    ("scenes", True, "retargetor_target", "interpose_target"),
    ("scenes", True, "retargetor_show_segments", "interpose_show_segments"),
)
RENAMED_COLLECTIONS = {"Retargetor Models": "Interpose Models"}


def rename_properties():
    """Move what Retargetor saved to Interpose's names, on the file's own data (not linked). An ID already holding
    the new name keeps it. Returns a message, or None if there was nothing to do."""
    moved = 0
    for collection, system, old, new in RENAMED_PROPERTIES:
        for id_block in getattr(bpy.data, collection):
            if id_block.library is not None:
                continue
            props = id_block.bl_system_properties_get() if system else id_block
            if props is None or old not in props:
                continue
            if new not in props:
                props[new] = props[old]  # a deep copy of the group, its ID pointers kept
            del props[old]
            moved += 1
    for old, new in RENAMED_COLLECTIONS.items():
        collection = bpy.data.collections.get(old)
        if collection is not None and collection.library is None and new not in bpy.data.collections:
            collection.name = new
            moved += 1
    if not moved:
        return None
    return f"what Retargetor saved moved to Interpose's names ({moved} properties and collections)."


def _legacy_properties(scene):
    props = scene.bl_system_properties_get()
    if props is None or "retarget_bones" not in props and "retarget_target_armature" not in props:
        return None
    return props


def _remove_legacy(props):
    for name in LEGACY_PROPERTIES:
        if name in props:
            del props[name]


def migrate_scene(scene):
    """Move the legacy setup of a scene onto its target object. Returns a message, or None if there was nothing to do.
    The legacy data is kept when it can't be moved (no target, linked target, target already set up)."""
    if scene.library is not None:
        return None
    props = _legacy_properties(scene)
    if props is None:
        return None

    rows = list(props.get("retarget_bones", []))
    target = props.get("retarget_target_armature")
    source = props.get("retarget_source_armature")

    if not rows:
        _remove_legacy(props)
        return f"Scene '{scene.name}': empty legacy setup removed."
    if not isinstance(target, bpy.types.Object) or target.type != 'ARMATURE':
        return f"Scene '{scene.name}': legacy setup kept, it has no target armature."
    if not target.is_editable:
        return f"Scene '{scene.name}': legacy setup kept, the target '{target.name}' is linked and can't be edited."
    state = target.interpose
    if len(state.bones) > 0:
        return f"Scene '{scene.name}': legacy setup kept, '{target.name}' already has a bone list."

    with suspended_target_update():
        for row in rows:
            item = state.bones.add()
            item.src_name = row.get("src_name", "")
            item.target_name = row.get("target_name", "")
            item.use_translation = bool(row.get("use_translation", False))
            item.offset_mode = LEGACY_OFFSET_MODES.get(row.get("offset_mode", 0), 'ROLL')
            item.has_corrective_offset = bool(row.get("has_corrective_offset", False))
            corrective = row.get("corrective_offset")
            if corrective is not None and len(corrective) == 4:
                item.corrective_offset = tuple(corrective)

    if isinstance(source, bpy.types.Object) and source.type == 'ARMATURE':
        state.source = source
    state.bones_active_index = int(props.get("retarget_bones_active_index", 0))
    state.translation_scale = float(props.get("retarget_translation_scale", 1.0))
    if scene.interpose_target is None:
        scene.interpose_target = target

    _remove_legacy(props)
    return f"Scene '{scene.name}': setup of {len(rows)} bones moved to the object '{target.name}'."


def rename_presets():
    """The rig profiles of the file's own armatures recording a preset by its old name: given its current one.
    Returns a message per armature."""
    messages = []
    for armature in bpy.data.armatures:
        profile = getattr(armature, "interpose_profile", None)
        if armature.library is not None or profile is None or profile.source not in RENAMED_PRESETS:
            continue
        old = profile.source
        profile.source = RENAMED_PRESETS[old]
        messages.append(f"Armature '{armature.name}': preset '{old}' is now called '{profile.source}'.")
    return messages


def migrate_all():
    """Migrate what Retargetor saved, every scene of the file, then the rig profiles' preset names. Returns the list
    of messages."""
    renamed = rename_properties()
    messages = [renamed] if renamed else []
    for scene in bpy.data.scenes:
        message = migrate_scene(scene)
        if message:
            messages.append(message)
    return messages + rename_presets()


@persistent
def migrate_on_load(_filepath):
    for message in migrate_all():
        print(f"Interpose: {message}")


def register():
    if migrate_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(migrate_on_load)


def unregister():
    if migrate_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(migrate_on_load)
