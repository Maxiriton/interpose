# type: ignore
import bpy
from bpy.types import Menu, Panel, UIList

from . import generation
from .backends import process, registry
from .preferences import active_backend, ADDON_ID
from .properties import get_character

class INTERPOSE_PT_RigProfilePanel(Panel):
    """Rig setup of the active armature: its bones for each humanoid role, and the check of what its controls do"""
    bl_label = "Rig Setup"
    bl_idname = "INTERPOSE_PT_RigProfilePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Interpose'

    def draw(self, context):
        from . import rig_check
        from .core.roles import missing_required
        from .profile_operators import detect_profile, last_check, source_label
        layout = self.layout
        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE':
            layout.label(text="Select the character's armature")
            return

        armature = obj.data
        profile = armature.interpose_profile
        layout.label(text=armature.name, icon='ARMATURE_DATA')
        if not armature.is_editable:
            layout.label(text="Linked armature: set it up in its library file", icon='LIBRARY_DATA_DIRECT')

        if len(profile.roles) > 0:
            layout.label(text=f"Bones {source_label(profile.source)}", icon='PRESET')
            if len(profile.limbs) > 0:
                snapped = sum(1 for limb in profile.limbs if len(limb.ik_snap) > 0)
                layout.label(text=f"{len(profile.limbs)} IK/FK limbs: pose in IK or FK"
                                  + ("" if snapped == len(profile.limbs) else f" ({len(profile.limbs) - snapped} FK after generating)"),
                             icon='CON_KINEMATIC')
        else:
            detected = detect_profile(armature)
            if detected is not None:
                layout.label(text=f"Recognized: {source_label(detected[0])}", icon='PRESET')
                layout.label(text="Applied when the character is chosen or generates", icon='BLANK1')
            else:
                layout.label(text="Not set up: detect the bones, or assign them", icon='INFO')

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("interpose.profile_detect", icon='VIEWZOOM')
        row.operator("interpose.check_rig", icon='CHECKMARK')
        row.menu("INTERPOSE_MT_ProfileFiles", text="", icon='DOWNARROW_HLT')

        problems = None
        try:
            problems = last_check(armature, profile.to_core()) if len(profile.roles) > 0 else None
        except ValueError:
            pass
        by_subject = {}
        if problems is not None:
            box = layout.box()
            errors = [p for p in problems if p.level == rig_check.ERROR]
            if not problems:
                box.label(text="Checked: the rig is ready", icon='CHECKMARK')
            else:
                title = f"{len(errors)} problem(s) to fix" if errors else f"Ready, {len(problems)} warning(s)"
                box.label(text=title, icon='ERROR' if errors else 'INFO')
                for problem in problems[:6]:
                    _wrapped(box, problem.message, 'CANCEL' if problem.level == rig_check.ERROR else 'DOT')
                if len(problems) > 6:
                    box.label(text=f"... and {len(problems) - 6} more", icon='BLANK1')
            for problem in problems:
                by_subject.setdefault(problem.subject, problem)

        if len(profile.roles) == 0:
            return
        layout.prop(profile, "use_controls")
        missing = set(missing_required([b.role for b in profile.roles if b.read_bone]))
        bindings = {b.role: b for b in profile.roles}
        for title, role_ids in _ROLE_GROUPS:
            box = layout.box()
            box.label(text=title)
            for role_id in role_ids:
                _draw_role(box, obj, profile, role_id, bindings.get(role_id), missing, by_subject)


def _wrapped(layout, text, icon, width=44):
    import textwrap
    for i, line in enumerate(textwrap.wrap(text, width)):
        layout.label(text=line, icon=icon if i == 0 else 'BLANK1')


_ROLE_GROUPS = (
    ("Spine and Head", ("hips", "spine", "chest", "upper_chest", "neck", "upper_neck", "head")),
    ("Left Arm", ("shoulder.L", "upper_arm.L", "forearm.L", "hand.L")),
    ("Right Arm", ("shoulder.R", "upper_arm.R", "forearm.R", "hand.R")),
    ("Left Leg", ("thigh.L", "shin.L", "foot.L", "toes.L")),
    ("Right Leg", ("thigh.R", "shin.R", "foot.R", "toes.R")),
)


