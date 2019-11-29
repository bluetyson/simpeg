
"""
Magnetics
=========

Here we use the module *SimPEG.potential_fields.magnetics* to predict magnetic
data for magnetic susceptibility and magnetic vector models.
For this tutorial, we focus on the following:

    - How to define the survey
    - How to generate a tensor mesh or an OcTree mesh based on survey geometry
    - How to predict magnetic data for a susceptibility model
    - How to predict magnetic data in the case of remanence
    - How to include surface topography
    - The units of the physical property model and resulting data

The tutorial contains two forward simulations. In the first , we predict
magnetic data resulting purely from induced magnetization. This is done using
a tensor mesh. In the second simulation, we predict magnetic data in the case
of magnetic remanence. This is done using an OcTree mesh.
    

"""

#########################################################################
# Import Modules
# --------------
#

import numpy as np
from scipy.interpolate import LinearNDInterpolator
import matplotlib as mpl
import matplotlib.pyplot as plt

from discretize import TensorMesh, TreeMesh
from discretize.utils import mkvc, refine_tree_xyz
from SimPEG.utils import plot2Ddata, ModelBuilder, surface2ind_topo, matutils
from SimPEG import maps
from SimPEG.potential_fields import magnetics

# sphinx_gallery_thumbnail_number = 4


#############################################
# Topography
# ----------
#
# Here we define surface topography as an (N, 3) numpy array. Topography could
# also be loaded from a file. This topography is used for both examples.
#

[x_topo, y_topo] = np.meshgrid(
        np.linspace(-200, 200, 41), np.linspace(-200, 200, 41)
        )
z_topo = -15*np.exp(-(x_topo**2 + y_topo**2) / 80**2)
x_topo, y_topo, z_topo = mkvc(x_topo), mkvc(y_topo), mkvc(z_topo)
xyz_topo = np.c_[x_topo, y_topo, z_topo]

#############################################
# Defining the Survey
# -------------------
#
# Here, we define the survey that will be used for both forward simulations.
# Magnetic surveys are simple to create. The user needs an (N, 3) array to define
# the xyz positions of the observation locations. The user also needs to
# define the Earth's magnetic field intensity and orientation. Here, we
# create a basic airborne survey with a flight height of 10 m above the
# surface topography.
#

# Define the observation locations as an (N, 3) numpy array or load them.
x = np.linspace(-80., 80., 17)
y = np.linspace(-80., 80., 17)
x, y = np.meshgrid(x, y)
x, y = mkvc(x.T), mkvc(y.T)
fun_interp = LinearNDInterpolator(np.c_[x_topo, y_topo], z_topo)
z = fun_interp(np.c_[x, y]) + 10  # Flight height 10 m above surface.
receiver_locations = np.c_[x, y, z]

# Define the receivers. Here the user may define the receiver to measure
# total magnetic intensity, Cartesian components of the anomalous field or
# gradient components of the magnetic field (for magnetic gradiometry)
receiver_list = magnetics.receivers.point_receiver(receiver_locations, "tmi")

# Define the inducing field H0 = (intensity [nT], inclination [deg], declination [deg])
inclination = 90
declination = 0
strength = 50000

inducing_field = (strength, inclination, declination)
source_field = magnetics.sources.SourceField(
    receiver_list=[receiver_list], parameters=inducing_field
    )

# Define the survey
survey = magnetics.survey.MagneticSurvey(source_field)


#############################################
# Defining a Tensor Mesh
# ----------------------
#
# Here, we create the tensor mesh that will be used to predict magnetic
# for our first forward simulation.
#

dh = 5.
hx = [(dh, 5, -1.3), (dh, 40), (dh, 5, 1.3)]
hy = [(dh, 5, -1.3), (dh, 40), (dh, 5, 1.3)]
hz = [(dh, 5, -1.3), (dh, 15)]
mesh = TensorMesh([hx, hy, hz], 'CCN')


#############################################
# Defining a Susceptibility Model
# -------------------------------
#
# Here, we create the model that will be used to predict magnetic data
# and the mapping from the model to the mesh. The model
# consists of a susceptible sphere in a less susceptible host.
#

# Define susceptibility values for each unit in SI
background_value = 0.0001
sphere_value = 0.01

# Find cells that are active in the forward modeling (cells below surface)
ind_active = surface2ind_topo(mesh, xyz_topo)

# Define mapping from model to active cells
nC = int(ind_active.sum())
model_map = maps.IdentityMap(nP=nC)  # model is a vlue for each active cell

# Define model
model = background_value*np.ones(ind_active.sum())
ind_sphere = ModelBuilder.getIndicesSphere(
    np.r_[0., 0., -45.], 15., mesh.gridCC
)
ind_sphere = ind_sphere[ind_active]
model[ind_sphere] = sphere_value

