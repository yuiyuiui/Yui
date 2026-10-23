import Mathlib

open MeasureTheory Filter
open scoped ENNReal

noncomputable section

namespace Translation
set_option autoImplicit false

theorem T001 (iota : Type) (F : iota → ℂ) (G : iota → ℂ) (h_H001 : ∀ r, ‖F r‖ = ‖G r‖) :
    ∀ r : iota, ‖F r‖ₑ = ‖G r‖ₑ := by
  intro r
  exact (enorm_eq_iff_norm_eq).2 (h_H001 r)

theorem T002 (iota : Type) (F : iota → ℂ) (G : iota → ℂ) (h_T001 : ∀ r : iota, ‖F r‖ₑ = ‖G r‖ₑ) :
    (⨆ r, ‖F r‖ₑ) = ⨆ r, ‖G r‖ₑ := by
  apply iSup_congr
  intro r
  exact h_T001 r

theorem P (iota : Type) (F : iota → ℂ) (G : iota → ℂ) (h_H001 : ∀ r, ‖F r‖ = ‖G r‖) :
    (⨆ r, ‖F r‖ₑ) = ⨆ r, ‖G r‖ₑ := by
  have h_T001 : ∀ r : iota, ‖F r‖ₑ = ‖G r‖ₑ := T001 iota F G h_H001
  have h_T002 : (⨆ r, ‖F r‖ₑ) = ⨆ r, ‖G r‖ₑ := T002 iota F G h_T001
  exact h_T002

#check @P
#print axioms P

end Translation
