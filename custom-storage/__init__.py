"""Custom-storage example — JSON-file ``OrchidChatStorage`` backend.

Demonstrates how integrators can plug an alternative chat persistence
layer into Orchid by subclassing :class:`OrchidChatStorage`.  See
``README.md`` in this directory for the contract and trade-offs of
this particular implementation (single-process, no migrations, suited
for demos and embedded apps — NOT production multi-tenant traffic).
"""
