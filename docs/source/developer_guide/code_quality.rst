############################
MCCS code quality guidelines
############################

MCCS is committed to writing and maintaining code of the highest
quality.

There are no shortcuts to writing quality code, but there are many
checks and metrics that can be used to measure progress and establish
quality thresholds. This page is a summary of the checks and metrics
that MCCS has implemented.

*************
Test coverage
*************
MCCS uses pytest to test its code, with the pytest-cov plugin for
measuring coverage. In accordance with the `SKA Software Testing Policy
and Strategy`_, we use branch coverage as our key coverage metric.

Some code has been deliberately excluded from coverage calculations,
such as

* Command line interface modules

* Historical code that will not be further developed, such as driver
  code for the outdated TPM 1.2.

MCCS aspires to a test coverage is 80%. Once this is achieved, we will
set guards against it dropping below that.

***********************
Code formatting / style
***********************

Black
^^^^^
MCCS uses the ``black`` code formatter to format its code. Formatting is
built into ``make lint`` and ``tox -e lint``, and there is also support for
adding it as a pre-commit hook.

The CI pipeline obviously does not format code, but does check that the
code has been blacked (i.e. that black would not make changes).

Advantages of formatting code with black are:

* More consistent, readable code

* Very clear diffs, because if code has been blacked both before and
  after, the diff should not show spurious formatting changes

Linting
^^^^^^^
MCCS uses flake8 for linting. Flake8 has excellent plugin support. The
following plugins are used:

* ``flake8-black`` - as mentioned above, this is used to check that the
  code has been blacked

* ``flake8-builtins`` - prevents use of python builtins (such as "id")
  as variable names

* ``flake8-use-fstring`` - enforces use of python f-strings rather than
  old-style format-strings or older-style %-strings

* ``pep8-naming`` - forces attribute names to follow PEP8.
  Unfortunately, the Tango community has conventions that are
  inconsistent with PEP8, such as capitalising device commands. Thus,
  certain PEP8 checks are turned off for Tango device modules
  (specifically, we use flake8's per-file-excludes configuration setting
  to ignore the N802 error code in modules that define Tango devices).

Other plugins used for docstring linting or other purposes are discussed below.

********************
Static type checking
********************

MCCS has recently begun static type checking using ``mypy``.

Static type checking requires the addition of type annotations or
"hints" to the python code. The type checker then uses those annotations
to analyse the code for logical errors.

Here's a simple example. A class initializer allows for an optional
logger to be passed in as an argument:

.. code-block:: python

   class ExampleClass:
       def __init__(self, logger=None):
           self._logger = logger

And in some other method, we have error handling code that calls

.. code-block:: python

   self._logger.error("Something went wrong")

This code contains a logical error: since the logger is optional,
``self._logger`` might be ``None`` when we try to call its error method.

This will cause a runtime error if the code is ever run; but because
this error is in error handling code, it might not have test coverage,
so the error might escape detection.

Static type checkers detect and report this kind of logical error. The
error message would be something like "Type 'None' has no 'error'
method".

***************
Code complexity
***************
The flake8 linter has a built-in McCabe cyclomatic complexity
calculator. Despite the impressive name, this is a fairly simple metric
that counts paths through a function/method. A score of 10 or more is
usually considered a problem.

In MCCS, this functionality is enabled in ``make lint`` and
``tox -e lint``, and is separately available via ``tox -e complexity``. At
present, our worst score is 10, and we guard against code that scores
higher than this.

******
To-dos
******
Points in the code where improvements are identified as needed are
marked with todos. Unfortunately there are two competing mechanisms
for this:

* Where a method is identified as overall needing improvement, or
  needing an interface update, we generally add a ``:todo:`` parameter
  into the docstring. This inserts the to-do text into the API
  documentation.

* Where a to-do annotation is required at a specific location in the
  code, a comment beginning with ``# TODO:`` or ``# FIXME:`` etc. can be
  inserted. The tox target ``tox -e todo`` will generate a report of
  these.

**********
Docstrings
**********
All public python code is documented with Sphinx/RST docstrings. The
following tools are used to maintain docstring format/style:

* To ensure our docstrings conform to PEP8 (general python style PEP),
  we don't need to do anything extra, as it is already handled by the
  flake8 linter.

* To ensure our docstrings conform to PEP257 (docstring style PEP), we
  use the flake8-docstrings extension. This also checks for 100%
  docstring coverage (but only on public methods/classes etc).

* Since we have adopted Sphinx/RST format for our docstrings, we want to
  ensure that our docstrings are valid RST. This is done with the
  flake8-rst-docstrings extension.

* The RST-format does not provide for crosslinks, but sphinx extends RST
  to support this. We cannot lint for correct crosslinks in our
  docstrings, but when we build our API documentation, we call sphinx
  with the ``-n`` ("nitpicky") flag to tell sphinx to check crosslinks
  for validity.

* Most importantly, we need our docstrings to actually document the
  python attribute that they purport to document. This is handled by
  darglint.

A final, and slightly unusual, way to verify our docstrings: our test
package is also fully documented with docstrings, including intersphinx
cross-references to our package documentation. When we build our test
documentation, it acts as an intersphinx client to our main package
documentation, helping to flush out issues in the latter.

.. _SKA Software Testing Policy and Strategy: https://developer.skao.int/en/latest/policies/ska-testing-policy-and-strategy.html