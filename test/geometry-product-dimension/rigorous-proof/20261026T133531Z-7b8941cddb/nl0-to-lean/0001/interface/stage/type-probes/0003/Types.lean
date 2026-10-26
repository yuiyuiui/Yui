import Mathlib
noncomputable def Hnative {X : Type*} [MetricSpace X] (s : ℝ) (A : Set X) : ℝ≥0∞ := letI : MeasurableSpace X := borel X; MeasureTheory.Measure.hausdorffMeasure s A

set_option autoImplicit false
#check (∀ (X : Type) [MetricSpace X] (s : ℝ) (A : Set X), Hnative s A = Hnative s A)
