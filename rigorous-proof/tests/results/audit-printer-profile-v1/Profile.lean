import Mathlib
set_option pp.all true
#eval IO.println "BEGIN_ALL"
#check @integral_bilinear_hasFDerivAt_right_eq_neg_left_of_integrable
#eval IO.println "BEGIN_NO_PROOF_TERMS"
set_option pp.proofs false
#check @integral_bilinear_hasFDerivAt_right_eq_neg_left_of_integrable
#eval IO.println "BEGIN_NO_STRUCT_LITERALS"
set_option pp.structureInstances false
#check @integral_bilinear_hasFDerivAt_right_eq_neg_left_of_integrable
#eval IO.println "END_PROFILE"
