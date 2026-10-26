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
theorem checked (n : ℕ) (E : Set (V n)) (h_T005 : Bornology.IsBounded E ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤) ∧ 0 ≤ dimH E ∧ dimH E ≤ (n : ℝ≥0∞) ∧ dimH E < ⊤ ∧ (n = 0 → E = Set.univ ∧ dimH E = 0)) : yui_aux_type% "LipschitzWith 1 (projX n) → ∀ (s δ : ℝ), 0 < s → ∀ (Vc : ℕ → Set (W n)), IsCover δ (cyl n E) Vc → ∀ (J : ℕ → Set ℝ), (∀ i, projT n '' Vc i ⊆ J i) → ∀ t ∈ unitI, Hscale s δ E ≤ ∑' i, (J i).indicator (fun _ : ℝ => (Metric.ediam (Vc i)) ^ s) t" := by
  intro hx s δ hs Vc hVc J hJ t ht
  classical
  let U : ℕ → Set (V n) := fun i => if t ∈ J i then projX n '' Vc i else ∅
  have hd (i : ℕ) : Metric.ediam (projX n '' Vc i) ≤ Metric.ediam (Vc i) := by simpa using hx.ediam_image_le (Vc i)
  have hU : IsCover δ E U := by
    constructor
    · intro x hxE
      have hp : pack n x t ∈ cyl n E := by simpa [cyl, projX, projT, pack] using And.intro hxE ht
      obtain ⟨i, hi⟩ := Set.mem_iUnion.mp (hVc.1 hp)
      have hti : t ∈ J i := hJ i ⟨pack n x t, hi, by simp [projT, pack]⟩
      apply Set.mem_iUnion.mpr
      refine ⟨i, ?_⟩
      simp only [U, if_pos hti]
      exact ⟨pack n x t, hi, by ext j; simp [projX, pack]⟩
    · intro i
      dsimp [U]
      split_ifs
      · exact (hd i).trans (hVc.2 i)
      · simp
  have hc : Hscale s δ E ≤ coverCost s U := iInf_le_of_le U (iInf_le_of_le hU le_rfl)
  refine hc.trans (ENNReal.tsum_le_tsum fun i => ?_)
  change (⨆ (_ : (U i).Nonempty), Metric.ediam (U i) ^ s) ≤ _
  apply iSup_le
  intro hne
  by_cases hi : t ∈ J i
  · simp only [Set.indicator_of_mem hi, U, if_pos hi]
    exact ENNReal.rpow_le_rpow (hd i) hs.le
  · have : U i = ∅ := by simp [U, hi]
    simp [this] at hne
#check @checked
#print axioms checked
end YuiAuxiliary
