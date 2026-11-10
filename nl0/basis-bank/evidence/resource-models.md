# Conditions for resource arguments

These are editorial notes about using abstraction in a resource proof. They do not establish new library results or a measured improvement in proof-author performance.

- A cost bound transfers across representations with the overhead supplied by the connecting theorem. Polynomial overhead can destroy a linear bound. Arithmetic-operation counts and bit-operation counts measure different things.
- Sequential composition uses output and cost specifications for the same execution. A bookkeeping field populated independently of execution does not establish a cost bound.
- The input of the next component may have a different size. Substituting an upper size bound in a cost envelope requires the corresponding monotonicity or a uniform bound over that range. Peak live storage may include data kept by the caller.
- A recurrence or finite sum must cover the calls the algorithm actually makes, including multiplicity and local work. Its solution needs the original parameter ranges and required precision of the bound.
- Summing a per-step potential inequality retains the endpoint terms. Bounds on these terms and the treatment of shared states determine whether the argument bounds the requested total. An aggregate bound alone does not give a per-operation worst-case guarantee.
