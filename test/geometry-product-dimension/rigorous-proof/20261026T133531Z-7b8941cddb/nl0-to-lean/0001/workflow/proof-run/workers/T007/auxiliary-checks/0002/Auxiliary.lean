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
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) : yui_aux_type% "∀ (q r b : ℝ), 0 < n → 0 < q → 0 < r → 0 < b → ∀ x : V n, ∃ B : Set (V n), x ∈ B ∧ 0 < Metric.ediam B ∧ Metric.ediam B ≤ ENNReal.ofReal r ∧ (Metric.ediam B)^q < ENNReal.ofReal b" := by
  intro q r b hn hq hr hb x
  letI : Nonempty (Fin n) := ⟨⟨0, hn⟩⟩
  have hc : ContinuousAt (fun t : ℝ => t ^ q) 0 := Real.continuousAt_rpow_const 0 q (Or.inr hq.le)
  obtain ⟨d, hd, hdc⟩ := Metric.continuousAt_iff.mp hc b hb
  let a : ℝ := min r d / 4
  have ha : 0 < a := by dsimp [a]; positivity
  have har : 2 * a ≤ r := by dsimp [a]; have := min_le_left r d; linarith
  have had : 2 * a < d := by dsimp [a]; have := min_le_right r d; linarith
  have hp : (2*a)^q < b := by
    have hh := hdc (show dist (2*a) 0 < d by simpa [Real.dist_eq, abs_of_pos ha] using had)
    rw [Real.zero_rpow hq.ne'] at hh
    have hnn := Real.rpow_nonneg (by positivity : 0 ≤ 2*a) q
    simpa [Real.dist_eq, abs_of_nonneg hnn] using hh
  have he : Metric.ediam (Metric.ball x a) = ENNReal.ofReal (2*a) := by
    rw [← Metric.diam_ball_eq x ha.le, Metric.diam, ENNReal.ofReal_toReal Metric.isBounded_ball.ediam_ne_top]
  refine ⟨Metric.ball x a, Metric.mem_ball_self ha, ?_, ?_, ?_⟩
  · rw [he]; exact ENNReal.ofReal_pos.mpr (by positivity)
  · rw [he]; exact ENNReal.ofReal_le_ofReal har
  · rw [he, ENNReal.ofReal_rpow_of_nonneg (by positivity) hq.le]
    exact (ENNReal.ofReal_lt_ofReal_iff hb).mpr hp
#check @checked
#print axioms checked
end YuiAuxiliary
