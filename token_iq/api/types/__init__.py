"""Request and response shapes for the routers next door.

Separate from the domain types because these are a wire contract: changing one changes what a
client receives, so they move only when an endpoint's response is meant to change.
"""
