"""Sphinx configuration for feral-segmentor documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "feral-segmentor"
author = "Matthew Manning"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_use_param = True
napoleon_use_rtype = True

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "torch": ("https://pytorch.org/docs/stable", None),
}

html_theme = "furo"
html_title = "feral-segmentor"
exclude_patterns = ["_build"]
