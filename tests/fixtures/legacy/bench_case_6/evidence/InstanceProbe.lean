import Mathlib

-- Standard library applicability support only; no Koch theorem is imported.
#synth CompleteSpace ℂ
#synth CompactSpace ↥(Set.Icc (0 : ℝ) 1)
#synth CompactlyCoherentSpace ↥(Set.Icc (0 : ℝ) 1)
#synth CompleteSpace C(↥(Set.Icc (0 : ℝ) 1), ℂ)
#synth NormMulClass ℂ
#synth NormedSpace ℝ ℂ