def _draw_role(layout, obj, profile, role_id, binding, missing, by_subject):
    """One role: its status, its bone (and control), assign / select / clear"""
    from . import rig_check
    from .core.roles import get_role
    role = get_role(role_id)
    problem = by_subject.get(role_id)
    if binding is None or not binding.read_bone:
        icon = 'ERROR' if role_id in missing else 'RADIOBUT_OFF'
    elif problem is not None:
        icon = 'ERROR' if problem.level == rig_check.ERROR else 'INFO'
    else:
        icon = 'CHECKMARK'
    label = role.label.replace(" (L)", "").replace(" (R)", "")
    split = layout.split(factor=0.36, align=True)
    split.label(text=label, icon=icon)
    row = split.row(align=True)
    if binding is None:
        row.label(text="(optional)" if role_id not in missing else "missing")
    else:
        row.prop_search(binding, "read_bone", obj.pose, "bones", text="")
        if profile.use_controls:
            row.prop_search(binding, "write_bone", obj.pose, "bones", text="")
    sub = row.row(align=True)
    if profile.use_controls:
        op = sub.operator("interpose.profile_assign", text="", icon='EYEDROPPER')
        op.role, op.which = role_id, 'READ'
        op = sub.operator("interpose.profile_assign", text="", icon='BONE_DATA')
        op.role, op.which = role_id, 'WRITE'
    else:
        op = sub.operator("interpose.profile_assign", text="", icon='EYEDROPPER')
        op.role, op.which = role_id, 'BOTH'
    if binding is not None:
        sub.operator("interpose.profile_select_role", text="", icon='RESTRICT_SELECT_OFF').role = role_id
        sub.operator("interpose.profile_clear_role", text="", icon='X').role = role_id


class INTERPOSE_MT_ProfileFiles(Menu):
    bl_label = "Rig Profile"

    def draw(self, context):
        layout = self.layout
        layout.operator("interpose.profile_load_preset", icon='PRESET')
        layout.separator()
        layout.operator("interpose.profile_import_json", icon='IMPORT')
        layout.operator("interpose.profile_export_json", icon='EXPORT')
        layout.separator()
        layout.operator("interpose.profile_add_roles", icon='ADD')


def _profile_panel_poll(context):
    obj = context.active_object
    return obj is not None and obj.type == 'ARMATURE' and len(obj.data.interpose_profile.roles) > 0


class INTERPOSE_PT_RigLimbsPanel(Panel):
    """The limbs switching between IK and FK: how the add-on snaps them before and after a generation"""
    bl_label = "IK/FK Limbs"
    bl_idname = "INTERPOSE_PT_RigLimbsPanel"
    bl_parent_id = "INTERPOSE_PT_RigProfilePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Interpose'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _profile_panel_poll(context)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        profile = obj.data.interpose_profile
        if len(profile.limbs) == 0:
            layout.label(text="No IK/FK limb: the rig is posed and written in FK", icon='INFO')
            return
        layout.template_list("INTERPOSE_UL_Limbs", "limbs", profile, "limbs", profile, "limbs_active_index", rows=2)
        if 0 <= profile.limbs_active_index < len(profile.limbs):
            limb = profile.limbs[profile.limbs_active_index]
            box = layout.box()
            box.prop_search(limb, "switch_bone", obj.pose, "bones")
            box.prop(limb, "switch_property")
            box.prop(limb, "fk_value")
            box.label(text="FK controls, and the bones they follow")
            for pair in limb.controls:
                row = box.row(align=True)
                row.prop_search(pair, "fk_control", obj.pose, "bones", text="")
                row.label(icon='FORWARD')
                row.prop_search(pair, "followed_bone", obj.pose, "bones", text="")
            if len(limb.ik_controls) > 0:
                box.label(text="IK controls (their keys make key poses)")
                for ref in limb.ik_controls:
                    box.prop_search(ref, "bone", obj.pose, "bones", text="")
            if len(limb.ik_snap) > 0:
                box.label(text="IK snap (after generating, in order)")
                for snap in limb.ik_snap:
                    row = box.row(align=True)
                    row.prop_search(snap, "ik_control", obj.pose, "bones", text="")
                    row.prop(snap, "mode", text="")
                    sub = row.row(align=True)
                    sub.enabled = snap.mode != 'REST'
                    sub.prop_search(snap, "followed_bone", obj.pose, "bones", text="")
            else:
                box.label(text="No IK snap: the limb plays in FK after generating", icon='INFO')
        layout.operator("interpose.snap_fk_to_ik", icon='SNAP_ON')


