import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QStandardPaths


PREFERENCES_FILENAME = "preferences.xml"
CONFIG_DIR_ENVIRONMENT_VARIABLE = "ICESCOPY_CONFIG_DIR"


def user_config_dir():
    override = str(os.environ.get(CONFIG_DIR_ENVIRONMENT_VARIABLE, "")).strip()
    if override:
        return Path(override).expanduser().resolve()

    generic_config_dir = QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation)
    if generic_config_dir:
        return Path(generic_config_dir) / "Icescopy"
    return Path.home() / ".config" / "Icescopy"


def user_preferences_path():
    return user_config_dir() / PREFERENCES_FILENAME


def preferences_read_path(resources_dir):
    user_path = user_preferences_path()
    if user_path.is_file():
        return user_path
    return Path(resources_dir) / PREFERENCES_FILENAME


def write_preferences_tree_atomic(tree):
    destination_path = user_preferences_path()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
        dir=destination_path.parent,
    )
    os.close(temp_fd)
    try:
        tree.write(temp_path, encoding="utf-8", xml_declaration=True)
        os.replace(temp_path, destination_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return destination_path
