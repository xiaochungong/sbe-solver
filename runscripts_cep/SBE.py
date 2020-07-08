#!/bin/python
import numpy as np
from numpy.fft import fft, fftfreq, fftshift
from numba import njit
from math import ceil
import matplotlib.pyplot as pl
from matplotlib.patches import RegularPolygon
from scipy.integrate import ode

from hfsbe.utility import evaluate_njit_matrix as ev_mat


def main(sys, dipole, params):
    # RETRIEVE PARAMETERS
    ###########################################################################
    # Flag evaluation
    user_out = params.user_out
    save_file = params.save_file
    save_full = params.save_full
    test = params.test

    # Unit converstion factors
    fs_conv = params.fs_conv
    E_conv = params.E_conv
    THz_conv = params.THz_conv
    # amp_conv = params.amp_conv
    eV_conv = params.eV_conv

    # System parameters
    a = params.a                                # Lattice spacing
    e_fermi = params.e_fermi*eV_conv            # Fermi energy
    temperature = params.temperature*eV_conv    # Temperature

    # Driving field parameters
    E0 = params.E0*E_conv                       # Driving pulse field amplitude
    w = params.w*THz_conv                       # Driving pulse frequency
    chirp = params.chirp*THz_conv               # Pulse chirp frequency
    alpha = params.alpha*fs_conv                # Gaussian pulse width
    phase = params.phase                        # Carrier-envelope phase

    # Time scales
    T1 = params.T1*fs_conv                      # Occupation damping time
    T2 = params.T2*fs_conv                      # Polarization damping time
    gamma1 = 1/T1                               # Occupation damping parameter
    gamma2 = 1/T2                               # Polarization damping param

    Nf = int((abs(2*params.t0))/params.dt)
    # Find out integer times Nt fits into total time steps
    dt_out = int(ceil(Nf/params.Nt))

    # Expand time window to fit Nf output steps
    Nt = dt_out*params.Nt
    total_fs = Nt*params.dt
    t0 = (-total_fs/2)*fs_conv
    tf = (total_fs/2)*fs_conv
    dt = params.dt*fs_conv

    # t0 = int(params.t0*fs_conv)                 # Initial time condition
    # tf = int(params.tf*fs_conv)                 # Final time
    # dt = params.dt*fs_conv                      # Integration time step
    # dt_out = 1/(2*params.dt)                    # Solution output time step

    # Brillouin zone type
    BZ_type = params.BZ_type                    # Type of Brillouin zone

    # Brillouin zone type
    if BZ_type == 'full':
        Nk1 = params.Nk1                        # kpoints in b1 direction
        Nk2 = params.Nk2                        # kpoints in b2 direction
        Nk = Nk1*Nk2                            # Total number of kpoints
        align = params.align                    # E-field alignment
    elif BZ_type == '2line':
        Nk_in_path = params.Nk_in_path
        Nk = 2*Nk_in_path
        # rel_dist_to_Gamma = params.rel_dist_to_Gamma
        # length_path_in_BZ = params.length_path_in_BZ
        angle_inc_E_field = params.angle_inc_E_field

    b1 = params.b1                              # Reciprocal lattice vectors
    b2 = params.b2

    # USER OUTPUT
    ###########################################################################
    if user_out:
        print("Solving for...")
        print("Brillouin zone: " + BZ_type)
        print("Number of k-points              = " + str(Nk))
        if BZ_type == 'full':
            print("Driving field alignment         = " + align)
        elif BZ_type == '2line':
            print("Driving field direction         = " + str(angle_inc_E_field))
        print("Driving amplitude (MV/cm)[a.u.] = " + "(" + '%.6f'%(E0/E_conv) + ")" + "[" + '%.6f'%(E0) + "]")
        print("Pulse Frequency (THz)[a.u.]     = " + "(" + '%.6f'%(w/THz_conv) + ")" + "[" + '%.6f'%(w) + "]")
        print("Pulse Width (fs)[a.u.]          = " + "(" + '%.6f'%(alpha/fs_conv) + ")" + "[" + '%.6f'%(alpha) + "]")
        print("Chirp rate (THz)[a.u.]          = " + "(" + '%.6f'%(chirp/THz_conv) + ")" + "[" + '%.6f'%(chirp) + "]")
        print("Damping time (fs)[a.u.]         = " + "(" + '%.6f'%(T2/fs_conv) + ")" + "[" + '%.6f'%(T2) + "]")
        print("Total time (fs)[a.u.]           = " + "(" + '%.6f'%((tf-t0)/fs_conv) + ")" + "[" + '%.5i'%(tf-t0) + "]")
        print("Time step (fs)[a.u.]            = " + "(" + '%.6f'%(dt/fs_conv) + ")" + "[" + '%.6f'%(dt) + "]")

    # INITIALIZATIONS
    ###########################################################################
    # Form the E-field direction

    # Form the Brillouin zone in consideration
    if BZ_type == 'full':
        kpnts, paths = hex_mesh(Nk1, Nk2, a, b1, b2, align)
        dk = 1/Nk1
        if align == 'K':
            E_dir = np.array([1, 0])
        elif align == 'M':
            E_dir = np.array([np.cos(np.radians(-30)),
                             np.sin(np.radians(-30))])
        # BZ_plot(kpnts, a, b1, b2, paths)
    elif BZ_type == '2line':
        E_dir = np.array([np.cos(np.radians(angle_inc_E_field)),
                         np.sin(np.radians(angle_inc_E_field))])
        dk, kpnts, paths = mesh(params, E_dir)
        # BZ_plot(kpnts, a, b1, b2, paths)

    t_constructed = False

    # Solution containers
    t = []
    solution = []

    # Initalise electric_field, create fnumba and initalise ode solver
    electric_field = make_electric_field(E0, w, alpha, chirp, phase)
    fnumba = make_fnumba(sys, dipole, E_dir, gamma1, gamma2, electric_field)
    solver = ode(fnumba, jac=None)\
        .set_integrator('zvode', method='bdf', max_step=dt)

    # Vector field
    A_field = []
    # SOLVING
    ###########################################################################
    # Iterate through each path in the Brillouin zone

    path_num = 1
    for path in paths:
        if user_out:
            print('path: ' + str(path_num))

        # Solution container for the current path
        path_solution = []

        # Retrieve the set of k-points for the current path
        kx_in_path = path[:, 0]
        ky_in_path = path[:, 1]

        # Calculate the dipole components along the path
        di_00x = dipole.Axfjit[0][0](kx=kx_in_path, ky=ky_in_path)
        di_01x = dipole.Axfjit[0][1](kx=kx_in_path, ky=ky_in_path)
        di_11x = dipole.Axfjit[1][1](kx=kx_in_path, ky=ky_in_path)
        di_00y = dipole.Ayfjit[0][0](kx=kx_in_path, ky=ky_in_path)
        di_01y = dipole.Ayfjit[0][1](kx=kx_in_path, ky=ky_in_path)
        di_11y = dipole.Ayfjit[1][1](kx=kx_in_path, ky=ky_in_path)

        # Calculate the dot products E_dir.d_nm(k).
        # To be multiplied by E-field magnitude later.
        # A[0,1,:] means 0-1 offdiagonal element
        dipole_in_path = E_dir[0]*di_01x + E_dir[1]*di_01y
        A_in_path = E_dir[0]*di_00x + E_dir[1]*di_00y \
            - (E_dir[0]*di_11x + E_dir[1]*di_11y)

        # in bite.evaluate, there is also an interpolation done if b1, b2 are
        # provided and a cutoff radius
        ec = sys.efjit[1](kx=kx_in_path, ky=ky_in_path)
        ev = sys.efjit[0](kx=kx_in_path, ky=ky_in_path)
        ecv_in_path = ec - ev

        # Initialize the values of of each k point vector
        # (rho_nn(k), rho_nm(k), rho_mn(k), rho_mm(k))
        y0 = initial_condition(e_fermi, temperature, ec)
        y0 = np.append(y0, [0.0])

        # Set the initual values and function parameters for the current kpath
        solver.set_initial_value(y0, t0)\
            .set_f_params(path, dk, ecv_in_path, dipole_in_path, A_in_path, y0)

        # Propagate through time
        ti = 0
        while solver.successful() and ti < Nt:
            # User output of integration progress
            # print(ti)
            if (ti % 1000 == 0 and user_out):
                print('{:5.2f}%'.format(ti/Nt*100))

            # Integrate one integration time step
            solver.integrate(solver.t + dt)

            # Save solution each output step
            if (ti % dt_out == 0):
                # Do not append the last element (A_field)
                path_solution.append(solver.y[:-1])
                # Construct time array only once
                if not t_constructed:
                    # Construct time and A_field only in first round
                    t.append(solver.t)
                    A_field.append(solver.y[-1])

            # Increment time counter
            ti += 1

        # Flag that time array has been built up
        t_constructed = True
        path_num += 1

        # Append path solutions to the total solution arrays
        solution.append(path_solution)

    # Convert solution and time array to numpy arrays
    t = np.array(t)
    solution = np.array(solution)
    A_field = np.array(A_field)

    # Slice solution along each path for easier observable calculation
    # Split the last index into 100 subarrays, corresponding to kx
    # Consquently the new last axis becomes 4.
    if BZ_type == 'full':
        solution = np.array_split(solution, Nk1, axis=2)
    elif BZ_type == '2line':
        solution = np.array_split(solution, Nk_in_path, axis=2)

    # Convert lists into numpy arrays
    solution = np.array(solution)

    # The solution array is structred as: first index is Nk1-index,
    # second is Nk2-index, third is timestep, fourth is f_h, p_he, p_eh, f_e

    # COMPUTE OBSERVABLES
    ###########################################################################
    # Calculate parallel and orthogonal components of observables
    # Polarization (interband)
    # P_E_dir, P_ortho = polarization(dipole, paths, solution[:, :, :, 1], E_dir)
    # Current (intraband)
    # J_E_dir, J_ortho = current(sys, paths, solution[:, :, :, 0],
    #                            solution[:, :, :, 3], t, alpha, E_dir)
    # Emission in time
    # I_E_dir = diff(t, P_E_dir)*gaussian_envelope(t, alpha) \
    #     + J_E_dir*gaussian_envelope(t, alpha)
    # I_ortho = diff(t, P_ortho)*gaussian_envelope(t, alpha) \
    #     + J_ortho*gaussian_envelope(t, alpha)

    # Fourier transforms
    dt_out = t[1] - t[0]
    freq = fftshift(fftfreq(np.size(t), d=dt_out))
    # Iw_E_dir = fftshift(fft(I_E_dir, norm='ortho'))
    # Iw_ortho = fftshift(fft(I_ortho, norm='ortho'))
    # # Iw_r = fftshift(fft(Ir, norm='ortho'))
    # Pw_E_dir = fftshift(fft(diff(t, P_E_dir), norm='ortho'))
    # Pw_ortho = fftshift(fft(diff(t, P_ortho), norm='ortho'))
    # Jw_E_dir = fftshift(fft(J_E_dir*gaussian_envelope(t, alpha), norm='ortho'))
    # Jw_ortho = fftshift(fft(J_ortho*gaussian_envelope(t, alpha), norm='ortho'))

    I_exact_E_dir, I_exact_ortho = emission_exact(sys, paths, solution,
                                                  E_dir, A_field)
    Iw_exact_E_dir = fftshift(fft(I_exact_E_dir*gaussian_envelope(t, alpha),
                                  norm='ortho'))
    Iw_exact_ortho = fftshift(fft(I_exact_ortho*gaussian_envelope(t, alpha),
                                  norm='ortho'))
    Int_exact_E_dir = (freq**2)*np.abs(Iw_exact_E_dir)**2
    Int_exact_ortho = (freq**2)*np.abs(Iw_exact_ortho)**2

    # Emission intensity
    # Int_E_dir = (freq**2)*np.abs(Pw_E_dir + Jw_E_dir)**2
    # Int_ortho = (freq**2)*np.abs(Pw_ortho + Jw_ortho)**2

    # Save observables to file
    if (BZ_type == '2line'):
        Nk1 = Nk_in_path
        Nk2 = 2

    tail = 'Nk1-{}_Nk2-{}_w{:4.2f}_E{:4.2f}_a{:4.2f}_ph{:3.2f}_T2-{:05.2f}'\
        .format(Nk1, Nk2, w/THz_conv, E0/E_conv, alpha/fs_conv, phase, T2/fs_conv)

    if (save_file):
        I_exact_name = 'Iexact_' + tail
        np.save(I_exact_name, [t, I_exact_E_dir, I_exact_ortho, freq/w,
                Iw_exact_E_dir, Iw_exact_ortho,
                Int_exact_E_dir, Int_exact_ortho])

    if (save_full):
        S_name = 'Sol_' + tail
        np.savez(S_name, t=t, solution=solution, paths=paths,
                 electric_field=electric_field(t))

    if (test):
        freq_lims = (0, 25)
        log_limits = (1e-7, 1e1)
        fig, ((ax_E_dir, ax_Ortho, ax_Total)) = pl.subplots(3, 1)
        ax_E_dir.semilogy(freq/w, Int_exact_E_dir)
        ax_E_dir.set_xlim(freq_lims)
        ax_E_dir.set_ylim(log_limits)
        ax_E_dir.grid(True, axis='x')
        ax_Ortho.semilogy(freq/w, Int_exact_ortho)
        ax_Ortho.set_xlim(freq_lims)
        ax_Ortho.set_ylim(log_limits)
        ax_Ortho.grid(True, axis='x')
        ax_Total.semilogy(freq/w, Int_exact_E_dir + Int_exact_ortho)
        ax_Total.set_xlim(freq_lims)
        ax_Total.set_ylim(log_limits)
        ax_Total.grid(True, axis='x')
        pl.show()

    # J_name = 'J_' + tail
    # np.save(J_name, [t, J_E_dir, J_ortho, freq/w, Jw_E_dir, Jw_ortho])
    # P_name = 'P_' + tail
    # np.save(P_name, [t, P_E_dir, P_ortho, freq/w, Pw_E_dir, Pw_ortho])
    # I_name = 'I_' + tail
    # np.save(I_name, [t, I_E_dir, I_ortho, freq/w, np.abs(Iw_E_dir),
    #                  np.abs(Iw_ortho), Int_E_dir, Int_ortho])

    # driving_tail = 'w{:4.2f}_E{:4.2f}_a{:4.2f}_ph{:3.2f}_wc-{:4.3f}'\
    #     .format(w/THz_conv, E0/E_conv, alpha/fs_conv, phase, chirp/THz_conv)

    # D_name = 'E_' + driving_tail
    # np.save(D_name, [t, electric_field(t)])