class INTERPOSE_PT_RigAdvancedPanel(Panel):
    """Per role: how the rest pose difference is compensated, and which bones carry the root motion"""
    bl_label = "Advanced"
    bl_idname = "INTERPOSE_PT_RigAdvancedPanel"
    bl_parent_id = "INTERPOSE_PT_RigProfilePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Interpose'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _profile_panel_poll(context)

    def draw(self, context):
        from .core.roles import get_role
        layout = self.layout
        for item in context.active_object.data.interpose_profile.roles:
            row = layout.split(factor=0.4, align=True)
            row.label(text=get_role(item.role).label if item.role else "?")
            sub = row.row(align=True)
            sub.prop(item, "offset_mode", text="")
            sub.prop(item, "use_translation", text="", icon='CON_LOCLIKE', toggle=True)


def worker_status(backend):
    """The backend's model, for the panel and the animation editors' headers: (label, icon, start button text or
    "", stop button shown, error message or "")"""
    worker = registry.existing_worker(backend.id)
    if worker is None or worker.state == process.STOPPED:
        return "Stopped", 'RADIOBUT_OFF', "Start", False, worker.error if worker is not None else ""
    if worker.state == process.STARTING:
        label, icon = "Starting", 'SORTTIME'
    elif worker.busy and not worker.loaded:
        label, icon = "Loading", 'SORTTIME'
    elif worker.busy:
        label, icon = "Busy", 'SORTTIME'
    elif worker.loaded:
        label, icon = "Model loaded", 'CHECKMARK'
    else:
        label, icon = "Running", 'RADIOBUT_ON'
    start = "Load" if not worker.loaded and not worker.busy else ""
    return label, icon, start, True, worker.error or ""


def draw_progress(layout, task, width=None):
    """The running generation's progress bar and its cancel button"""
    row = layout.row(align=True)
    if width is not None:
        row.ui_units_x = width
    row.progress(factor=task.fraction, type='BAR', text=f"{task.message} {task.fraction * 100:.0f}%")
    row.operator("interpose.cancel_generation", text="", icon='CANCEL')


class INTERPOSE_PT_GeneratePanel(Panel):
    """Generate the in-betweens of the character with the active backend"""
    bl_label = "Generate"
    bl_idname = "INTERPOSE_PT_GeneratePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Interpose'

    def draw(self, context):
        layout = self.layout
        backend = active_backend(context)

        row = layout.row(align=True)
        row.label(text=f"Backend: {backend.label}", icon='OUTLINER_OB_ARMATURE')
        props = row.operator("preferences.addon_show", text="", icon='PREFERENCES')
        props.module = ADDON_ID

        from .model_setup import setup_problem
        problem = setup_problem(context, backend)
        label, icon, start, stop, error = worker_status(backend)
        row = layout.row(align=True)
        if problem:
            row.label(text=f"{problem}: see the add-on's preferences (Models)", icon='ERROR')
            start = ""
        else:
            row.label(text=label, icon=icon)
        if start:
            row.operator("interpose.backend_start", text=start, icon='PLAY')
        if stop:
            row.operator("interpose.backend_stop", text="Stop", icon='PAUSE')
        if error:
            box = layout.box()
            for line in error.splitlines()[:6]:
                box.label(text=line, icon='ERROR')

        rig, state = get_character(context)
        if rig is None:
            layout.label(text="Select the character's armature", icon='INFO')
            return
        layout.label(text=f"Character: {rig.name}", icon='ARMATURE_DATA')
        draw_profile_status(layout, rig)
        blocked = rig_problem(context)
        if blocked is not None:
            draw_rig_problem(layout, blocked)
        if len(state.segments) > 0:
            problem = draw_segments(context, layout, rig, state, backend)
        else:
            caps = backend.capabilities
            if caps.prompt:
                layout.prop(state, "prompt", text="")
            if caps.seed:
                layout.prop(state, "seed")
            problem = draw_range(context, layout, rig, state, backend)
            if caps.prompt:
                layout.operator("interpose.segment_add", icon='SEQ_STRIP_META')

        task = generation.current_task
        if task is not None:
            draw_progress(layout, task)
        else:
            if len(state.segments) == 0:
                # The first generation: it becomes prompt segment 1. With segments, the segment's own button
                # generates it, and the timeline's Generate the whole track
                row = layout.row()
                row.enabled = not problem and blocked is None
                row.operator("interpose.generate_inbetweens", text="Generate", icon='ANIM')
            layout.operator("interpose.clear_generated_keys", icon='TRASH')


