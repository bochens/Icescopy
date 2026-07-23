import importlib
import importlib.metadata
import platform
from pathlib import Path

from icescopy_version import __version__


RUNTIME_DEPENDENCIES = (
    ("PySide6", "PySide6"),
    ("numpy", "numpy"),
    ("opencv-python", "cv2"),
    ("darkdetect", "darkdetect"),
    ("Pillow", "PIL"),
    ("pandas", "pandas"),
    ("scipy", "scipy"),
    ("pyqtgraph", "pyqtgraph"),
    ("av", "av"),
)


def find_resources_dir():
    module_dir = Path(__file__).resolve().parent
    candidates = (module_dir / "resources", module_dir.parent / "resources")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def main():
    failures = []
    print(f"Python {platform.python_version()} ({platform.system()} {platform.machine()})")
    try:
        installed_version = importlib.metadata.version("Icescopy")
        if installed_version != __version__:
            failures.append(
                f"version mismatch: package={installed_version}, source={__version__}"
            )
            print(
                f"FAIL Icescopy version mismatch: package={installed_version}, source={__version__}"
            )
        else:
            print(f"OK  Icescopy {installed_version}")
    except importlib.metadata.PackageNotFoundError:
        failures.append("Icescopy is not installed in this Python environment")
        print("FAIL Icescopy is not installed in this Python environment")

    for distribution_name, module_name in RUNTIME_DEPENDENCIES:
        try:
            importlib.import_module(module_name)
            version = importlib.metadata.version(distribution_name)
            print(f"OK  {distribution_name} {version}")
        except Exception as err:
            failures.append(f"{distribution_name}: {err}")
            print(f"FAIL {distribution_name}: {err}")

    resources_dir = find_resources_dir()
    for relative_path in (
        Path("preferences.xml"),
        Path("app_icons") / "IcescopyApp.png",
    ):
        asset_path = resources_dir / relative_path
        if asset_path.is_file():
            print(f"OK  resource {relative_path}")
        else:
            failures.append(f"missing resource: {asset_path}")
            print(f"FAIL missing resource: {asset_path}")

    if failures:
        print(f"Validation failed with {len(failures)} problem(s).")
        return 1
    print("Icescopy runtime validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
