"""Materialize generic fixture templates for the selected test environment only."""
from pathlib import Path
import json
import shutil


def prepare(source, destination, selected):
    source,destination=Path(source),Path(destination)
    shutil.copytree(source,destination)
    for path in (destination/'lean/examples').glob('*/contract.json'):
        value=json.loads(path.read_text())
        value['pins']={'lean_version':selected['lean']['version_number'],
                       'mathlib_commit':selected['mathlib']['rev']}
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    # Other fixture files remain byte-for-byte copies.
    return destination
