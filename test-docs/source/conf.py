# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
# sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('../..'))


# This is an elaborate hack to insert write property into _all_
# mock decorators. It is needed for getting @attribute to build
# in mocked out tango.server
# see https://github.com/sphinx-doc/sphinx/issues/6709
from sphinx.ext.autodoc.mock import _MockObject


def call_mock(self, *args, **kw):
    from types import FunctionType, MethodType

    if args and type(args[0]) in [type, FunctionType, MethodType]:
        # Appears to be a decorator, pass through unchanged
        args[0].write = lambda x: x
        return args[0]
    return self


_MockObject.__call__ = call_mock
_MockObject.__getitem__ = lambda self, key: _MockObject()
_MockObject.__mul__ = lambda self, other: _MockObject()
_MockObject.__sub__ = lambda self, other: _MockObject()
_MockObject.__truediv__ = lambda self, other: _MockObject()
# hack end




# -- Project information -----------------------------------------------------

project = 'SKA Low MCCS tests'
copyright = '2021, SKA Software, MCCS Team'
author = 'SKA Software, MCCS Team'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    # "sphinx_autodoc_typehints",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

autodoc_mock_imports = ["pytest_bdd", "scipy", "ska", "ska_tango_base", "tango"]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']


intersphinx_mapping = {
    "https://docs.python.org/3/": None,
    "pytango": ("https://pytango.readthedocs.io/en/stable/", None),
    "pytest": ("https://docs.pytest.org/en/stable/", None),
    "ska_low_mccs": ("https://developer.skatelescope.org/projects/ska-low-mccs/en/master/", None),
    "ska-tango-base": (
        "https://developer.skatelescope.org/projects/ska-tango-base/en/latest/",
        None,
    ),
}

nitpick_ignore = [
    ("py:class", "callable"),
    ("py:class", "contextmanager"),  # actually a std type -- impossible to link to?
    ("py:class", "pytest.config.Config"),  # something not right at pytest end
    ("py:class", "pytest_mock.module_mocker"),  # pytest_mock has no sphinx docs
    ("py:class", "pytest_mock.mocker"),  # pytest_mock has no sphinx docs
    ("py:class", "pytest_mock.mocker.Mock"),  # pytest_mock has no sphinx docs
    # workaround -- everything below here is missing ska-low-mccs documentation 
    ("py:mod", "ska.low.mccs.hardware.base_hardware"),
    ("py:mod", "ska.low.mccs.hardware.power_mode_hardware"),
    ("py:mod", "ska.low.mccs.hardware.simulable_hardware"),
    ("py:class", "ska.low.mccs.tile.tile_device.TilePowerManager"),
]
