"""Provider chain traversal utilities.

The translation provider can be wrapped in multiple decorator layers
(CachingProvider, InlineQaWrapper, etc.).  This module provides a single
place to walk that chain, so callers don't duplicate the ``_inner``
traversal pattern.
"""

from __future__ import annotations

from typing import Any


def resolve_provider_attr(provider: object, attr_name: str, *, default: Any = None) -> Any:
    """Walk the provider decorator chain looking for *attr_name*.

    Traverses the linked list of ``_inner`` references until the attribute
    is found.  Returns *default* if the attribute is not found on any
    wrapper in the chain.

    This replaces the duplicated ``while current: … _inner`` pattern
    that previously existed in ``pipeline._collect_inline_qa_stats``,
    ``translate._consume_inline_qa_metadata``, and the ``CachingProvider``
    attribute delegation.
    """
    current = provider
    while current is not None:
        if hasattr(current, attr_name):
            return getattr(current, attr_name)
        current = getattr(current, "_inner", None)
    return default
