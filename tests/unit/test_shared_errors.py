"""The models' errors made readable (backends/shared/errors.py), the same for every model. No Blender, no torch."""
import os
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from backends.shared import errors  # noqa: E402


# Named like the libraries' own
class OutOfMemoryError(RuntimeError):
    pass


class LocalEntryNotFoundError(OSError):
    pass


class SafetensorError(Exception):
    pass


def chained(outer, inner, cause=True):
    """outer raised from inner (cause) or while handling it (context)"""
    try:
        try:
            raise inner
        except type(inner) as e:
            if cause:
                raise outer from e
            raise outer
    except type(outer) as e:
        return e


class TestKinds(unittest.TestCase):
    def test_out_of_memory(self):
        for error in (OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB (GPU 0; 24 GiB total)"),
                      RuntimeError("CUDA error: CUBLAS_STATUS_ALLOC_FAILED when calling `cublasCreate(handle)`"),
                      RuntimeError("CUDA error: out of memory")):
            self.assertEqual(errors.kind(error), errors.OUT_OF_MEMORY, error)

    def test_weights(self):
        for error in (LocalEntryNotFoundError("Cannot find the requested files in the disk cache and outgoing "
                                              "traffic has been disabled."),
                      OSError("We couldn't connect to 'https://huggingface.co' to load the files, and couldn't find "
                              "them in the cached files."),
                      SafetensorError("Error while deserializing header: MetadataIncompleteBuffer"),
                      RuntimeError("PytorchStreamReader failed reading zip archive: failed finding central "
                                   "directory")):
            self.assertEqual(errors.kind(error), errors.WEIGHTS, error)

    def test_environment_and_gpu(self):
        self.assertEqual(errors.kind(ModuleNotFoundError("No module named 'bitsandbytes'")), errors.ENVIRONMENT)
        self.assertEqual(errors.kind(OSError("[WinError 126] DLL load failed while importing _C")),
                         errors.ENVIRONMENT)
        self.assertEqual(errors.kind(RuntimeError("CUDA error: no kernel image is available for execution on "
                                                  "the device")), errors.GPU)
        self.assertEqual(errors.kind(AssertionError("Torch not compiled with CUDA enabled")), errors.GPU)

    def test_unknown(self):
        self.assertIsNone(errors.kind(RuntimeError("the model failed")))
        self.assertIsNone(errors.explain(ValueError("Unexpected token size: 3 frames."), "ARDY"))

    def test_chain(self):
        """Found in the error it was raised from or while handling, as libraries wrap them"""
        error = chained(OSError("Can't load the model 'x'."),
                        LocalEntryNotFoundError("Cannot find the requested files in the disk cache"), cause=False)
        self.assertEqual(errors.kind(error), errors.WEIGHTS)
        error = chained(RuntimeError("generation failed"), OutOfMemoryError("CUDA out of memory."))
        self.assertEqual(errors.kind(error), errors.OUT_OF_MEMORY)

    def test_optional_import_in_the_context(self):
        """An ImportError a library caught (an optional package) doesn't make an unrelated error a missing one"""
        error = chained(RuntimeError("the model failed"), ImportError("No module named 'flash_attn'"), cause=False)
        self.assertIsNone(errors.kind(error))


class TestMessages(unittest.TestCase):
    def test_out_of_memory(self):
        error = OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB.\nSee the documentation.")
        first, second = errors.explain(error, "ARDY").splitlines()
        self.assertEqual(first, "Not enough video memory for ARDY: close the other programs using the GPU, or "
                                "generate a shorter range.")
        self.assertEqual(second, "OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB.")
        message = errors.explain(error, "ARDY", "choose the 4-bit text encoder in the add-on's preferences")
        self.assertTrue(message.startswith("Not enough video memory for ARDY: close the other programs using the "
                                           "GPU, generate a shorter range, or choose the 4-bit text encoder"), message)

    def test_fixes(self):
        self.assertIn("Kimodo's weights are missing or damaged: Check Setup in the add-on's preferences (Models)",
                      errors.explain(LocalEntryNotFoundError("Cannot find the requested files in the disk cache"),
                                     "Kimodo"))
        self.assertIn("ARDY's environment is missing a package: Check Setup",
                      errors.explain(ModuleNotFoundError("No module named 'bitsandbytes'"), "ARDY"))
        self.assertIn("The GPU can't run ARDY: update the NVIDIA driver",
                      errors.explain(RuntimeError("CUDA driver version is insufficient for CUDA runtime version"),
                                     "ARDY"))

    def test_release_gpu_cache_without_torch(self):
        errors.release_gpu_cache()  # torch isn't loaded here: nothing to do, no error

    def test_workers_explain_their_errors(self):
        """Each model's worker gives its errors to explain(), with its own label"""
        for backend in ("kimodo", "ardy"):
            with open(os.path.join(REPO, "backends", backend, "worker.py"), encoding="utf-8") as f:
                source = f.read()
            self.assertIn("def explain_error(self, error):", source, backend)
            self.assertIn("errors.explain(error, LABEL", source, backend)


if __name__ == "__main__":
    unittest.main()