###############################################################################
# FUNCTIONS
###############################################################################
def mesh(params, E_dir):
    Nk_in_path = params.Nk_in_path                    # Number of kpoints in each of the two paths
    rel_dist_to_Gamma = params.rel_dist_to_Gamma      # relative distance (in units of 2pi/a) of both paths to Gamma
    a = params.a                                      # Lattice spacing
    length_path_in_BZ = params.length_path_in_BZ      #

    alpha_array = np.linspace(-0.5 + (1/(2*Nk_in_path)),
                              0.5 - (1/(2*Nk_in_path)), num=Nk_in_path)
    vec_k_path = E_dir*length_path_in_BZ

    vec_k_ortho = 2.0*(np.pi/a)*rel_dist_to_Gamma*np.array([E_dir[1], -E_dir[0]])

    # Containers for the mesh, and BZ directional paths
    mesh = []
    paths = []

    # Create the kpoint mesh and the paths
    for path_index in [-1, 1]:
        # Container for a single path
        path = []
        for alpha in alpha_array:
            # Create a k-point
            kpoint = path_index*vec_k_ortho + alpha*vec_k_path

            mesh.append(kpoint)
            path.append(kpoint)

        # Append the a1'th path to the paths array
        paths.append(path)

    dk = 1.0/Nk_in_path*length_path_in_BZ

    return dk, np.array(mesh), np.array(paths)


