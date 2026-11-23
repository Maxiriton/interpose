"""The models' own errors made readable: what went wrong and what to do, worded the same for every model (no bpy).

A worker's handler calls explain() from its explain_error() (protocol.WorkerLoop sends what it returns instead of
the raw exception). The errors are recognised by their class names and messages, so nothing here imports torch or
huggingface_hub: video memory full, weights missing or damaged, the environment missing a package, a GPU the
environment can't use. Anything else is left as it is (None). The raw error's first line follows on a second line,
for the details; the whole traceback is in the worker's stderr.

The workers run offline (HF_HUB_OFFLINE): weights that a refused Hugging Face access kept from downloading show up
as missing ones here; Check Setup and the install say why (gated repository, sign-in).
"""
import sys

CHECK_SETUP = "Check Setup in the add-on's preferences (Models) shows how to fix it"

OUT_OF_MEMORY = "out_of_memory"
WEIGHTS = "weights"
ENVIRONMENT = "environment"
GPU = "gpu"

_OUT_OF_MEMORY_CLASSES = {"OutOfMemoryError"}
_OUT_OF_MEMORY_TEXT = ("cuda out of memory", "cublas_status_alloc_failed", "cudnn_status_alloc_failed",
                       "cuda error: out of memory", "not enough memory: you tried to allocate")
_WEIGHTS_CLASSES = {"LocalEntryNotFoundError", "EntryNotFoundError", "SafetensorError", "HeaderTooLarge",
                    "HeaderTooSmall", "InvalidHeaderDeserialization"}
_WEIGHTS_TEXT = ("couldn't find them in the cached files", "cannot find the requested files in the disk cache",
                 "does not appear to have a file named", "error no file named", "pytorchstreamreader failed",
                 "error while deserializing header", "incomplete metadata", "unexpected eof",
                 "is not a valid model identifier", "offline mode is enabled")
_ENVIRONMENT_CLASSES = {"ModuleNotFoundError", "ImportError"}
_ENVIRONMENT_TEXT = ("dll load failed",)
_GPU_TEXT = ("no kernel image is available", "cuda driver version is insufficient", "torch not compiled with cuda",
             "found no nvidia driver")


def _chain(error):
    """error, then the errors it was raised from or while handling"""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        yield error
        error = error.__cause__ or error.__context__


def kind(error):
    """OUT_OF_MEMORY, WEIGHTS, ENVIRONMENT, GPU or None. A missing package counts only for the error itself: an
    ImportError a library caught earlier (an optional dependency) is often the context of an unrelated error."""
    for depth, e in enumerate(_chain(error)):
        name, text = type(e).__name__, str(e).lower()
        if name in _OUT_OF_MEMORY_CLASSES or any(t in text for t in _OUT_OF_MEMORY_TEXT):
            return OUT_OF_MEMORY
        if any(t in text for t in _GPU_TEXT):
            return GPU
        if name in _WEIGHTS_CLASSES or any(t in text for t in _WEIGHTS_TEXT):
            return WEIGHTS
        if depth == 0 and (name in _ENVIRONMENT_CLASSES or any(t in text for t in _ENVIRONMENT_TEXT)):
            return ENVIRONMENT
    return None


def raw(error):
    """The error as the worker used to send it, on one line"""
    lines = str(error).strip().splitlines()
    return f"{type(error).__name__}: {lines[0] if lines else ''}".rstrip(": ")


def explain(error, label, memory_hint=""):
    """A readable message for error (the model called label), or None if it isn't a known one. memory_hint: what
    else frees video memory with this model, as the end of a sentence ("choose the 4-bit text encoder...")."""
    found = kind(error)
    if found is None:
        return None
    if found == OUT_OF_MEMORY:
        todo = "close the other programs using the GPU, or generate a shorter range"
        if memory_hint:
            todo = f"close the other programs using the GPU, generate a shorter range, or {memory_hint}"
        message = f"Not enough video memory for {label}: {todo}."
    elif found == WEIGHTS:
        message = f"{label}'s weights are missing or damaged: {CHECK_SETUP}."
    elif found == ENVIRONMENT:
        message = f"{label}'s environment is missing a package: {CHECK_SETUP}."
    else:
        message = f"The GPU can't run {label}: update the NVIDIA driver. If it still fails, {CHECK_SETUP}."
    return f"{message}\n{raw(error)}"


def release_gpu_cache():
    """Give the video memory torch keeps cached back to the GPU (after running out of it), if torch is loaded"""
    torch = sys.modules.get("torch")
    try:
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001 - best effort, the error being reported matters more
        pass
