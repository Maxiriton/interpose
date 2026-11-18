"""The models' setup in Blender: the preferences' Models section, a model not installed, an existing environment
checked, the worker's command.

    blender -b --factory-startup --python tests/blender/test_model_setup.py -- <scratch dir> [<Kimodo python>]

Nothing is downloaded: the install itself is tested with fake steps in tests/unit/test_setup.py, and for real only by
hand (it downloads several GB). With a Kimodo environment, its setup is checked (a few seconds: it imports torch).
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
from test_panel import CheckingLayout  # noqa: E402


def refused(operator, **kwargs):
    """The operator stops with an error"""
    try:
        return operator(**kwargs) == {'CANCELLED'}
    except RuntimeError:
        return True


def draw(function, *args):
    errors = []
    function(CheckingLayout(errors), *args)
    return errors


class LabelLayout(CheckingLayout):
    """A CheckingLayout keeping the labels' text"""

    def __init__(self, errors, labels):
        super().__init__(errors)
        self.labels = labels

    def _sub(self, *_args, **_kwargs):
        return LabelLayout(self.errors, self.labels)

    row = column = box = split = _sub

    def label(self, **kwargs):
        super().label(**kwargs)
        self.labels.append(kwargs.get("text", ""))


def drawn_labels(function, *args):
    labels = []
    function(LabelLayout([], labels), *args)
    return labels


class OperatorLayout(LabelLayout):
    """A LabelLayout keeping the operators' text and the properties drawn"""

    def __init__(self, errors, labels, operators=None, props=None):
        super().__init__(errors, labels)
        self.operators = [] if operators is None else operators
        self.props = [] if props is None else props

    def _sub(self, *_args, **_kwargs):
        return OperatorLayout(self.errors, self.labels, self.operators, self.props)

    row = column = box = split = _sub

    def operator(self, idname, **kwargs):
        self.operators.append((idname, kwargs.get("text", ""), kwargs.get("icon"), kwargs.get("depress")))
        return super().operator(idname, **kwargs)

    def prop(self, data, name, **kwargs):
        self.props.append(name)
        return super().prop(data, name, **kwargs)


def check_model_choices(checks, context, prefs, model_setup, registry):
    """Fewer choices for animators: ARDY first, its 8-bit or 4-bit text encoder with the video memory each needs, the
    variants behind the Developer option; the encoder the GPU fits when never chosen"""
    from interpose.backends.ardy import backend as ardy_backend
    from interpose.backends.setup.spec import Gpu, Machine
    checks.check(registry.BACKENDS[0].id == "ardy" and registry.visible()[0].id == "ardy", "ARDY is the default model")
    ardy = registry.get("ardy")
    settings = prefs.settings_ardy
    small = Machine("windows", "x86_64", (Gpu("RTX 3070", 8192, (8, 6)),))
    big = Machine("windows", "x86_64", (Gpu("RTX 3090", 24576, (8, 6)),))
    checks.check(not settings.is_property_set("text_encoder")
                 and ardy_backend.chosen_text_encoder(settings, small) == "NF4"
                 and ardy_backend.chosen_text_encoder(settings, big) == "INT8",
                 "never chosen: the 4-bit text encoder on 8 GB, the 8-bit one on 24 GB")
    checks.check(ardy.requirements(small, settings).min_vram_gb == 6.2, "an 8 GB GPU installs the 4-bit text encoder")

    def drawn(developer, memory):
        layout = OperatorLayout([], [])
        ardy.draw_settings(layout, settings, developer, memory)
        return layout

    plain = drawn(False, 8.0)
    encoders = [(text, icon, depress) for idname, text, icon, depress in plain.operators
                if idname == "interpose.backend_setting"]
    checks.check([text for text, _i, _d in encoders] == ["8-bit: 9.5 GB", "4-bit: 6.2 GB"] and "model" not in plain.props,
                 f"without Developer: the 8-bit and 4-bit text encoders with their memory, no model choice ({encoders})")
    checks.check([icon for _t, icon, _d in encoders] == ['ERROR', 'NONE'],
                 "on an 8 GB GPU, the 8-bit text encoder is marked as too big")
    dev = drawn(True, 24.0)
    texts = [text for idname, text, _i, _d in dev.operators if idname == "interpose.backend_setting"]
    checks.check(len(texts) == 3 and "model" in dev.props, f"with Developer: the full text encoder and the model ({texts})")

    result = bpy.ops.interpose.backend_setting(backend_id="ardy", name="text_encoder", value="NF4")
    checks.check(result == {'FINISHED'} and settings.text_encoder == "NF4" and settings.is_property_set("text_encoder")
                 and ardy_backend.chosen_text_encoder(settings, big) == "NF4",
                 "a text encoder chosen by the user is kept, whatever the GPU")
    status = model_setup.vram_status(context, ardy)
    checks.check(status is not None and "6.2 GB" in status[0], f"the memory the chosen setting needs is shown ({status})")
    kimodo_layout = OperatorLayout([], [])
    registry.get("kimodo").draw_settings(kimodo_layout, prefs.settings_kimodo, False, 24.0)
    checks.check("model" not in kimodo_layout.props, "Kimodo: no model choice without Developer")
    settings.property_unset("text_encoder")


