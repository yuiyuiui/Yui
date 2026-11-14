# Local setup reference

The sole public adaptation entry is [setup/README.md](../setup/README.md).
Ask Codex to execute it for first installation, repair or an environment switch.
It owns bootstrap, skill registration, carrier/authentication checks, the selected
Lean/Mathlib pair, optional external libraries and actual consumer qualification.

Machine defaults and reports live in the ignored .runtime directory. New jobs
freeze their own context; changing a default does not update existing jobs.

Current execution requires macOS isolation. See [environment semantics](../nl0/references/lean-environments.md),
[explicit external libraries](../nl0/references/lean-libraries.md), and
[software tests](../tests/README.md) for the underlying interfaces and evidence limits.