def hex_mesh(Nk1, Nk2, a, b1, b2, align):
    alpha1 = np.linspace(-0.5 + (1/(2*Nk1)), 0.5 - (1/(2*Nk1)), num=Nk1)
    alpha2 = np.linspace(-0.5 + (1/(2*Nk2)), 0.5 - (1/(2*Nk2)), num=Nk2)

    def is_in_hex(p, a):
        # Returns true if the point is in the hexagonal BZ.
        # Checks if the absolute values of x and y components of p are within
        # the first quadrant of the hexagon.
        x = np.abs(p[0])
        y = np.abs(p[1])
        return ((y <= 2.0*np.pi/(np.sqrt(3)*a)) and
                (np.sqrt(3.0)*x + y <= 4*np.pi/(np.sqrt(3)*a)))

    def reflect_point(p, a, b1, b2):
        x = p[0]
        y = p[1]
        if (y > 2*np.pi/(np.sqrt(3)*a)):   # Crosses top
            p -= b2
        elif (y < -2*np.pi/(np.sqrt(3)*a)):
            # Crosses bottom
            p += b2
        elif (np.sqrt(3)*x + y > 4*np.pi/(np.sqrt(3)*a)):
            # Crosses top-right
            p -= b1 + b2
        elif (-np.sqrt(3)*x + y < -4*np.pi/(np.sqrt(3)*a)):
            # Crosses bot-right
            p -= b1
        elif (np.sqrt(3)*x + y < -4*np.pi/(np.sqrt(3)*a)):
            # Crosses bot-left
            p += b1 + b2
        elif (-np.sqrt(3)*x + y > 4*np.pi/(np.sqrt(3)*a)):
            # Crosses top-left
            p += b1
        return p

    # Containers for the mesh, and BZ directional paths
    mesh = []
    paths = []

    # Create the Monkhorst-Pack mesh
    if align == 'M':
        for a2 in alpha2:
            # Container for a single gamma-M path
            path_M = []
            for a1 in alpha1:
                # Create a k-point
                kpoint = a1*b1 + a2*b2
                # If current point is in BZ, append it to the mesh and path_M
                if (is_in_hex(kpoint, a)):
                    mesh.append(kpoint)
                    path_M.append(kpoint)
                # If current point is NOT in BZ, reflect it along
                # the appropriate axis to get it in the BZ, then append.
                else:
                    while (not is_in_hex(kpoint, a)):
                        kpoint = reflect_point(kpoint, a, b1, b2)
                    mesh.append(kpoint)
                    path_M.append(kpoint)
            # Append the a1'th path to the paths array
            paths.append(path_M)

    elif align == 'K':
        b_a1 = 8*np.pi/(a*3)*np.array([1, 0])
        b_a2 = 4*np.pi/(a*3)*np.array([1, np.sqrt(3)])
        # Extend over half of the b2 direction and 1.5x the b1 direction
        # (extending into the 2nd BZ to get correct boundary conditions)
        alpha1 = np.linspace(-0.5 + (1/(2*Nk1)), 1.0 - (1/(2*Nk1)), num=Nk1)
        alpha2 = np.linspace(0, 0.5 - (1/(2*Nk2)), num=Nk2)
        for a2 in alpha2:
            path_K = []
            for a1 in alpha1:
                kpoint = a1*b_a1 + a2*b_a2
                if is_in_hex(kpoint, a):
                    mesh.append(kpoint)
                    path_K.append(kpoint)
                else:
                    kpoint -= (2*np.pi/a) * np.array([1, 1/np.sqrt(3)])
                    mesh.append(kpoint)
                    path_K.append(kpoint)
            paths.append(path_K)

    return np.array(mesh), np.array(paths)