# Plot Model
fig = plt.figure(figsize=(9, 4))

plotting_map = maps.InjectActiveCells(mesh, ind_active, np.nan)
ax1 = fig.add_axes([0.05, 0.05, 0.78, 0.9])
mesh.plotSlice(
    plotting_map*model, normal='Y', ax=ax1, ind=int(mesh.nCy/2), grid=True,
    clim=(np.min(model), np.max(model))
)
ax1.set_title('Model slice at y = 0 m')

ax2 = fig.add_axes([0.85, 0.05, 0.05, 0.9])
norm = mpl.colors.Normalize(vmin=np.min(model), vmax=np.max(model))
cbar = mpl.colorbar.ColorbarBase(
    ax2, norm=norm, orientation='vertical'
)
cbar.set_label(
    'Magnetic Susceptibility (SI)',
    rotation=270, labelpad=15, size=12
)

plt.show()


###################################################################
# Simulation 1: TMI Data for a Susceptibility Model
# -------------------------------------------------
#
# Here we demonstrate how to predict magnetic data for a magnetic
# susceptibility model.
#

# Define the forward simluation
mag_simulation = magnetics.simulation.MagneticIntegralSimulation(
    survey=survey, mesh=mesh,
    modelType='susceptibility', chiMap=model_map,
    actInd=ind_active, forwardOnly=True
)

# Compute predicted data for a susceptibility model
dpred_mag = mag_simulation.dpred(model)

# Plot
fig = plt.figure(figsize=(6, 5))
v_max = np.max(np.abs(dpred_mag))

ax1 = fig.add_axes([0.05, 0.05, 0.8, 0.9])
plot2Ddata(
    receiver_list.locs, dpred_mag, ax=ax1, ncontour=30, clim=(-v_max, v_max),
    contourOpts={"cmap": "RdBu_r"}
)
ax1.set_title('TMI Anomaly')

ax2 = fig.add_axes([0.85, 0.05, 0.05, 0.9])
norm = mpl.colors.Normalize(
        vmin=-np.max(np.abs(dpred_mag)), vmax=np.max(np.abs(dpred_mag))
)
cbar = mpl.colorbar.ColorbarBase(
        ax2, norm=norm, orientation='vertical', cmap=mpl.cm.RdBu_r
)
cbar.set_label('$nT$', rotation=270, labelpad=15, size=12)

plt.show()


##########################################################
# Defining an OcTree Mesh
# -----------------------
#
# Here, we create the OcTree mesh that will be used to predict magnetic anomaly
# data for our second forward simuulation.
# 

dx = 5    # minimum cell width (base mesh cell width) in x
dy = 5    # minimum cell width (base mesh cell width) in y
dz = 5    # minimum cell width (base mesh cell width) in z

x_length = 240.     # domain width in x
y_length = 240.     # domain width in y
z_length = 120.     # domain width in y

# Compute number of base mesh cells required in x and y
nbcx = 2**int(np.round(np.log(x_length/dx)/np.log(2.)))
nbcy = 2**int(np.round(np.log(y_length/dy)/np.log(2.)))
nbcz = 2**int(np.round(np.log(z_length/dz)/np.log(2.)))

# Define the base mesh
hx = [(dx, nbcx)]
hy = [(dy, nbcy)]
hz = [(dz, nbcz)]
mesh = TreeMesh([hx, hy, hz], x0='CCN')

# Refine based on surface topography
mesh = refine_tree_xyz(
    mesh, xyz_topo, octree_levels=[2, 2], method='surface', finalize=False
)

# Refine box base on region of interest
xp, yp, zp = np.meshgrid([-100., 100.], [-100., 100.], [-80., 0.])
xyz = np.c_[mkvc(xp), mkvc(yp), mkvc(zp)]

mesh = refine_tree_xyz(
    mesh, xyz, octree_levels=[2, 2], method='box', finalize=False
)

mesh.finalize()

##########################################################
# Create Magnetic Vector Intensity Model (MVI)
# --------------------------------------------
#
# Magnetic vector models are defined by three-component effective
# susceptibilities. To create a magnetic vector
# model, we must
#
#     1) Define the magnetic susceptibility for each cell. Then multiply by the
#     unit vector direction of the inducing field. (induced contribution)
#     2) Define the remanent magnetization vector for each cell and normalized
#     by the magnitude of the Earth's field (remanent contribution)
#     3) Sum the induced and remanent contributions
#     4) Define as a vector np.r_[chi_1, chi_2, chi_3]
#     
#

# Define susceptibility values for each unit in SI
background_value = 0.0001
sphere_value = 0.01

# Find cells active in the forward modeling (cells below surface)
ind_active = surface2ind_topo(mesh, xyz_topo)