RIG_SETUP_PANEL = "INTERPOSE_PT_RigProfilePanel"


def rig_problem(context):
    """Why Generate can't start from here, as (message, the rig setup fixes it), or None: the character must be the
    active object, in Pose Mode, with a rig profile (its own or one recognized) holding the required bones, and no
    error at its last check (Generate runs the check)"""
    from . import rig_check
    from .core.roles import missing_required
    from .profile_operators import detect_profile, last_check
    rig, _state = get_character(context)
    active = context.active_object
    if rig is None or active != rig:
        return "Select the character's armature in Pose Mode", False
    if rig.mode != 'POSE':
        return "Enter Pose Mode to generate", False
    if not rig.is_editable:
        return f"'{rig.name}' is linked: make a library override", False
    profile = rig.data.interpose_profile
    if len(profile.roles) == 0:
        if detect_profile(rig.data) is None:
            return f"{rig.name}: rig not set up", True
        return None
    if missing_required([b.role for b in profile.roles if b.read_bone]):
        return f"{rig.name}: rig setup incomplete", True
    try:
        problems = last_check(rig.data, profile.to_core())
    except ValueError as e:
        return f"{rig.name}: {e}", True
    if problems and any(p.level == rig_check.ERROR for p in problems):
        return f"{rig.name}: the rig check failed", True
    return None


def draw_rig_problem(layout, problem):
    """The rig problem in a row, with the button opening the rig setup when it fixes it"""
    message, fixable = problem
    row = layout.row(align=True)
    row.label(text=message, icon='ERROR' if fixable else 'INFO')
    if fixable:
        props = row.operator("wm.call_panel", text="Set Up Rig...", icon='ARMATURE_DATA')
        props.name, props.keep_open = RIG_SETUP_PANEL, True


def _error(layout, text, width=48):
    """An error message as labels, cut into lines"""
    import textwrap
    for i, line in enumerate(textwrap.wrap(text, width) if text else []):
        layout.label(text=line, icon='ERROR' if i == 0 else 'BLANK1')


def draw_profile_status(layout, rig):
    """Where the character's rig profile comes from"""
    from .profile_operators import detect_profile, source_label
    profile = rig.data.interpose_profile
    if len(profile.roles) > 0:
        layout.label(text=f"Rig: {source_label(profile.source)}", icon='OUTLINER_DATA_ARMATURE')
        return
    detected = detect_profile(rig.data)
    if detected is not None:
        layout.label(text=f"Rig: {source_label(detected[0])} (detected)", icon='OUTLINER_DATA_ARMATURE')
    else:
        _error(layout, "Rig not set up: open the Rig Setup panel")


