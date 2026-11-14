"""Read back the current native client's transmitted context."""
from pathlib import Path


def audit_stage(directory):
    import native_client
    directory=Path(directory)
    if not (directory/'native-client.json').is_file():
        raise ValueError('A current native-client record is required')
    return native_client.audit(directory)


def audit_run(directory):
    directory=Path(directory)
    return [dict(path=str(p.parent.relative_to(directory)),**audit_stage(p.parent))
            for p in sorted(directory.rglob('native-client.json'))]
