"""Cross-session messaging for spellbook.

Provides an in-memory message bus for real-time coordination between
any spellbook-connected coding sessions.
"""

from spellbook.messaging.bus import MessageBus, MessageEnvelope, message_bus

__all__ = ["MessageBus", "MessageEnvelope", "message_bus"]
