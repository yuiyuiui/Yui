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
theorem checked (n : ℕ) (E : Set (V n)) (h_T007 : 0 < n → ∀ (q r ε : ℝ), dimH E < ENNReal.ofReal q → 0 < r → r ≤ 1 → 0 < ε → ∃ U : ℕ → Set (V n), IsCover r E U ∧ (∀ i, (U i).Nonempty → 0 < Metric.ediam (U i)) ∧ coverCost q U < ENNReal.ofReal ε) : yui_aux_type% "∀ (d : ℝ), 0 < d → d ≤ 1 → let N := ⌈1 / d⌉₊; 0 < N ∧ 1 / (N : ℝ) ≤ d ∧ (N : ℝ) ≤ 2 / d" := by
  intro d hd hd1 N
  have hN : (0 : ℝ) < N := lt_of_lt_of_le (one_div_pos.mpr hd) (Nat.le_ceil (1 / d))
  refine ⟨by exact_mod_cast hN, ?_, ?_⟩
  · apply (div_le_iff₀ hN).2
    have h := (div_le_iff₀ hd).1 (Nat.le_ceil (1 / d))
    nlinarith
  · have h := (Nat.ceil_lt_add_one (le_of_lt (one_div_pos.mpr hd))).le
    dsimp [N]
    calc
      (⌈1 / d⌉₊ : ℝ) ≤ 1 / d + 1 := h
      _ ≤ 2 / d := by apply (le_div_iff₀ hd).2; field_simp; nlinarith
#check @checked
#print axioms checked
end YuiAuxiliary
