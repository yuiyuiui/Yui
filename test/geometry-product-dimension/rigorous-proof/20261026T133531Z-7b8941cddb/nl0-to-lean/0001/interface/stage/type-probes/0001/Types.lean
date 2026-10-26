import Mathlib
open scoped ENNReal NNReal
noncomputable def V (n : ℕ) := EuclideanSpace ℝ (Fin n)
noncomputable def W (n : ℕ) := EuclideanSpace ℝ (Fin n ⊕ Unit)
noncomputable def pack (n : ℕ) (x : V n) (t : ℝ) : W n := WithLp.toLp 2 (Sum.elim (fun i => x i) (fun _ => t))
noncomputable def projX (n : ℕ) (z : W n) : V n := WithLp.toLp 2 (fun i => z (Sum.inl i))
noncomputable def projT (n : ℕ) (z : W n) : ℝ := z (Sum.inr ())
noncomputable def unitI : Set ℝ := Set.Icc 0 1
noncomputable def cyl (n : ℕ) (E : Set (V n)) : Set (W n) := {z | projX n z ∈ E ∧ projT n z ∈ unitI}
noncomputable def coverCost {X : Type*} [MetricSpace X] (s : ℝ) (U : ℕ → Set X) : ℝ≥0∞ := ∑' i, ⨆ (_ : (U i).Nonempty), (Metric.ediam (U i)) ^ s
 def IsCover {X : Type*} [MetricSpace X] (δ : ℝ) (A : Set X) (U : ℕ → Set X) : Prop := A ⊆ ⋃ i, U i ∧ ∀ i, Metric.ediam (U i) ≤ ENNReal.ofReal δ
noncomputable def Hscale {X : Type*} [MetricSpace X] (s δ : ℝ) (A : Set X) : ℝ≥0∞ := ⨅ (U : ℕ → Set X) (_ : IsCover δ A U), coverCost s U
noncomputable def Hmeasure {X : Type*} [MetricSpace X] (s : ℝ) (A : Set X) : ℝ≥0∞ := ⨆ (δ : ℝ) (_ : 0 < δ), Hscale s δ A
noncomputable def Hnative {X : Type*} [MetricSpace X] (s : ℝ) (A : Set X) : ℝ≥0∞ := @MeasureTheory.Measure.hausdorffMeasure X _ (borel X) ⟨rfl⟩ s A

set_option autoImplicit false
#check (fun (n : ℕ) (E : Set (V n)) => ∀ (X : Type) [MetricSpace X] (A : Set X) (s : ℝ), 0 < s → Hmeasure s A = Hnative s A)
#check (fun (n : ℕ) (E : Set (V n)) => dimH (cyl n E) = dimH E + 1)
#check (fun (n : ℕ) (E : Set (V n)) => ∀ (δ s : ℝ), 0 < δ → 0 < s → Hscale s δ E < ⊤)
#check (fun (n : ℕ) (E : Set (V n)) => ∀ (x : V n) (t : ℝ), projX n (pack n x t) = x ∧ projT n (pack n x t) = t)
