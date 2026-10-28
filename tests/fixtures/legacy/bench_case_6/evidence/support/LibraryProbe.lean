import Mathlib
set_option pp.universes true
set_option pp.explicit true
#eval IO.println "BEGIN_SIGNATURE:M020"
#check @Complex.instCompleteSpace
#eval IO.println "BEGIN_AXIOMS:M020"
#print axioms Complex.instCompleteSpace
#eval IO.println "END_SOURCE:M020"
#eval IO.println "BEGIN_SIGNATURE:M021"
#check @compactSpace_Icc
#eval IO.println "BEGIN_AXIOMS:M021"
#print axioms compactSpace_Icc
#eval IO.println "END_SOURCE:M021"
#eval IO.println "BEGIN_SIGNATURE:M022"
#check @to_compactlyCoherentSpace
#eval IO.println "BEGIN_AXIOMS:M022"
#print axioms to_compactlyCoherentSpace
#eval IO.println "END_SOURCE:M022"
