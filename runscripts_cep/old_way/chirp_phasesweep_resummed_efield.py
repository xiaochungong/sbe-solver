import numpy as np
import os
from params import params

import hfsbe.dipole
import hfsbe.example
import hfsbe.utility
from hfsbe.utility import conversion_factors as co
# Set BZ type independent parameters
# Hamiltonian parameters
from SBE import main as solver


def run():

    C0 = -0.00647156                  # C0
    c2 = 0.0117598                    # k^2 coefficient
    A = 0.0422927                     # Fermi velocity
    r = 0.109031                      # k^3 coefficient
    ksym = 0.0635012                  # k^2 coefficent dampening
    kasym = 0.113773                  # k^3 coeffcient dampening

    params.w = 25
    if (params.w == 30):
        params.t0 = -250
        params.alpha = 45

    params.e_fermi = 0
    twoelectron = False
    if (twoelectron == True):
        # Semiclassical calculation with two electrons at the 0.03 path
        # Fermi energy to only occupy middle point of path
        params.e_fermi = -0.004171*co.au_to_eV
        params.temperature = 0
        params.dipole_off = True
        params.Nk_in_path = 1401


    E_max = 10
    Elist = np.linspace(2.5, E_max, 4)
    E = Elist[1]
    params.E0 = E

    params.rel_dist_to_gamma = 0.03

    # dirname_E = 'E_{:.1f}'.format(params.E0)
    # if (not os.path.exists(dirname_E)):
    #     os.mkdir(dirname_E)
    # os.chdir(dirname_E)

    # chirplist = np.linspace(-0.920, 0.920, 11)
    chirplist = [-0.920, 0.00]
    # chirplist = [-2.000, -1.400]
    for chirp in chirplist[0:1]:
        params.chirp = chirp
        print("Current chirp: ", params.chirp)
        dirname_chirp = 'chirp_{:1.3f}'.format(params.chirp)
        if (not os.path.exists(dirname_chirp)):
            os.mkdir(dirname_chirp)
        os.chdir(dirname_chirp)

        phaselist = np.linspace(0, np.pi, 20)
        # phaselist = [phaselist[0]]
        for phase in phaselist:
            params.phase = phase
            print("Current phase: ", params.phase)
            dirname_phase = 'phase_{:1.2f}'.format(params.phase)
            if (not os.path.exists(dirname_phase)):
                os.mkdir(dirname_phase)
            os.chdir(dirname_phase)

            system = hfsbe.example.BiTeResummed(C0=C0, c2=c2, A=A, r=r, ksym=ksym, kasym=kasym)
            h_sym, ef_sym, wf_sym, ediff_sym = system.eigensystem(gidx=1)
            dipole = hfsbe.dipole.SymbolicDipole(h_sym, ef_sym, wf_sym)
            solver(system, dipole, params)
            os.chdir('..')

        os.chdir('..')


if __name__ == "__main__":
    run()