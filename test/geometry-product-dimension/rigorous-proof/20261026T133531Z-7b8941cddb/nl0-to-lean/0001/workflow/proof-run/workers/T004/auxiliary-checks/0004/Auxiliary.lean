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
theorem checked (n : ℕ) (E : Set (V n)) (h_T003 : Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤)) : yui_aux_type% "∀ (a δ d : ℝ), 0 ≤ a → d ≤ δ → ∀ {ι : Type} [Fintype ι] (U : ι → Set (V n)), E ⊆ ⋃ i, U i → (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal d) → Hscale a δ E ≤ (Fintype.card ι : ℝ≥0∞) * (ENNReal.ofReal d) ^ a" := by
  classical
  intro a δ d ha hd ι _ U hU hdiam
  let c := Fintype.card ι
  let e : Fin c ≃ ι := (Fintype.equivFin ι).symm
  let T : ℕ → Set (V n) := fun i => if hi : i < c then U (e ⟨i, hi⟩) else ∅
  have hcov : IsCover δ E T := by
    constructor
    · intro x hx
      obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hU hx)
      refine Set.mem_iUnion.mpr ⟨(e.symm i).val, ?_⟩
      simp only [T, dif_pos (e.symm i).isLt, Fin.eta, Equiv.apply_symm_apply]
      exact hi
    · intro i
      dsimp [T]
      split_ifs with hi
      · exact (hdiam _).trans (ENNReal.ofReal_le_ofReal hd)
      · simp
  have hcost : coverCost a T ≤ (c : ℝ≥0∞) * (ENNReal.ofReal d) ^ a := by
    unfold coverCost
    rw [tsum_eq_sum (s := Finset.range c) (fun i hi => ?_)]
    · calc
        _ ≤ ∑ _i ∈ Finset.range c, (ENNReal.ofReal d) ^ a := by
          apply Finset.sum_le_sum
          intro i hi
          have hi' : i < c := Finset.mem_range.mp hi
          dsimp [T]
          rw [dif_pos hi']
          apply iSup_le
          intro _
          exact ENNReal.rpow_le_rpow (hdiam (e ⟨i, hi'⟩)) ha
        _ = _ := by simp
    · have hi' : ¬ i < c := by simpa using hi
      simp [T, hi']
  unfold Hscale
  exact (iInf_le_of_le T (iInf_le_of_le hcov le_rfl)).trans hcost
#check @checked
#print axioms checked
end YuiAuxiliary
