import numpy as np
import sympy as sp
import os
from params_zeeman import params

from hfsbe.dipole import SymbolicDipole, SymbolicZeemanDipole
from hfsbe.example import BiTe


from SBE_zeeman import sbe_zeeman_solver


def run():

    # C2                  = 5.39018     # k^2 coefficient
    # A                   = 0.19732     # Fermi velocity
    A = 0.1974
    # R                   = 5.52658     # k^3 coefficient
    # mb                  = 0.000373195 # Splitting of cones.(10 meV)
    # k_cut               = 0.05        # Model hamiltonian cutoff

    # Sweep electric field
    for E in np.arange(5.00, 5.10, 0.50):

        params.E0 = E
        print("Current E-field: ", params.E0)
        dirname = 'E_{:1.2f}'.format(params.E0)
        if (not os.path.exists(dirname)):
            os.mkdir(dirname)
        os.chdir(dirname)

        system = BiTe(C0=0, C2=0, A=A, R=0, zeeman=True)
        h_sym, ef_sym, wf_sym, ediff_sym = system.eigensystem(gidx=1)
        dipole = SymbolicDipole(h_sym, ef_sym, wf_sym)

        dipole_mb = SymbolicZeemanDipole(h_sym, wf_sym)
        sbe_zeeman_solver(system, dipole, dipole_mb, params)
        os.chdir('..')


if __name__ == "__main__":
    run()
