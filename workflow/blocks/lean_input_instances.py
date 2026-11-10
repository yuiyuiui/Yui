"""Resolve an explicitly specialized Lean input to its real declaration."""
from typing import NamedTuple


class Source(NamedTuple):
    name: str
    levels: list
    takes_context: bool


def resolve(key, nodes, prepared):
    if key in nodes:
        return Source('__connected_' + key, nodes[key].get('universe_params', []), True)
    if key in prepared:
        row = prepared[key]
        return Source('YuiBasis.' + row['basis'], row['levels'], False)
    return None


def suffix(levels):
    return '.{' + ', '.join(levels) + '}' if levels else ''


def application(source, levels, context_arguments):
    args = context_arguments if source.takes_context else []
    return '(' + ' '.join(['@' + source.name + suffix(levels), *args]) + ')'
