"""Deprecated alias package.

Nothing imports this on purpose. `pip install ncel` installs `northcel`, which
provides the `northcel` command and the `ncel` alias; this module only exists so
the distribution has a file to ship.
"""

RAISED = "ncel is a deprecated alias: use `northcel` (install `pip install northcel`)."
