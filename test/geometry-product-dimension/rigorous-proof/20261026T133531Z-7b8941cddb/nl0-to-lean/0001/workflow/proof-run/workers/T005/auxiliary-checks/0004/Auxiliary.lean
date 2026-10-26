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
theorem checked (n : ℕ) (E : Set (V n)) (h_H001 : E.Nonempty) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T003 : Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤)) (h_T004 : 0 < n → ∀ a : ℝ, (n : ℝ) < a → (∀ δ : ℝ, 0 < δ → Hscale a δ E = 0) ∧ Hmeasure a E = 0) : yui_aux_type% "n = 0 → E = Set.univ ∧ ∀ s : ℝ, 0 < s → Hmeasure s E = 0" := by
  intro hn
  subst n
  have hE : E = Set.univ := by
    apply Set.eq_univ_of_forall
    intro x
    obtain ⟨y, hy⟩ := h_H001
    simpa only [Subsingleton.elim x y] using hy
  refine ⟨hE, ?_⟩
  intro s hs
  have hd : Metric.ediam E = 0 := Metric.ediam_subsingleton (fun _ _ _ _ => Subsingleton.elim _ _)
  have hc : coverCost s (fun _ : ℕ => E) = 0 := by
    simp [coverCost, hd, ENNReal.zero_rpow_of_pos hs]
  apply le_antisymm _ bot_le
  change (⨆ δ : ℝ, ⨆ (_ : 0 < δ), Hscale s δ E) ≤ 0
  apply iSup_le
  intro δ
  apply iSup_le
  intro hδ
  have hcov : IsCover δ E (fun _ : ℕ => E) := by
    constructor
    · intro x hx
      exact Set.mem_iUnion.mpr ⟨0, hx⟩
    · intro i
      rw [hd]
      exact bot_le
  calc
    Hscale s δ E ≤ coverCost s (fun _ : ℕ => E) := iInf_le_of_le (fun _ : ℕ => E) (iInf_le_of_le hcov le_rfl)
    _ = 0 := hc
#check @checked
#print axioms checked
end YuiAuxiliary
