"""Load the shared proof-round policy from this Yui executable snapshot."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_path = Path(__file__).resolve().parents[2] / 'workflow/blocks/proof_rounds.py'
_spec = spec_from_file_location('yui_proof_round_policy', _path)
_rules = module_from_spec(_spec)
_spec.loader.exec_module(_rules)

locally_complete = _rules.locally_complete
compiler_accepted = _rules.compiler_accepted
retains_bodies = _rules.retains_bodies
state_for = _rules.state_for
selection = _rules.selection
read = _rules.read