def draw_range(context, layout, rig, state, backend):
    """The frames the next generation covers, and why the backend can't generate them ("" if it can)"""
    box = layout.box()
    box.row().prop(state, "range_mode", expand=True)
    if state.range_mode == 'CUSTOM':
        row = box.row(align=True)
        row.prop(state, "range_start")
        row.operator("interpose.range_start_here", text="", icon='TIME')
        row.prop(state, "range_duration")
    scene = context.scene
    fps = scene.render.fps / scene.render.fps_base
    from .profile_operators import detect_profile
    rig_profile = rig.data.interpose_profile.to_core()
    detected = detect_profile(rig.data) if not rig_profile.roles else None
    try:
        start, end, key_frames = generation.generation_range(rig, detected[1] if detected else rig_profile)
    except ValueError as e:
        _error(box, str(e))
        return str(e)
    keys = ", ".join(str(f) for f in key_frames[:6]) + (" ..." if len(key_frames) > 6 else "")
    box.label(text=f"Frames {start}-{end} ({(end - start + 1) / fps:.1f} s)", icon='TIME')
    box.label(text=f"{len(key_frames)} key poses" + (f": {keys}" if key_frames else " (prompt only)"),
              icon='KEYFRAME')
    problem = backend.range_problem(start, end, fps, len(key_frames))
    _error(box, problem)
    return problem


def draw_segments(context, layout, rig, state, backend):
    """The active prompt segment (chosen in the timeline, or with the arrows), the buttons editing the track, and
    why the backend can't generate it ("" if it can)"""
    from . import segment_track
    count = len(state.segments)
    item = segment_track.active_segment(state)
    row = layout.row(align=True)
    row.operator("interpose.segment_step", text="", icon='TRIA_LEFT').step = -1
    row.label(text=f"Segment {state.segments_active_index + 1} / {count}", icon='SEQ_STRIP_META')
    row.operator("interpose.segment_step", text="", icon='TRIA_RIGHT').step = 1
    row.separator()
    row.operator("interpose.segment_add", text="", icon='ADD')
    row.operator("interpose.segment_remove", text="", icon='REMOVE')
    row.operator("interpose.segment_split", text="", icon='MOD_EDGESPLIT')
    caps = backend.capabilities
    if item is not None:
        if caps.prompt:
            layout.prop(item, "prompt", text="")
        else:
            layout.label(text=f"{backend.label} takes no prompt", icon='INFO')
        row = layout.row(align=True)
        row.prop(item, "frame_start")
        row.prop(item, "frame_end")
        if caps.seed:
            layout.prop(item, "seed")
        state_label = {'NEW': "Not generated yet", 'MODIFIED': "Edited since the last generation"}
        label = state_label.get(segment_track.segment_state(item))
        if label:
            layout.label(text=label, icon='INFO')
        layout.operator("interpose.regenerate_segment", text=f"{segment_track.generate_verb(item)} Segment",
                        icon='FILE_REFRESH')

    box = layout.box()
    scene = context.scene
    fps = segment_track.scene_fps(scene)
    track = segment_track.read_track(state)
    start, end = track[0].start_frame, track[-1].end_frame
    from .segment_operators import character_profile
    rig_profile = character_profile(rig)
    if rig_profile is None:
        problem = "No rig profile"
        _error(box, problem)
        return problem
    try:
        key_frames = [f for f in generation.find_key_frames(rig, rig_profile) if start <= f <= end]
    except ValueError as e:
        _error(box, str(e))
        return str(e)
    keys = ", ".join(str(f) for f in key_frames[:6]) + (" ..." if len(key_frames) > 6 else "")
    box.label(text=f"Track: frames {start}-{end} ({(end - start + 1) / fps:.1f} s), {count} segments", icon='TIME')
    box.label(text=f"{len(key_frames)} key poses" + (f": {keys}" if key_frames else " (prompts only)"),
              icon='KEYFRAME')
    if not caps.prompt_segments and count > 1:
        box.label(text=f"{backend.label}: segments generated one by one, no transition", icon='INFO')
    problem = backend.segments_problem(track, fps, key_frames)
    _error(box, problem)
    return problem


### The animation editors' headers: everything from the timeline

