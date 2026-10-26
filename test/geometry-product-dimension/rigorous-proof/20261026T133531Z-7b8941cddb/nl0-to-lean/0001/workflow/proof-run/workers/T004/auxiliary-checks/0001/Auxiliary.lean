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
theorem checked (n : ℕ) (E : Set (V n)) (h_T003 : Bornology.IsBounded E ∧ (∃ B : ℝ, 1 ≤ B ∧ ∀ x ∈ E, ‖x‖ ≤ B) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → ∃ (k : ℕ) (U : Fin k → Set (V n)), E ⊆ ⋃ i, U i ∧ (∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ) ∧ (∑ i, (Metric.ediam (U i)) ^ s) < ⊤) ∧ (∀ (s δ : ℝ), 0 < s → 0 < δ → Hscale s δ E < ⊤)) : yui_aux_type% "∀ (B : ℝ), 1 ≤ B → (∀ x ∈ E, ‖x‖ ≤ B) → ∀ k : ℕ, 0 < k → ∃ U : (Fin n → Fin k) → Set (V n), E ⊆ ⋃ i, U i ∧ ∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal (Real.sqrt n * (2 * (B + 1) / k))" := by
  intro B hB hE k hk
  let h : ℝ := 2 * (B + 1) / k
  have hk' : (0 : ℝ) < k := by exact_mod_cast hk
  have hh : 0 < h := div_pos (by linarith) hk'
  have hhk : h * k = 2 * (B + 1) := by dsimp [h]; field_simp
  let U : (Fin n → Fin k) → Set (V n) := fun j => {x | ∀ i, -(B+1) + (j i : ℕ) * h ≤ x i ∧ x i ≤ -(B+1) + ((j i : ℕ) + 1) * h}
  refine ⟨U, ?_, ?_⟩
  · intro x hx
    have hb : ∀ i, |x i| ≤ B := fun i => (PiLp.norm_apply_le x i).trans (hE x hx)
    have hr : ∀ i, 0 ≤ (x i + (B+1)) / h ∧ (x i + (B+1)) / h < k := by
      intro i
      have hi := abs_le.mp (hb i)
      constructor
      · exact div_nonneg (by linarith) hh.le
      · apply (div_lt_iff₀ hh).2
        nlinarith [hhk]
    let j : Fin n → Fin k := fun i => ⟨⌊(x i + (B+1)) / h⌋₊, (Nat.floor_lt (hr i).1).2 (hr i).2⟩
    apply Set.mem_iUnion.mpr
    refine ⟨j, ?_⟩
    intro i
    have hlo := (le_div_iff₀ hh).mp (Nat.floor_le (hr i).1)
    have hhi := (div_lt_iff₀ hh).mp (Nat.lt_floor_add_one ((x i + (B+1)) / h))
    change -(B+1) + (⌊(x i + (B+1)) / h⌋₊ : ℝ) * h ≤ x i ∧ x i ≤ -(B+1) + ((⌊(x i + (B+1)) / h⌋₊ : ℝ) + 1) * h
    constructor <;> linarith
  · intro j
    apply Metric.ediam_le_iff.mpr
    intro x hx y hy
    have hd : ∀ i, dist (x i) (y i) ≤ h := by
      intro i
      have hxi := hx i
      have hyi := hy i
      rw [Real.dist_eq, abs_le]
      constructor <;> linarith
    have hs : ∑ i : Fin n, dist (x i) (y i) ^ 2 ≤ (n : ℝ) * h ^ 2 := by
      calc
        _ ≤ ∑ _i : Fin n, h ^ 2 := Finset.sum_le_sum fun i _ => pow_le_pow_left₀ (dist_nonneg) (hd i) 2
        _ = _ := by simp
    have hdist : dist x y ≤ Real.sqrt n * h := by
      rw [EuclideanSpace.dist_eq]
      calc
        _ ≤ Real.sqrt ((n : ℝ) * h ^ 2) := Real.sqrt_le_sqrt hs
        _ = _ := by rw [Real.sqrt_mul (Nat.cast_nonneg n), Real.sqrt_sq hh.le]
    rw [edist_dist]
    exact ENNReal.ofReal_le_ofReal hdist
#check @checked
#print axioms checked
end YuiAuxiliary
