import Mathlib
set_option pp.universes true
set_option pp.explicit true
#eval IO.println "BEGIN_SIGNATURE:M001"
#check @Real.sq_sqrt
#eval IO.println "BEGIN_AXIOMS:M001"
#print axioms Real.sq_sqrt
#eval IO.println "END_SOURCE:M001"
#eval IO.println "BEGIN_SIGNATURE:M002"
#check @Complex.normSq_apply
#eval IO.println "BEGIN_AXIOMS:M002"
#print axioms Complex.normSq_apply
#eval IO.println "END_SOURCE:M002"
#eval IO.println "BEGIN_SIGNATURE:M003"
#check @Complex.sq_norm
#eval IO.println "BEGIN_AXIOMS:M003"
#print axioms Complex.sq_norm
#eval IO.println "END_SOURCE:M003"
#eval IO.println "BEGIN_SIGNATURE:M004"
#check @norm_mul
#eval IO.println "BEGIN_AXIOMS:M004"
#print axioms norm_mul
#eval IO.println "END_SOURCE:M004"
#eval IO.println "BEGIN_SIGNATURE:M005"
#check @isClosed_eq
#eval IO.println "BEGIN_AXIOMS:M005"
#print axioms isClosed_eq
#eval IO.println "END_SOURCE:M005"
#eval IO.println "BEGIN_SIGNATURE:M006"
#check @ContinuousMap.dist_apply_le_dist
#eval IO.println "BEGIN_AXIOMS:M006"
#print axioms ContinuousMap.dist_apply_le_dist
#eval IO.println "END_SOURCE:M006"
#eval IO.println "BEGIN_SIGNATURE:M007"
#check @ContinuousMap.dist_le
#eval IO.println "BEGIN_AXIOMS:M007"
#print axioms ContinuousMap.dist_le
#eval IO.println "END_SOURCE:M007"
#eval IO.println "BEGIN_SIGNATURE:M008"
#check @ContinuousMap.instCompleteSpaceOfCompactlyCoherentSpace
#eval IO.println "BEGIN_AXIOMS:M008"
#print axioms ContinuousMap.instCompleteSpaceOfCompactlyCoherentSpace
#eval IO.println "END_SOURCE:M008"
#eval IO.println "BEGIN_SIGNATURE:M009"
#check @IsClosed.completeSpace_coe
#eval IO.println "BEGIN_AXIOMS:M009"
#print axioms IsClosed.completeSpace_coe
#eval IO.println "END_SOURCE:M009"
#eval IO.println "BEGIN_SIGNATURE:M010"
#check @ContinuousOn.piecewise
#eval IO.println "BEGIN_AXIOMS:M010"
#print axioms ContinuousOn.piecewise
#eval IO.println "END_SOURCE:M010"
#eval IO.println "BEGIN_SIGNATURE:M011"
#check @ContractingWith.fixedPoint_isFixedPt
#eval IO.println "BEGIN_AXIOMS:M011"
#print axioms ContractingWith.fixedPoint_isFixedPt
#eval IO.println "END_SOURCE:M011"
#eval IO.println "BEGIN_SIGNATURE:M012"
#check @ContractingWith.fixedPoint_unique
#eval IO.println "BEGIN_AXIOMS:M012"
#print axioms ContractingWith.fixedPoint_unique
#eval IO.println "END_SOURCE:M012"
#eval IO.println "BEGIN_SIGNATURE:M013"
#check @ContractingWith.tendsto_iterate_fixedPoint
#eval IO.println "BEGIN_AXIOMS:M013"
#print axioms ContractingWith.tendsto_iterate_fixedPoint
#eval IO.println "END_SOURCE:M013"
#eval IO.println "BEGIN_SIGNATURE:M014"
#check @DifferentiableWithinAt.isBigO_sub
#eval IO.println "BEGIN_AXIOMS:M014"
#print axioms DifferentiableWithinAt.isBigO_sub
#eval IO.println "END_SOURCE:M014"
#eval IO.println "BEGIN_SIGNATURE:M015"
#check @Asymptotics.isBigO_iff'
#eval IO.println "BEGIN_AXIOMS:M015"
#print axioms Asymptotics.isBigO_iff'
#eval IO.println "END_SOURCE:M015"
#eval IO.println "BEGIN_SIGNATURE:M016"
#check @Metric.mem_nhdsWithin_iff
#eval IO.println "BEGIN_AXIOMS:M016"
#print axioms Metric.mem_nhdsWithin_iff
#eval IO.println "END_SOURCE:M016"
#eval IO.println "BEGIN_SIGNATURE:M017"
#check @tendsto_pow_atTop_nhds_zero_of_lt_one
#eval IO.println "BEGIN_AXIOMS:M017"
#print axioms tendsto_pow_atTop_nhds_zero_of_lt_one
#eval IO.println "END_SOURCE:M017"
#eval IO.println "BEGIN_SIGNATURE:M018"
#check @tendsto_pow_atTop_atTop_of_one_lt
#eval IO.println "BEGIN_AXIOMS:M018"
#print axioms tendsto_pow_atTop_atTop_of_one_lt
#eval IO.println "END_SOURCE:M018"
#eval IO.println "BEGIN_SIGNATURE:M019"
#check @norm_add_le
#eval IO.println "BEGIN_AXIOMS:M019"
#print axioms norm_add_le
#eval IO.println "END_SOURCE:M019"
