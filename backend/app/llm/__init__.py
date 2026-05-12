"""LLM credential management.

The agent loop, conversations and tools live under ``app.agent``.
This module concerns itself only with the credentials that the
workspace admin registers (BYOK) so that ``app.agent`` can later
pick one at chat time, decrypt it, and talk to the provider.
"""
