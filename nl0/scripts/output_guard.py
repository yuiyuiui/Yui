"""Historical Responses event classification for retained execution ledgers.

Current native role control uses native_client events, not raw-stream monitors.
"""
TERMINAL_EVENTS = {'response.completed', 'response.incomplete', 'response.failed'}


def substantive_event(event):
    """Observable output progress, as distinct from a connection heartbeat."""
    kind=event.get('type','')
    if kind.endswith('.delta'):
        delta=event.get('delta')
        return isinstance(delta,str) and bool(delta.strip())
    return kind in {'response.output_item.added','response.output_item.done',
                    'response.content_part.added','response.content_part.done'}
