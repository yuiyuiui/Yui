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
theorem checked (n : ℕ) (E : Set (V n)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) (h_T010 : ∀ (s δ ε : ℝ), 0 < s → 0 < δ → 0 < ε → ∀ Vc : ℕ → Set (W n), IsCover δ (cyl n E) Vc → ∃ J : ℕ → Set ℝ, (∀ i, IsOpen (J i) ∧ projT n '' Vc i ⊆ J i ∧ MeasureTheory.volume (J i) ≤ Metric.ediam (Vc i) + ENNReal.ofReal ε * (1 / 2 : ℝ≥0∞) ^ (i + 1) / (1 + (Metric.ediam (Vc i)) ^ s)) ∧ (∀ t ∈ unitI, Hscale s δ E ≤ ∑' i, (J i).indicator (fun _ : ℝ => (Metric.ediam (Vc i)) ^ s) t) ∧ (∀ i, Measurable ((J i).indicator (fun _ : ℝ => (Metric.ediam (Vc i)) ^ s)))) : yui_aux_type% "∀ a b : ℝ≥0∞, a * (b / (1 + a)) ≤ b" := by
  intro a b
  exact (mul_le_mul_right' (le_add_left le_rfl : a ≤ 1 + a) _).trans ENNReal.mul_div_le
#check @checked
#print axioms checked
end YuiAuxiliary
