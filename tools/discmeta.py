"""Resolve private volume identifiers from the player's extraction project.

Only placeholders are committed in disc-layout.xml. tools/extract.sh writes the
original identifiers to the ignored build/digimonworld.xml using dumpsxiso.
"""
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

FIELDS = ('publisher', 'data_preparer', 'copyright')


def redact(layout):
    """Keep the layout recipe free of the original volume's identifying strings."""
    for field in FIELDS:
        layout, n = re.subn(rf'\b{field}="[^"]*"', f'{field}="@SOURCE_{field.upper()}@"', layout)
        if n != 1:
            raise ValueError(f'layout: expected one {field} identifier')
    return layout


def resolve(layout, project):
    """Fill the committed placeholders without changing XML formatting or disc bytes."""
    try:
        ids = ET.parse(project).find('.//identifiers')
    except (OSError, ET.ParseError) as e:
        raise ValueError(f'{project}: cannot read disc metadata; run tools/extract.sh with your USA disc') from e
    if ids is None:
        raise ValueError(f'{project}: no disc identifiers')
    for field in FIELDS:
        token = f'@SOURCE_{field.upper()}@'
        if layout.count(token) != 1:
            raise ValueError(f'layout: expected one {token}')
        layout = layout.replace(token, escape(ids.get(field, ''), {'"': '&quot;'}))
    return layout
