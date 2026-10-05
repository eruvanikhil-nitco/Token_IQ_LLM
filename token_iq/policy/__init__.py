"""Decisions the gateway asks Token IQ to make while serving a request.

Not hooks in the gateway's sense of the word, which are logger subclasses. These are policy:
which way a team may reach the models, what a plan allows, what is kept in the spend log, and
who may read a credential. Each is a function the request path calls and nothing more.
"""