def make_electric_field(E0, w, alpha, chirp, phase):
    @njit
    def electric_field(t):
        '''
        Returns the instantaneous driving pulse field
        '''
        # Non-pulse
        # return E0*np.sin(2.0*np.pi*w*t)
        # Chirped Gaussian pulse
        return E0*np.exp(-t**2/(2*alpha)**2) \
            * np.sin(2.0*np.pi*w*t*(1 + chirp*t) + phase)

    return electric_field


def diff(x, y):
    '''
    Takes the derivative of y w.r.t. x
    '''
    if (len(x) != len(y)):
        raise ValueError('Vectors have different lengths')
    elif len(y) == 1:
        return 0
    else:
        dx = np.gradient(x)
        dy = np.gradient(y)
        return dy/dx


def gaussian_envelope(t, alpha):
    '''
    Function to multiply a Function f(t) before Fourier transform
    to ensure no step in time between t_final and t_final + delta
    '''
    # sigma = sqrt(2)*alpha
    return 1/(2*np.sqrt(np.pi)*alpha)*np.exp(-t**2/(2*alpha)**2)


def polarization(dip, paths, pcv, E_dir):
    '''
    Calculates the polarization as: P(t) = sum_n sum_m sum_k [d_nm(k)p_nm(k)]
    Dipole term currently a crude model to get a vector polarization
    '''
    E_ort = np.array([E_dir[1], -E_dir[0]])

    d_E_dir, d_ortho = [], []
    for path in paths:

        kx_in_path = path[:, 0]
        ky_in_path = path[:, 1]

        # Evaluate the dipole moments in path
        di_01x = dip.Axfjit[0][1](kx=kx_in_path, ky=ky_in_path)
        di_01y = dip.Ayfjit[0][1](kx=kx_in_path, ky=ky_in_path)

        # Append the dot product d.E
        d_E_dir.append(di_01x*E_dir[0] + di_01y*E_dir[1])
        d_ortho.append(di_01x*E_ort[0] + di_01y*E_ort[1])

    d_E_dir_swapped = np.swapaxes(d_E_dir, 0, 1)
    d_ortho_swapped = np.swapaxes(d_ortho, 0, 1)

    P_E_dir = 2*np.real(np.tensordot(d_E_dir_swapped, pcv, 2))
    P_ortho = 2*np.real(np.tensordot(d_ortho_swapped, pcv, 2))

    return P_E_dir, P_ortho


