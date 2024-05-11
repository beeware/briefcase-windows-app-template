import os
from pathlib import Path


BIN_PATH = Path("src")

# Rename the stub binary we want
STUB_PATH = (
    BIN_PATH / '{% if cookiecutter.console_app %}Console{% else %}GUI{% endif %}-Stub-{{ cookiecutter.python_version|py_tag }}.exe'
)
STUB_PATH.rename(BIN_PATH / "Stub.exe")

# Delete all remaining stubs
for stub in BIN_PATH.glob("*-Stub-*.exe"):
    os.unlink(stub)
