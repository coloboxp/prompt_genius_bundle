"""Custom PyInstaller hook for torch.

The stock ``hook-torch.py`` in ``pyinstaller-hooks-contrib`` calls
``collect_submodules('torch')`` in an isolated subprocess that crashes on
recent torch versions on macOS/Apple Silicon (SIGABRT, exit code -6). This
override skips that probe and instead lists the torch surface area
sentence-transformers actually needs.
"""

from PyInstaller.utils.hooks import collect_data_files

# Bring along torch's data files (compiled kernels, shared libs, etc.) — these
# are what makes the actual import work at runtime.
datas = collect_data_files("torch", include_py_files=False)

# Minimal hidden imports — only the subpackages sentence-transformers touches.
# If you ever swap to a model that uses other torch features, extend this list.
hiddenimports = [
    "torch",
    "torch._C",
    "torch._classes",
    "torch.nn",
    "torch.nn.functional",
    "torch.nn.modules",
    "torch.nn.modules.activation",
    "torch.nn.modules.linear",
    "torch.nn.modules.normalization",
    "torch.nn.modules.sparse",
    "torch.nn.modules.transformer",
    "torch.optim",
    "torch.serialization",
    "torch.utils",
    "torch.utils.data",
    "torch.utils._import_utils",
    "torch.cuda",       # imported even on CPU-only systems; lazy at runtime
    "torch.backends",
    "torch.backends.cpu",
    "torch.backends.mps",
]
