import Mathlib

open scoped BigOperators Topology ContDiff
open MeasureTheory

namespace WM
abbrev X (n : ℕ) := Fin n → ℝ
abbrev Y (m : ℕ) := EuclideanSpace ℝ (Fin m)
def dom (n : ℕ) : Set (X n × ℝ) := {p | 0 < p.2}
noncomputable def dt {n : ℕ} {V : Type*} [NormedAddCommGroup V] [NormedSpace ℝ V] (f : X n × ℝ → V) (x : X n) (t : ℝ) : V := deriv (fun r => f (x,r)) t
noncomputable def dx {n : ℕ} {V : Type*} [NormedAddCommGroup V] [NormedSpace ℝ V] (f : X n × ℝ → V) (j : Fin n) (x : X n) (t : ℝ) : V := fderiv ℝ (fun y => f (y,t)) x (Pi.single j 1)
noncomputable def ut {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → Y m := fun p => dt u p.1 p.2
noncomputable def utt {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → Y m := fun p => dt (ut u) p.1 p.2
noncomputable def xu {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → Y m := fun p => dx u j p.1 p.2
noncomputable def lap {n m : ℕ} (u : X n × ℝ → Y m) (x : X n) (t : ℝ) : Y m := ∑ j, dx (xu u j) j x t
noncomputable def e {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → ℝ := fun p => ‖ut u p‖ ^ 2 + ∑ j, ‖xu u j p‖ ^ 2
noncomputable def et {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → ℝ := fun p => dt (e u) p.1 p.2
noncomputable def energy {n m : ℕ} (u : X n × ℝ → Y m) (t : ℝ) : ℝ := ∫ x, e u (x,t)
def box (n : ℕ) (R : ℝ) : Set (X n) := {x | ∀ j, x j ∈ Set.Icc (-R) R}
def openBox (n : ℕ) (R : ℝ) : Set (X n) := {x | ∀ j, x j ∈ Set.Ioo (-R) R}
noncomputable def aTerm {n m : ℕ} (u : X n × ℝ → Y m) : X n × ℝ → ℝ := fun p => inner ℝ (ut u p) (utt u p)
noncomputable def bTerm {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → ℝ := fun p => inner ℝ (xu u j p) (dx (ut u) j p.1 p.2)
noncomputable def cTerm {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → ℝ := fun p => inner ℝ (ut u p) (dx (xu u j) j p.1 p.2)
noncomputable def flux {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → ℝ := fun p => inner ℝ (ut u p) (xu u j p)
noncomputable def divFlux {n m : ℕ} (u : X n × ℝ → Y m) (j : Fin n) : X n × ℝ → ℝ := fun p => dx (flux u j) j p.1 p.2
def regular {n m : ℕ} (u : X n × ℝ → Y m) : Prop :=
  ContDiffOn ℝ ∞ (ut u) (dom n) ∧ ContDiffOn ℝ ∞ (utt u) (dom n) ∧ (∀ j, ContDiffOn ℝ ∞ (xu u j) (dom n)) ∧ ContDiffOn ℝ ∞ (e u) (dom n) ∧ ContDiffOn ℝ ∞ (et u) (dom n) ∧
  (∀ x t, 0 < t → et u (x,t) = 2 * aTerm u (x,t) + 2 * ∑ j, bTerm u j (x,t)) ∧
  (∀ j x t, 0 < t → dt (xu u j) x t = dx (ut u) j x t)
def good {n : ℕ} (C : Set (X n)) (R : ℝ) (f : X n → ℝ) : Prop :=
  Continuous f ∧ (∃ B : ℝ, 0 ≤ B ∧ ∀ x ∈ box n R, |f x| ≤ B) ∧ (∀ x, x ∉ C → f x = 0) ∧ Integrable f
noncomputable def quot {n m : ℕ} (u : X n × ℝ → Y m) (t h : ℝ) (x : X n) : ℝ := (e u (x,t+h) - e u (x,t)) / h
noncomputable def major {n : ℕ} (R B : ℝ) : X n → ℝ := (box n R).indicator (fun _ => B)
def geometry {n m : ℕ} (u : X n × ℝ → Y m) (q : Y m) (τ : ℝ) (C : Set (X n)) (R : ℝ) : Prop :=
  IsCompact C ∧ 0 < R ∧ C ⊆ openBox n R ∧ (∀ x, x ∉ C → ∀ r ∈ Set.Icc (τ/2) (3*τ/2), u (x,r) = q)
def localData {n m : ℕ} (u : X n × ℝ → Y m) (q : Y m) (τ : ℝ) (C : Set (X n)) (R : ℝ) : Prop :=
  geometry u q τ C R ∧ IsCompact (box n R) ∧ volume (box n R) = ENNReal.ofReal ((2*R)^n) ∧ volume (box n R) < ⊤ ∧
  (∀ x, x ∉ C → ∀ r ∈ Set.Ioo (τ/2) (3*τ/2), ∀ k : ℕ, 0 < k → iteratedFDeriv ℝ k u (x,r) = 0) ∧
  (∀ r ∈ Set.Ioo (τ/2) (3*τ/2), good C R (fun x => e u (x,r)) ∧ good C R (fun x => et u (x,r)) ∧ good C R (fun x => aTerm u (x,r)) ∧ ∀ j, good C R (fun x => bTerm u j (x,r)) ∧ good C R (fun x => cTerm u j (x,r)) ∧ good C R (fun x => divFlux u j (x,r)))
def supportAndRegularity {n m : ℕ} (u : X n × ℝ → Y m) (q : Y m) : Prop :=
  regular u ∧ (∀ t : ℝ, 0 < t → Integrable (fun x => e u (x,t))) ∧ ∀ τ : ℝ, 0 < τ → ∃ C R, localData u q τ C R
noncomputable def fluxData {n m : ℕ} (u : X n × ℝ → Y m) (q : Y m) (t : ℝ) (j : Fin n) (C : Set (X n)) (R : ℝ) : Prop :=
  localData u q t C R ∧ ContDiff ℝ ∞ (fun x => flux u j (x,t)) ∧ good C R (fun x => flux u j (x,t)) ∧
  (∀ x, divFlux u j (x,t) = bTerm u j (x,t) + cTerm u j (x,t))
end WM

namespace Translation
set_option autoImplicit false

#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H002 : ContDiffOn ℝ ∞ u (WM.dom n)) (h_H004 : ∀ (x : WM.X n) (t : ℝ), 0 < t → ‖u (x,t)‖ = 1) (h_H005 : ∀ (x : WM.X n) (t : ℝ), 0 < t → ∃ a : ℝ, WM.utt u (x,t) - WM.lap u x t = a • u (x,t)), ∀ (x : WM.X n) (t : ℝ), 0 < t → inner ℝ (u (x,t)) (WM.ut u (x,t)) = 0 ∧ inner ℝ (WM.ut u (x,t)) (WM.utt u (x,t) - WM.lap u x t) = 0)
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H002 : ContDiffOn ℝ ∞ u (WM.dom n)), WM.regular u)
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H006 : ∀ (s t : ℝ), 0 < s → s < t → ∃ C : Set (WM.X n), IsCompact C ∧ ∀ x, x ∉ C → ∀ r ∈ Set.Icc s t, u (x,r) = q), ∀ τ : ℝ, 0 < τ → ∃ (C : Set (WM.X n)) (R : ℝ), WM.geometry u q τ C R)
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H001 : 1 ≤ n ∧ 1 ≤ m) (h_H002 : ContDiffOn ℝ ∞ u (WM.dom n)) (h_T002 : WM.regular u) (h_T003 : ∀ τ : ℝ, 0 < τ → ∃ (C : Set (WM.X n)) (R : ℝ), WM.geometry u q τ C R), WM.supportAndRegularity u q)
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T004 : WM.supportAndRegularity u q), ∀ t : ℝ, 0 < t → ∃ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R ∧ 0 ≤ B ∧ ∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B)
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T004 : WM.supportAndRegularity u q), ∀ (t : ℝ), 0 < t → ∀ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R → 0 ≤ B → (∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B) → ((∀ h : ℝ, 0 < |h| → |h| < t/4 → Integrable (WM.quot u t h) ∧ AEStronglyMeasurable (WM.quot u t h) ∧ ∀ x, |WM.quot u t h x| ≤ WM.major R B x) ∧ (∀ x, Filter.Tendsto (fun h => WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (WM.et u (x,t))))))
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T004 : WM.supportAndRegularity u q) (h_T005 : ∀ t : ℝ, 0 < t → ∃ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R ∧ 0 ≤ B ∧ ∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B) (h_T006 : ∀ (t : ℝ), 0 < t → ∀ (C : Set (WM.X n)) (R B : ℝ), WM.localData u q t C R → 0 ≤ B → (∀ x ∈ WM.box n R, ∀ r ∈ Set.Icc (t-t/4) (t+t/4), |WM.et u (x,r)| ≤ B) → ((∀ h : ℝ, 0 < |h| → |h| < t/4 → Integrable (WM.quot u t h) ∧ AEStronglyMeasurable (WM.quot u t h) ∧ ∀ x, |WM.quot u t h x| ≤ WM.major R B x) ∧ (∀ x, Filter.Tendsto (fun h => WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (WM.et u (x,t)))))), ∀ t : ℝ, 0 < t → Filter.Tendsto (fun h => ∫ x, WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (∫ x, WM.et u (x,t))))
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T004 : WM.supportAndRegularity u q) (h_T007 : ∀ t : ℝ, 0 < t → Filter.Tendsto (fun h => ∫ x, WM.quot u t h x) (nhdsWithin 0 ({0}ᶜ)) (nhds (∫ x, WM.et u (x,t)))), ∀ t : ℝ, 0 < t → DifferentiableAt ℝ (WM.energy u) t ∧ deriv (WM.energy u) t = ∫ x, WM.et u (x,t))
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H001 : 1 ≤ n ∧ 1 ≤ m) (h_H002 : ContDiffOn ℝ ∞ u (WM.dom n)) (h_T004 : WM.supportAndRegularity u q), ∀ (t : ℝ), 0 < t → ∀ j : Fin n, ∃ (C : Set (WM.X n)) (R : ℝ), WM.fluxData u q t j C R)
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) , ∀ (k : ℕ) (j : Fin (k+1)) (R : ℝ), 0 < R → MeasurePreserving (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) volume volume ∧ (Set.image (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) (Set.Icc (-R) R ×ˢ WM.box k R) = WM.box (k+1) R) ∧ (∀ d : WM.X (k+1) → ℝ, Continuous d → (∫ x in WM.box (k+1) R, d x) = ∫ z in WM.box k R, ∫ y in Set.Icc (-R) R, d (Fin.insertNth j y z)))
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_H001 : 1 ≤ n ∧ 1 ≤ m) (h_T009 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, ∃ (C : Set (WM.X n)) (R : ℝ), WM.fluxData u q t j C R) (h_T010 : ∀ (k : ℕ) (j : Fin (k+1)) (R : ℝ), 0 < R → MeasurePreserving (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) volume volume ∧ (Set.image (fun p : ℝ × WM.X k => (Fin.insertNth j p.1 p.2 : WM.X (k+1))) (Set.Icc (-R) R ×ˢ WM.box k R) = WM.box (k+1) R) ∧ (∀ d : WM.X (k+1) → ℝ, Continuous d → (∫ x in WM.box (k+1) R, d x) = ∫ z in WM.box k R, ∫ y in Set.Icc (-R) R, d (Fin.insertNth j y z))), ∀ (t : ℝ), 0 < t → ∀ j : Fin n, (∫ x, WM.divFlux u j (x,t)) = 0)
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T009 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, ∃ (C : Set (WM.X n)) (R : ℝ), WM.fluxData u q t j C R) (h_T011 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, (∫ x, WM.divFlux u j (x,t)) = 0), ∀ (t : ℝ), 0 < t → ∀ j : Fin n, Integrable (fun x => WM.bTerm u j (x,t)) ∧ Integrable (fun x => WM.cTerm u j (x,t)) ∧ (∫ x, WM.bTerm u j (x,t)) = -(∫ x, WM.cTerm u j (x,t)))
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T001 : ∀ (x : WM.X n) (t : ℝ), 0 < t → inner ℝ (u (x,t)) (WM.ut u (x,t)) = 0 ∧ inner ℝ (WM.ut u (x,t)) (WM.utt u (x,t) - WM.lap u x t) = 0) (h_T004 : WM.supportAndRegularity u q) (h_T008 : ∀ t : ℝ, 0 < t → DifferentiableAt ℝ (WM.energy u) t ∧ deriv (WM.energy u) t = ∫ x, WM.et u (x,t)) (h_T012 : ∀ (t : ℝ), 0 < t → ∀ j : Fin n, Integrable (fun x => WM.bTerm u j (x,t)) ∧ Integrable (fun x => WM.cTerm u j (x,t)) ∧ (∫ x, WM.bTerm u j (x,t)) = -(∫ x, WM.cTerm u j (x,t))), ∀ t : ℝ, 0 < t → Integrable (fun x => WM.e u (x,t)) ∧ HasDerivAt (WM.energy u) 0 t ∧ deriv (WM.energy u) t = 0)
#check (∀ (n : ℕ) (m : ℕ) (u : WM.X n × ℝ → WM.Y m) (q : WM.Y m) (h_T013 : ∀ t : ℝ, 0 < t → Integrable (fun x => WM.e u (x,t)) ∧ HasDerivAt (WM.energy u) 0 t ∧ deriv (WM.energy u) t = 0), (∀ t : ℝ, 0 < t → Integrable (fun x => WM.e u (x,t))) ∧ DifferentiableOn ℝ (WM.energy u) (Set.Ioi 0) ∧ (∀ t : ℝ, 0 < t → deriv (WM.energy u) t = 0) ∧ (∀ s t : ℝ, 0 < s → 0 < t → WM.energy u s = WM.energy u t))

end Translation