def current(sys, paths, fv, fc, t, alpha, E_dir):
    '''
    Calculates the current as: J(t) = sum_k sum_n [j_n(k)f_n(k,t)]
    where j_n(k) != (d/dk) E_n(k)
    '''
    E_ort = np.array([E_dir[1], -E_dir[0]])

    # Calculate the gradient analytically at each k-point
    J_E_dir, J_ortho = [], []
    jc_E_dir, jc_ortho, jv_E_dir, jv_ortho = [], [], [], []
    for path in paths:
        path = np.array(path)
        kx_in_path = path[:, 0]
        ky_in_path = path[:, 1]

        evdx = sys.ederivfjit[0](kx=kx_in_path, ky=ky_in_path)
        evdy = sys.ederivfjit[1](kx=kx_in_path, ky=ky_in_path)
        ecdx = sys.ederivfjit[2](kx=kx_in_path, ky=ky_in_path)
        ecdy = sys.ederivfjit[3](kx=kx_in_path, ky=ky_in_path)

        # 0: v, x   1: v,y   2: c, x  3: c, y
        jc_E_dir.append(ecdx*E_dir[0] + ecdy*E_dir[1])
        jc_ortho.append(ecdx*E_ort[0] + ecdy*E_ort[1])
        jv_E_dir.append(evdx*E_dir[0] + evdy*E_dir[1])
        jv_ortho.append(evdx*E_ort[0] + evdy*E_ort[1])

    jc_E_dir = np.swapaxes(jc_E_dir, 0, 1)
    jc_ortho = np.swapaxes(jc_ortho, 0, 1)
    jv_E_dir = np.swapaxes(jv_E_dir, 0, 1)
    jv_ortho = np.swapaxes(jv_ortho, 0, 1)

    # tensordot for contracting the first two indices (2 kpoint directions)
    J_E_dir = np.tensordot(jc_E_dir, fc, 2) + np.tensordot(jv_E_dir, fv, 2)
    J_ortho = np.tensordot(jc_ortho, fc, 2) + np.tensordot(jv_ortho, fv, 2)

    # Return the real part of each component
    return np.real(J_E_dir), np.real(J_ortho)


