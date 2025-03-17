# A site customization that processes .pth files from "app_packages".
import os
import sys
import site

# Add the "app_packages" directory to the path and process its .pth files.
site.addsitedir(os.path.join(os.path.dirname(__file__), "app_packages"))

# Call the next sitecustomize script if there is one
# (https://nedbatchelder.com/blog/201001/running_code_at_python_startup.html).
del sys.modules["sitecustomize"]
this_dir = os.path.dirname(__file__)
path_index = sys.path.index(this_dir)
del sys.path[path_index]
try:
    import sitecustomize  # noqa: F401
finally:
    sys.path.insert(path_index, this_dir)