"""The shapes Token IQ's own data takes.

None of these import from the gateway. That is deliberate and worth keeping: a type that
reaches back into the proxy makes every module holding one unable to be imported on its own,
and is how the import graph stops being a graph.
"""
