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
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) : yui_aux_type% "∀ (q r ε : ℝ), 0 < q → dimH E < ENNReal.ofReal q → 0 < r → 0 < ε → ∃ U : ℕ → Set (V n), IsCover r E U ∧ coverCost q U < ENNReal.ofReal ε" := by
  intro q r ε hq hdim hr hε
  have hh := h_T002 (ULift (V n)) (ULift.up '' E) q hq
  have hi : Isometry (ULift.up : V n → ULift (V n)) := fun _ _ => rfl
  have hm : Hmeasure q (ULift.up '' E : Set (ULift (V n))) = 0 := hh.2.1 (by rw [hi.dimH_image]; exact hdim)
  have hz : Hscale q r (ULift.up '' E : Set (ULift (V n))) = 0 := by
    apply le_antisymm _ bot_le
    calc Hscale q r (ULift.up '' E : Set (ULift (V n))) ≤ Hmeasure q (ULift.up '' E : Set (ULift (V n))) := le_iSup_of_le r (le_iSup_of_le hr le_rfl)
         _ = 0 := hm
  have hsmall : Hscale q r (ULift.up '' E : Set (ULift (V n))) < ENNReal.ofReal ε := by rw [hz]; exact ENNReal.ofReal_pos.mpr hε
  obtain ⟨C, hC, hcost⟩ : ∃ C : ℕ → Set (ULift (V n)), IsCover r (ULift.up '' E) C ∧ coverCost q C < ENNReal.ofReal ε := by
    simpa only [Hscale, iInf_lt_iff, exists_prop] using hsmall
  let U : ℕ → Set (V n) := fun i => ULift.up ⁻¹' C i
  have hed (i : ℕ) : Metric.ediam (U i) ≤ Metric.ediam (C i) := by
    simpa using hi.antilipschitz.ediam_preimage_le (C i)
  refine ⟨U, ⟨?_, fun i => (hed i).trans (hC.2 i)⟩, lt_of_le_of_lt ?_ hcost⟩
  · intro x hx
    obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hC.1 (Set.mem_image_of_mem ULift.up hx))
    exact Set.mem_iUnion.mpr ⟨i, hi⟩
  · apply ENNReal.tsum_le_tsum
    intro i
    apply iSup_le
    intro hne
    have hneC : (C i).Nonempty := hne.image ULift.up |>.mono (Set.image_preimage_subset _ _)
    exact (ENNReal.rpow_le_rpow (hed i) hq.le).trans (le_iSup_of_le hneC le_rfl)
#check @checked
#print axioms checked
end YuiAuxiliary