def main(scratch, kimodo_python=None):
    checks = bootstrap.Checks("test_model_setup")
    bootstrap.register_addon()
    from interpose import model_setup, ui
    from interpose.backends import registry
    from interpose.backends.setup import checks as setup_checks

    prefs = bootstrap.set_backend("kimodo")
    prefs.models_folder = os.path.join(scratch, "models")
    kimodo = registry.get("kimodo")
    interpolate = registry.get("interpolate")
    context = bpy.context

    checks.check(hasattr(prefs, "setup_kimodo") and not hasattr(prefs, "setup_interpolate"),
                 "only a backend with something to install gets an environment setting")
    checks.check(model_setup.models_root(context) == os.path.normpath(os.path.join(scratch, "models")),
                 "the models' folder comes from the preferences")
    checks.check(model_setup.setup_problem(context, kimodo) == "Not installed", "a model never installed says so")
    try:
        model_setup.worker_for(context, kimodo)
        checks.check(False, "no worker for a model not installed")
    except ValueError as e:
        checks.check("isn't installed" in str(e), f"no worker for a model not installed ({e})")
    checks.check(model_setup.setup_problem(context, interpolate) == "", "the interpolation backend needs nothing")
    worker = model_setup.worker_for(context, interpolate)
    checks.check(worker.command[0] == sys.executable, "the interpolation worker runs with Blender's Python")

    checks.check(draw(model_setup.draw_models, context, prefs) == [], "the Models section draws")
    prefs.developer = True
    checks.check(draw(model_setup.draw_models, context, prefs) == [], "the Models section draws, developer on")
    labels = drawn_labels(model_setup.draw_models, context, prefs)
    others = [b.label for b in registry.visible(True) if b.id != "kimodo" and b.label in labels]
    checks.check(kimodo.label in labels and not others,
                 f"only the chosen backend is drawn ({kimodo.label}; others drawn: {others})")
    check_model_choices(checks, context, prefs, model_setup, registry)
    header = type("Header", (), {"layout": None})()
    errors = []
    header.layout = CheckingLayout(errors)
    ui.draw_editor_header(header, context)
    checks.check(errors == [], "the editors' header draws with a model not installed")

    if not bpy.app.online_access:
        checks.check(refused(bpy.ops.interpose.model_install, backend_id="kimodo"),
                     "no install without online access")

    # An existing environment
    setup = prefs.setup_kimodo
    setup.environment = 'EXISTING'
    setup.python = os.path.join(scratch, "nowhere", "python.exe")
    checks.check(model_setup.setup_problem(context, kimodo) == "Python not found", "an existing Python not found")
    run = model_setup.start_check(context, kimodo).wait(30)
    checks.check(run.items[0].fix == setup_checks.FIX_PYTHON, "the check asks for another Python")
    checks.check(refused(bpy.ops.interpose.model_remove, backend_id="kimodo"),
                 "an existing environment isn't removed")

    if kimodo_python:
        setup.python = kimodo_python
        checks.check(model_setup.setup_problem(context, kimodo) == "", "an existing Kimodo environment is used")
        worker = model_setup.worker_for(context, kimodo)
        venv = os.path.dirname(os.path.dirname(kimodo_python))
        checks.check(os.path.normcase(worker.command[0]) == os.path.normcase(os.path.normpath(kimodo_python))
                     and os.path.normcase(worker.env["KIMODO_TEXT_ENCODER_DIR"])
                     == os.path.normcase(os.path.join(venv, "llm2vec-model")),
                     "the Kimodo worker gets the existing environment's text encoder")
        run = model_setup.start_check(context, kimodo).wait(300)
        for item in run.items:
            print(f"    {item.level:8} {item.label}: {item.message}")
        checks.check(setup_checks.ready(run.items), "the existing Kimodo environment is ready")
        checks.check(draw(model_setup.draw_models, context, prefs) == [], "the Models section draws a check")

    installed = os.environ.get("INTERPOSE_MODELS_FOLDER")
    if installed:
        # Kimodo as the add-on installed it
        setup.environment = 'MANAGED'
        prefs.models_folder = installed
        checks.check(model_setup.setup_problem(context, kimodo) == "", "the installed Kimodo is found")
        layout = model_setup.layout_for(context, kimodo)
        worker = model_setup.worker_for(context, kimodo)
        checks.check(os.path.normcase(worker.env["KIMODO_TEXT_ENCODER_DIR"])
                     == os.path.normcase(os.path.join(layout.backend_dir, "llm2vec-model")),
                     "the installed Kimodo's worker gets its text encoder")
        run = model_setup.start_check(context, kimodo).wait(300)
        for item in run.items:
            print(f"    {item.level:8} {item.label}: {item.message}")
        checks.check(setup_checks.ready(run.items), "the installed Kimodo is ready")
    checks.finish()


if __name__ == "__main__":
    args = bootstrap.script_args()
    main(args[0], args[1] if len(args) > 1 else None)