def emission_exact(sys, paths, solution, E_dir, A_field):

    E_ort = np.array([E_dir[1], -E_dir[0]])

    n_time_steps = np.size(solution[0, 0, :, 0])

    # I_E_dir is of size (number of time steps)
    I_E_dir = np.zeros(n_time_steps)
    I_ortho = np.zeros(n_time_steps)

    for i_time in range(n_time_steps):

        for i_path, path in enumerate(paths):
            path = np.array(path)
            kx_in_path = path[:, 0]
            ky_in_path = path[:, 1]

            kx_in_path_shifted = kx_in_path  # - A_field[i_time]*E_dir[0]
            ky_in_path_shifted = ky_in_path  # - A_field[i_time]*E_dir[1]

            h_deriv_x = ev_mat(sys.hderivfjit[0], kx=kx_in_path_shifted,
                               ky=ky_in_path_shifted)
            h_deriv_y = ev_mat(sys.hderivfjit[1], kx=kx_in_path_shifted,
                               ky=ky_in_path_shifted)

            h_deriv_E_dir = h_deriv_x*E_dir[0] + h_deriv_y*E_dir[1]
            h_deriv_ortho = h_deriv_x*E_ort[0] + h_deriv_y*E_ort[1]

            U = sys.Uf(kx=kx_in_path, ky=ky_in_path)
            U_h = sys.Uf_h(kx=kx_in_path, ky=ky_in_path)

            for i_k in range(np.size(kx_in_path)):

                dH_U_E_dir = np.matmul(h_deriv_E_dir[:, :, i_k], U[:, :, i_k])
                U_h_H_U_E_dir = np.matmul(U_h[:, :, i_k], dH_U_E_dir)

                dH_U_ortho = np.matmul(h_deriv_ortho[:, :, i_k], U[:, :, i_k])
                U_h_H_U_ortho = np.matmul(U_h[:, :, i_k], dH_U_ortho)

                I_E_dir[i_time] += np.real(U_h_H_U_E_dir[0, 0])\
                    * np.real(solution[i_k, i_path, i_time, 0])
                I_E_dir[i_time] += np.real(U_h_H_U_E_dir[1, 1])\
                    * np.real(solution[i_k, i_path, i_time, 3])
                I_E_dir[i_time] += 2*np.real(U_h_H_U_E_dir[0, 1]
                                             * solution[i_k, i_path, i_time, 2])

                I_ortho[i_time] += np.real(U_h_H_U_ortho[0, 0])\
                    * np.real(solution[i_k, i_path, i_time, 0])
                I_ortho[i_time] += np.real(U_h_H_U_ortho[1, 1])\
                    * np.real(solution[i_k, i_path, i_time, 3])
                I_ortho[i_time] += 2*np.real(U_h_H_U_ortho[0, 1]
                                             * solution[i_k, i_path, i_time, 2])

    return I_E_dir, I_ortho