class INTERPOSE_MT_EditorMenu(Menu):
    """Interpose in the animation editors: generate, the prompt segments, the model"""
    bl_idname = "INTERPOSE_MT_editor_menu"
    bl_label = "Interpose"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_DEFAULT'
        backend = active_backend(context)
        rig, state = get_character(context)
        if rig is None:
            layout.label(text="Select the character's armature", icon='INFO')
        else:
            layout.label(text=f"Character: {rig.name}", icon='ARMATURE_DATA')
        layout.operator("interpose.generate_inbetweens", text="Generate Whole Track", icon='ANIM')
        layout.separator()
        if rig is not None and len(state.segments) > 0:
            from . import segment_track
            verb = segment_track.generate_verb(segment_track.active_segment(state))
            layout.operator("interpose.regenerate_segment", text=f"{verb} Active Segment", icon='FILE_REFRESH')
            props = layout.operator("interpose.segment_edit", text="Edit Active Segment...", icon='GREASEPENCIL')
            props.character, props.index = rig.name, state.segments_active_index
        layout.operator("interpose.segment_add", icon='ADD')
        layout.operator("interpose.segment_split", icon='MOD_EDGESPLIT')
        layout.operator("interpose.segment_remove", icon='REMOVE')
        layout.prop(context.scene, "interpose_show_segments")
        layout.separator()
        layout.operator("interpose.clear_generated_keys", icon='TRASH')
        layout.separator()
        label, icon, start, stop, error = worker_status(backend)
        layout.label(text=f"{backend.label}: {label}", icon=icon)
        if start:
            layout.operator("interpose.backend_start", text=f"{start} {backend.label}", icon='PLAY')
        if stop:
            layout.operator("interpose.backend_stop", text=f"Stop {backend.label}", icon='PAUSE')
        for line in error.splitlines()[:6]:
            layout.label(text=line, icon='ERROR')
        props = layout.operator("preferences.addon_show", text="Preferences...", icon='PREFERENCES')
        props.module = ADDON_ID


def draw_editor_header(self, context):
    """Appended to the Dope Sheet (Timeline included) and Graph Editor headers: the model's state, the
    generation's progress or the Generate button, the bands' visibility and the Interpose menu"""
    layout = self.layout
    scene = context.scene
    if not hasattr(scene, "interpose_show_segments"):
        return
    backend = active_backend(context)
    layout.separator()
    row = layout.row(align=True)
    show = scene.interpose_show_segments
    row.prop(scene, "interpose_show_segments", text="", icon='HIDE_OFF' if show else 'HIDE_ON')
    row.menu(INTERPOSE_MT_EditorMenu.bl_idname, text="", icon='OUTLINER_OB_ARMATURE')
    task = generation.current_task
    if task is not None:
        draw_progress(layout, task, width=12)
        return
    from .model_setup import setup_problem
    problem = setup_problem(context, backend)
    label, icon, start, _stop, error = worker_status(backend)
    row = layout.row(align=True)
    if problem:
        row.label(text=f"{backend.label}: {problem}", icon='ERROR' if problem != "Installing" else 'SORTTIME')
        props = row.operator("preferences.addon_show", text="", icon='PREFERENCES')
        props.module = ADDON_ID
    else:
        row.label(text=backend.label, icon='ERROR' if error else icon)
        if start:
            row.operator("interpose.backend_start", text="", icon='PLAY')
    blocked = rig_problem(context)
    if blocked is not None:
        draw_rig_problem(layout, blocked)
    else:
        layout.operator("interpose.generate_inbetweens", text="Generate", icon='ANIM')


_HEADERS = ("DOPESHEET_HT_header", "GRAPH_HT_header")


class INTERPOSE_UL_Limbs(UIList):
    """Limbs whose FK controls can be snapped to their IK pose"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False)
        row.label(text=f"{len(item.controls)} FK controls")


### Registration
classes = (
    INTERPOSE_UL_Limbs,
    INTERPOSE_PT_RigProfilePanel,
    INTERPOSE_PT_RigLimbsPanel,
    INTERPOSE_PT_RigAdvancedPanel,
    INTERPOSE_MT_ProfileFiles,
    INTERPOSE_PT_GeneratePanel,
    INTERPOSE_MT_EditorMenu,
)

def register():
    for cl in classes:
        bpy.utils.register_class(cl)
    for name in _HEADERS:
        getattr(bpy.types, name).append(draw_editor_header)


def unregister():
    for name in _HEADERS:
        getattr(bpy.types, name).remove(draw_editor_header)
    for cl in reversed(classes):
        bpy.utils.unregister_class(cl)
