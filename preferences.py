# type: ignore
"""Add-on preferences: the active backend, the models' folder, each model's environment and settings, the developer
option.

Each backend declares its settings (backends.base.Backend.settings_class); they are added here as
settings_<backend id>, so nothing specific to a backend is written in this file. A backend with something to install
(Backend.installable) also gets setup_<backend id>: its environment, installed by the add-on or an existing one.
The Models section is drawn by model_setup.py.
"""
import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, PropertyGroup

from .backends import registry

ADDON_ID = __package__

# Enum items, made once and kept alive here ({developer: items}): Blender doesn't keep the strings returned by an
# items callback, and still reads those of a previous call (the button's label while its menu is open). Making them
# again on each call freed them: the button showed no label.
_backend_items = {}


def backend_items(self, _context):
    developer = bool(self.developer)
    items = _backend_items.get(developer)
    if items is None:
        items = _backend_items[developer] = [
            (backend.id, backend.label, backend.description, number)
            for number, backend in enumerate(registry.BACKENDS) if developer or not backend.developer_only]
    return items


def _backend_changed(self, _context):
    # One model on the GPU at a time: the others' workers are stopped (a generation keeps its own running)
    for backend in registry.BACKENDS:
        if backend.id != self.backend:
            worker = registry.existing_worker(backend.id)
            if worker is not None and not worker.busy:
                registry.stop(backend.id)


def _developer_changed(self, _context):
    # A backend made for testing, hidden again: the first visible one is chosen (the menu would show none)
    if not self.developer:
        visible = [backend.id for backend in registry.BACKENDS if not backend.developer_only]
        if visible and self.backend not in visible:
            self.backend = visible[0]


def _settings_classes():
    return [(b, b.settings_class()) for b in registry.BACKENDS if b.settings_class() is not None]


class INTERPOSE_ModelSetup(PropertyGroup):
    """Where a backend's model environment is"""
    environment: EnumProperty(
        name="Environment",
        items=[('MANAGED', "Installed by the Add-on", "The add-on installs the model and its environment in the "
                                                     "models' folder"),
               ('EXISTING', "Existing Environment", "Use a Python environment where the model is installed already")],
        default='MANAGED')
    python: StringProperty(name="Python", subtype='FILE_PATH',
                           description="Python executable of the existing environment "
                                       "(for example <venv>/Scripts/python.exe)")


class INTERPOSE_Preferences(AddonPreferences):
    bl_idname = ADDON_ID

    backend: EnumProperty(name="Backend", items=backend_items, update=_backend_changed,
                          description="Motion model generating the in-betweens")
    developer: BoolProperty(name="Developer", default=False, update=_developer_changed,
                            description="Also list the backends made for testing")
    models_folder: StringProperty(name="Models Folder", subtype='DIR_PATH', default="",
                                  description="Folder where the models' environments are installed (empty: the "
                                              "default folder of this system, shown below)")

    def draw(self, context):
        from . import model_setup
        layout = self.layout
        model_setup.draw_models(layout, context, self)
        layout.prop(self, "developer")


def get_preferences(context):
    """The add-on preferences, or None if the add-on isn't enabled through Blender (some scripts and tests)"""
    addon = context.preferences.addons.get(ADDON_ID)
    return addon.preferences if addon is not None else None


def active_backend(context):
    """The backend chosen in the preferences, as its settings make it (Backend.configured); the first visible
    backend if that one is hidden or unknown"""
    prefs = get_preferences(context)
    developer = prefs.developer if prefs is not None else False
    visible = registry.visible(developer)
    chosen = visible[0]
    if prefs is not None:
        chosen = next((backend for backend in visible if backend.id == prefs.backend), chosen)
    return chosen.configured(backend_settings(context, chosen))


def backend_settings(context, backend):
    """The backend's settings (its settings_class instance), or None"""
    prefs = get_preferences(context)
    if prefs is None:
        return None
    return getattr(prefs, f"settings_{backend.id}", None)


def setup_settings(context, backend):
    """The backend's environment settings (INTERPOSE_ModelSetup), or None"""
    prefs = get_preferences(context)
    if prefs is None:
        return None
    return getattr(prefs, f"setup_{backend.id}", None)


def register():
    bpy.utils.register_class(INTERPOSE_ModelSetup)
    for backend, cls in _settings_classes():
        bpy.utils.register_class(cls)
        INTERPOSE_Preferences.__annotations__[f"settings_{backend.id}"] = PointerProperty(type=cls)
    for backend in registry.BACKENDS:
        if backend.installable:
            INTERPOSE_Preferences.__annotations__[f"setup_{backend.id}"] = PointerProperty(type=INTERPOSE_ModelSetup)
    bpy.utils.register_class(INTERPOSE_Preferences)


def unregister():
    bpy.utils.unregister_class(INTERPOSE_Preferences)
    for backend in registry.BACKENDS:
        INTERPOSE_Preferences.__annotations__.pop(f"setup_{backend.id}", None)
    for backend, cls in reversed(_settings_classes()):
        INTERPOSE_Preferences.__annotations__.pop(f"settings_{backend.id}", None)
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(INTERPOSE_ModelSetup)
    registry.stop_all()