def make_fnumba(sys, dipole, E_dir, gamma1, gamma2, electric_field):

    @njit
    def fnumba(t, y, kpath, dk, ecv_in_path, dipole_in_path, A_in_path, y0):
        # x != y(t+dt)
        x = np.empty(np.shape(y), dtype=np.dtype('complex'))

        # Gradient term coefficient
        electric_f = electric_field(t)
        D = electric_f/(2*dk)

        # Update the solution vector
        Nk_path = kpath.shape[0]
        for k in range(Nk_path):
            i = 4*k
            if k == 0:
                m = 4*(k+1)
                n = 4*(Nk_path-1)
            elif k == Nk_path-1:
                m = 0
                n = 4*(k-1)
            else:
                m = 4*(k+1)
                n = 4*(k-1)

            # Energy term eband(i,k) the energy of band i at point k
            ecv = ecv_in_path[k]

            # Rabi frequency: w_R = d_12(k).E(t)
            # Rabi frequency conjugate
            wr = dipole_in_path[k]*electric_f
            wr_c = wr.conjugate()

            # Rabi frequency: w_R = (d_11(k) - d_22(k))*E(t)
            # wr_d_diag   = A_in_path[k]*D
            wr_d_diag = A_in_path[k]*electric_f

            # Update each component of the solution vector
            # i = f_v, i+1 = p_vc, i+2 = p_cv, i+3 = f_c
            x[i] = 2*(wr*y[i+1]).imag + D*(y[m] - y[n]) \
                - gamma1*(y[i]-y0[i])

            x[i+1] = (1j*ecv - gamma2 + 1j*wr_d_diag)*y[i+1] \
                - 1j*wr_c*(y[i]-y[i+3]) + D*(y[m+1] - y[n+1])

            x[i+2] = x[i+1].conjugate()

            x[i+3] = -2*(wr*y[i+1]).imag + D*(y[m+3] - y[n+3]) \
                - gamma1*(y[i+3]-y0[i+3])

        x[-1] = -electric_f
        return x

    def f(t, y, kpath, dk, ecv_in_path, dipole_in_path, A_in_path, y0):
        return fnumba(t, y, kpath, dk, ecv_in_path, dipole_in_path, A_in_path, y0)

    return f


