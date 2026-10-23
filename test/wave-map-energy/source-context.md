# Source context and pending support decision

Source: Lawrence C. Evans, Partial Differential Equations, second edition,
Graduate Studies in Mathematics 19, AMS, 2010, ISBN 978-0-8218-4974-3.
Chapter 12, section 12.6, exercise 14, printed page 694 matches source.png.
Primary textbook scan: https://wms.mat.agh.edu.pl/~lusapa/pl/Evans.pdf
Downloaded complete PDF: 29,369,281 bytes; SHA256
 a515efdc1c5f0cda49729b9c47ce479e8660864e1158b92554cebb7e2dd6ce47.
Printed page 694 is PDF page 703, counting the first PDF page as 1.

The immediately preceding exercise 13 defines a smooth sphere-valued wave
map u: R^n times [0,infinity) to R^m by |u|=1 and acceleration u_tt-Delta u
normal to the sphere at u. Its equation is
u_tt-Delta u=(|D u|^2-|u_t|^2)u.
Exercise 14 literally calls u compactly supported in space. A sphere-valued
function cannot equal zero outside a compact set. Under the literal zero-support
reading, there are no such maps and the implication is vacuous; that is not an
accepted nontrivial energy-conservation test.

Proposed interpretation, awaiting user confirmation: fix a unit vector q,
require u-q to have compact spatial support locally uniformly in time, and
prove the displayed energy derivative is zero for interior times. More precisely,
for every compact time interval J in the open time domain there is a compact
spatial set C_J such that u(x,t)=q outside C_J for every t in J.
This gives a consistent nontrivial class and supports the needed differentiation
and integration-by-parts justification. It is a disclosed interpretation of the
exercise, not a claimed author-issued correction. No proof has been run under
this proposed modification.
