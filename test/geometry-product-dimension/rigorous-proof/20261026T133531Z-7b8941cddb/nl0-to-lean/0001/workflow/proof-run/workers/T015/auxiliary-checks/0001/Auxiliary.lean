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
theorem checked (n : ℕ) (E : Set (V n)) (h_T002 : ∀ (X : Type*) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A ∧ (dimH A < ENNReal.ofReal s → Hmeasure s A = 0) ∧ (ENNReal.ofReal s < dimH A → Hmeasure s A = ⊤) ∧ (Hmeasure s A = 0 → dimH A ≤ ENNReal.ofReal s) ∧ (Hmeasure s A = ⊤ → ENNReal.ofReal s ≤ dimH A)) : yui_aux_type% "∀ (N : ℕ), 0 < N → unitI ⊆ ⋃ i : ℕ, if i < N then Set.Icc ((i : ℝ) / N) (((i : ℝ) + 1) / N) else ∅" := by
  intro N hN x hx
  have hNr : (0 : ℝ) < N := by exact_mod_cast hN
  rcases hx with ⟨hx0, hx1⟩
  by_cases hx : x = 1
  · refine Set.mem_iUnion.mpr ⟨N-1, ?_⟩
    rw [if_pos (by omega)]
    have hc : ((N-1 : ℕ) : ℝ) = (N : ℝ) - 1 := by rw [Nat.cast_sub (by omega)]; norm_num
    simp only [Set.mem_Icc, hc, hx]
    constructor <;> apply (div_le_iff₀ hNr).2 <;> nlinarith
  · let i := ⌊x * N⌋₊
    have hi0 : (i : ℝ) ≤ x * N := Nat.floor_le (by positivity)
    have hi1 : x * N < (i : ℝ) + 1 := Nat.lt_floor_add_one _
    have hiN : i < N := by
      have : (i : ℝ) < N := lt_of_le_of_lt hi0 (by nlinarith)
      exact_mod_cast this
    refine Set.mem_iUnion.mpr ⟨i, ?_⟩
    rw [if_pos hiN]
    exact ⟨(div_le_iff₀ hNr).2 hi0, (le_div_iff₀ hNr).2 hi1.le⟩
#check @checked
#print axioms checked
end YuiAuxiliary