def initial_condition(e_fermi, temperature, e_c):
    knum = e_c.size
    ones = np.ones(knum)
    zeros = np.zeros(knum)
    if (temperature > 1e-5):
        distrib = 1/(np.exp((e_c-e_fermi)/temperature) + 1)
        return np.array([ones, zeros, zeros, distrib]).flatten('F')
    else:
        smaller_e_fermi = (e_fermi - e_c) < 0
        distrib = ones[smaller_e_fermi]
        return np.array([ones, zeros, zeros, distrib]).flatten('F')


def BZ_plot(kpnts, a, b1, b2, paths, si_units=True):

    as_to_au = 1.88973
    au_to_as = 0.529177

    if (si_units):
        a *= au_to_as
        kpnts *= as_to_au
        b1 *= as_to_au
        b2 *= as_to_au

    R = 4.0*np.pi/(3*a)
    r = 2.0*np.pi/(np.sqrt(3)*a)

    BZ_fig = pl.figure(figsize=(10, 10))
    ax = BZ_fig.add_subplot(111, aspect='equal')

    for b in ((0, 0), b1, -b1, b2, -b2, b1+b2, -b1-b2):
        poly = RegularPolygon(b, 6, radius=R, orientation=np.pi/6, fill=False)
        ax.add_patch(poly)

#    ax.arrow(-0.5*E_dir[0], -0.5*E_dir[1], E_dir[0], E_dir[1],
#             width=0.005, alpha=0.5, label='E-field')

    pl.scatter(0, 0, s=15, c='black')
    pl.text(0.01, 0.01, r'$\Gamma$')
    pl.scatter(r*np.cos(-np.pi/6), r*np.sin(-np.pi/6), s=15, c='black')
    pl.text(r*np.cos(-np.pi/6)+0.01, r*np.sin(-np.pi/6)-0.05, r'$M$')
    pl.scatter(R, 0, s=15, c='black')
    pl.text(R, 0.02, r'$K$')
    pl.scatter(kpnts[:, 0], kpnts[:, 1], s=10)
    pl.xlim(-7.0/a, 7.0/a)
    pl.ylim(-7.0/a, 7.0/a)

    if (si_units):
        pl.xlabel(r'$k_x \text{ in } 1/\si{\angstrom}$')
        pl.ylabel(r'$k_y \text{ in } 1/\si{\angstrom}$')
    else:
        pl.xlabel(r'$k_x \text{ in } 1/a_0$')
        pl.ylabel(r'$k_y \text{ in } 1/a_0$')

    for path in paths:
        path = np.array(path)
        pl.plot(path[:, 0], path[:, 1])

    pl.show()
