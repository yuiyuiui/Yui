import Mathlib
open scoped ENNReal NNReal
abbrev V (n : ℕ) := EuclideanSpace ℝ (Fin n)
abbrev W (n : ℕ) := EuclideanSpace ℝ (Fin n ⊕ Unit)
noncomputable def pack (n : ℕ) (x : V n) (t : ℝ) : W n := WithLp.toLp 2 (Sum.elim (fun i => x i) (fun _ => t))
noncomputable def projX (n : ℕ) (z : W n) : V n := WithLp.toLp 2 (fun i => z (Sum.inl i))
noncomputable def projT (n : ℕ) (z : W n) : ℝ := z (Sum.inr ())
def unitI : Set ℝ := Set.Icc 0 1
def cyl (n : ℕ) (E : Set (V n)) : Set (W n) := {z | projX n z ∈ E ∧ projT n z ∈ unitI}
noncomputable def coverCost {X : Type*} [MetricSpace X] (s : ℝ) (U : ℕ → Set X) : ℝ≥0∞ := ∑' i, ⨆ (_ : (U i).Nonempty), (Metric.ediam (U i)) ^ s
def IsCover {X : Type*} [MetricSpace X] (δ : ℝ) (A : Set X) (U : ℕ → Set X) : Prop := A ⊆ ⋃ i, U i ∧ ∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ
noncomputable def Hscale {X : Type*} [MetricSpace X] (s δ : ℝ) (A : Set X) : ℝ≥0∞ := ⨅ (U : ℕ → Set X) (_ : IsCover δ A U), coverCost s U
noncomputable def Hmeasure {X : Type*} [MetricSpace X] (s : ℝ) (A : Set X) : ℝ≥0∞ := ⨆ (δ : ℝ) (_ : 0 < δ), Hscale s δ A
noncomputable def Hnative {X : Type*} [MetricSpace X] (s : ℝ) (A : Set X) : ℝ≥0∞ := letI : MeasurableSpace X := borel X; letI : BorelSpace X := ⟨rfl⟩; MeasureTheory.Measure.hausdorffMeasure s A

open Lean Elab Term
elab "yui_aux_type% " text:str : term => do
  let parsed ← ofExcept <| Parser.runParserCategory (← getEnv) `term text.getString
  Term.elabTerm parsed none

namespace YuiAuxiliary
set_option autoImplicit false
theorem checked (n : ℕ) (E : Set (V n)) (h_T007 : 0 < n → ∀ (q r ε : ℝ), dimH E < ENNReal.ofReal q → 0 < r → r ≤ 1 → 0 < ε → ∃ U : ℕ → Set (V n), IsCover r E U ∧ (∀ i, (U i).Nonempty → 0 < Metric.ediam (U i)) ∧ coverCost q U < ENNReal.ofReal ε) : yui_aux_type% "∀ (N : ℕ), 0 < N → ∀ t ∈ unitI, ∃ j : ℕ, j < N ∧ t ∈ Set.Icc ((j : ℝ) / N) (((j : ℝ) + 1) / N)" := by
  intro N hN t ht
  have hNr : (0 : ℝ) < N := by exact_mod_cast hN
  change 0 ≤ t ∧ t ≤ 1 at ht
  by_cases ht1 : t = 1
  · refine ⟨N - 1, by omega, ?_⟩
    have hcast : ((N - 1 : ℕ) : ℝ) + 1 = N := by
      exact_mod_cast Nat.sub_add_cancel hN
    rw [ht1]
    constructor
    · apply (div_le_iff₀ hNr).2
      linarith
    · rw [hcast, div_self (ne_of_gt hNr)]
  · have htlt : t < 1 := lt_of_le_of_ne ht.2 ht1
    refine ⟨⌊t * N⌋₊, ?_, ?_, ?_⟩
    · apply Nat.floor_lt (by positivity) |>.2
      nlinarith
    · exact (div_le_iff₀ hNr).2 (Nat.floor_le (mul_nonneg ht.1 hNr.le))
    · exact (le_div_iff₀ hNr).2 (Nat.lt_floor_add_one (t * N)).le
#check @checked
#print axioms checked
end YuiAuxiliary
