"""Example builds owned by the BlockForge project, kept as code that regenerates them (see README.md).

EXAMPLES = {name: module}; every module has TITLE, SOURCE, LICENCE and code() -> build script text.
"""
from . import good_cottage, good_manor, good_village

EXAMPLES = {"good_cottage": good_cottage, "good_manor": good_manor, "good_village": good_village}


def code(name):
    """The build script of an example by name."""
    if name not in EXAMPLES:
        raise KeyError(f"unknown example {name!r}; examples: {', '.join(sorted(EXAMPLES))}")
    return EXAMPLES[name].code()
