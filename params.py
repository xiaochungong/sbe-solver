#Input parameters for SBE.py
import numpy as np

# System parameters
#########################################################################
a                   = 8.308       # Lattice spacing in atomic units (4.395 A)
e_fermi             = 0.2         # Fermi energy in eV
temperature         = 0.03        # Temperature in eV

# Model Hamiltonian parameters 
C0                  = 0           # Dirac point position
C2                  = 0           # k^2 coefficient
A                   = 0.1974      # Fermi velocity
R                   = 11.06       # k^3 coefficient
k_cut               = 0.05       # Model hamiltonian cutoff

# Brillouin zone parameters
##########################################################################
# Type of Brillouin zone
# 'full' for full hexagonal BZ, '2line' for two lines with adjustable size
BZ_type = '2line'

# Reciprocal lattice vectors
b1 = (2*np.pi/(a*np.sqrt(3)))*np.array([np.sqrt(3),-1])
b2 = (4*np.pi/(a*np.sqrt(3)))*np.array([0,1])

# full BZ parametes
Nk1                 = 50           # Number of kpoints in b1 direction
Nk2                 = 50           # Number of kpoints in b2 direction (number of paths)

# 2line BZ parameters
Nk_in_path          = 400         # Number of kpoints in each of the two paths
rel_dist_to_Gamma   = 0.05        # relative distance (in units of 2pi/a) of both paths to Gamma
length_path_in_BZ   = 5*np.pi/a   # Length of path in BZ 
angle_inc_E_field   = 0           # incoming angle of the E-field in degree

# Driving field parameters
##########################################################################
align               = 'K'         # E-field direction (gamma-'K' or gamma-'M')
E0                  = 5.0         # Pulse amplitude (MV/cm)
w                   = 25.0        # Pulse frequency (THz)
wt                  = 0.01        # Pulse chirp frequency (THz)
alpha               = 25.0         # Gaussian pulse width (femtoseconds)
phase               = (0/1)*2*np.pi# Carrier envelope phase (edited by cep-scan.py)

# Time scales (all units in femtoseconds)
##########################################################################
T1    = 10      # Phenomenological occupations damping time
T2    = 1      # Phenomenological polarization damping time 
t0    = -1200  # Start time *pulse centered @ t=0, use t0 << 0
tf    = 1200   # End time
dt    = 0.02   # Time step

# Unit conversion factors
##########################################################################
fs_conv = 41.34137335                  #(1fs    = 41.341473335 a.u.)
E_conv = 0.0001944690381               #(1MV/cm = 1.944690381*10^-4 a.u.) 
THz_conv = 0.000024188843266           #(1THz   = 2.4188843266*10^-5 a.u.)
amp_conv = 150.97488474                #(1A     = 150.97488474)
eV_conv = 0.03674932176                #(1eV    = 0.036749322176 a.u.)

# Flags for testing and features
##########################################################################
user_out      = True  # Set to True to get user plotting and progress output
energy_plots  = False  # Set to True to plot 3d energy bands and contours
dipole_plots  = False  # Set tp True to plot dipoles (currently not working?)
test          = False  # Set to True to output travis testing parameters
matrix_method = False  # Set to True to use old matrix method for solving