# Define mapping from model to active cells
nC = int(ind_active.sum())
model_map = maps.IdentityMap(nP=3*nC)  # model has 3 parameters for each cell

# Define susceptibility for each cell
model = background_value*np.ones(ind_active.sum())
ind_sphere = ModelBuilder.getIndicesSphere(
    np.r_[0.,  0., -45.], 15., mesh.gridCC
)
ind_sphere = ind_sphere[ind_active]
model[ind_sphere] = sphere_value

# Compute the unit direction of the inducing field in Cartesian coordinates
u = matutils.dip_azimuth2cartesian(inclination, declination)

# Multiply susceptibility model to obtain the x, y, z components of the
# effective susceptibility contribution from induced magnetization
susceptibility_model = np.outer(model, u)

# Define the effective susceptibility contribution for remanent magnetization to have a
# magnitude of 0.006 SI, with inclination -45 and declination 90
remanence_value = 0.006
remanence_model = np.zeros(np.shape(susceptibility_model))
effective_susceptibility_sphere = remanence_value*matutils.dip_azimuth2cartesian(-45, 90)
remanence_model[ind_sphere, :] = effective_susceptibility_sphere

# Define effective susceptibility model as a vector np.r_[chi_x, chi_y, chi_z]
model = mkvc(susceptibility_model + remanence_model)

# Plot Effective Susceptibility Model
fig = plt.figure(figsize=(9, 4))

plotting_map = maps.InjectActiveCells(mesh, ind_active, np.nan)
plotting_model = np.sqrt(np.sum(susceptibility_model + remanence_model, axis=1)**2)
ax1 = fig.add_axes([0.05, 0.05, 0.78, 0.9])
mesh.plotSlice(
    plotting_map*plotting_model, normal='Y', ax=ax1,
    ind=int(mesh.hy.size/2), grid=True,
    clim=(np.min(plotting_model), np.max(plotting_model))
)
ax1.set_title('MVI Model at y = 0 m')

ax2 = fig.add_axes([0.85, 0.05, 0.05, 0.9])
norm = mpl.colors.Normalize(vmin=np.min(plotting_model), vmax=np.max(plotting_model))
cbar = mpl.colorbar.ColorbarBase(ax2, norm=norm, orientation='vertical')
cbar.set_label(
    'Effective Susceptibility (SI)', rotation=270, labelpad=15, size=12
)


###################################################################
# Simulation 2: TMI Data for a MVI Model
# --------------------------------------
#
# Here we predict magnetic data for an effective susceptibility model in the
# case of remanent magnetization.
#

# Define the forward modeling problem. Set modelType to 'vector'
mvi_simulation = magnetics.simulation.MagneticIntegralSimulation(
    survey=survey, mesh=mesh, chiMap=model_map, actInd=ind_active,
    modelType='vector'
)

# Compute predicted data for some model
dpred_mvi = mvi_simulation.dpred(mkvc(model))

dpred_mvi = dpred_mvi + 5e-5*np.random.rand(len(dpred_mvi))

# Plot
fig = plt.figure(figsize=(10, 3))

ax1 = fig.add_axes([0.05, 0.05, 0.25, 0.9])
cplot1 = plot2Ddata(
    receiver_list.locs, dpred_mag, ax=ax1, ncontour=30, clim=(-v_max, v_max),
    contourOpts={"cmap": "RdBu_r"}
)
cplot1[0].set_clim((-v_max, v_max))
ax1.set_title('Induced')

ax2 = fig.add_axes([0.31, 0.05, 0.25, 0.9])
cplot2 = plot2Ddata(
    receiver_list.locs, dpred_mvi - dpred_mag, ax=ax2, ncontour=30,
    clim=(-v_max, v_max), contourOpts={"cmap": "RdBu_r"}
)
cplot2[0].set_clim((-v_max, v_max))
ax2.set_title('Remanent')
ax2.set_yticks([])

ax3 = fig.add_axes([0.57, 0.05, 0.25, 0.9])
cplot3 = plot2Ddata(
    receiver_list.locs, dpred_mvi, ax=ax3, ncontour=30, clim=(-v_max, v_max),
    contourOpts={"cmap": "RdBu_r"}
)
cplot3[0].set_clim((-v_max, v_max))
ax3.set_title('Total')
ax3.set_yticks([])

ax4 = fig.add_axes([0.84, 0.08, 0.03, 0.83])
norm = mpl.colors.Normalize(vmin=-v_max, vmax=v_max)
cbar = mpl.colorbar.ColorbarBase(
    ax4, norm=norm, orientation='vertical', cmap=mpl.cm.RdBu_r
)
cbar.set_label(
    '$nT$',
    rotation=270, labelpad=15, size=12
)

plt.show()
