# type: ignore
"""Bring what older versions saved up to date, on file load:
- data saved before the add-on was renamed from Retargetor to Interpose (RENAMED_PROPERTIES): the character state,
  the rig profile, the scene's character and bands toggle, the model armatures' skeleton, the models' collection.
  Each is moved to its new name, on the file's own data (a linked rig gets it when its own file is opened and saved).
- rig profiles recording a preset by its old name ("Auto-Rig Pro (FK controls)"), given its current one. Linked
  armatures keep it: the panels show the current name anyway.
The manual bone list of the first versions (scene.retarget_*, then object.interpose.bones) went with the Retarget
panel: what a file still holds of it is left alone, unused.
"""
import bpy
from bpy.app.handlers import persistent

from .profile_operators import RENAMED_PRESETS

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
    """Migrate what Retargetor saved, then the rig profiles' preset names. Returns the list of messages."""
    renamed = rename_properties()
    return ([renamed] if renamed else []) + rename_presets()


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
