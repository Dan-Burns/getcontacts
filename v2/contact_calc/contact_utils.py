##############################################################################
# MDContactNetworks: A Python Library for computing non-covalent contacts
#                    throughout Molecular Dynamics Trajectories. 
# Copyright 2016-2017 Stanford University and the Authors
#
# Authors: Anthony Kai Kwang Ma
# Email: anthony.ma@yale.edu, anthonyma27@gmail.com, akma327@stanford.edu
##############################################################################

##############################################################################
# Imports
##############################################################################

from vmd import *
import molecule
import numpy as np
import math

def get_file_type(file_name):
	"""
	Determine file type by extracting suffix of file_name
	"""
	file_type = file_name.split(".")[-1].strip()
	if(file_type == "nc"): file_type = 'netcdf'
	return file_type

def load_traj(TOP, TRAJ, beg_frame, end_frame, stride):
	"""
	Loads in topology and trajectory into VMD

	Parameters
	----------
	TOP: MD Topology
	TRAJ: MD Trajectory
	beg_frame: int 
	end_frame: int 
	stride: int 

	Returns
	-------
	trajid: int
	simulation molid object 
	"""

	top_file_type = get_file_type(TOP)
	traj_file_type = get_file_type(TRAJ)
	trajid = molecule.load(top_file_type, TOP)
	molecule.read(trajid, traj_file_type, TRAJ, beg=beg_frame, end=end_frame, skip=stride, waitfor=-1)
	return trajid

def get_atom_selection_labels(selection_id):
	"""
	Returns list of atom labels for each atom in selection_id
	"""
	chains, resnames, resids, names, indices = get_atom_selection_properties(selection_id)
	atom_labels = []
	for idx in range(len(chains)):
		chain, resname, resid, name, index = chains[idx], resnames[idx], resids[idx], names[idx], indices[idx]
		atom_labels.append("%s:%s:%s:%s:%s" % (chain, resname, resid, name, index))

	return atom_labels

def get_atom_selection_properties(selection_id):
	"""
	After executing an evaltcl atom selection command, this function
	is called to retrieve the chain, resname, resid, name, and index 
	of each atom in the selection 

	Parameters
	----------
	selection_id: string
		Denotes the atom selection identifier 

	Returns
	-------
	chains: list of strings 
		Chain identifier for each atom ["A", "B", "A", ...]
	resnames: list of strings 
		Resname for each atom ["ASP", "GLU", "TYR", ...]
	resids: list of strings 
		Residue index for each atom ["12", "45", ...]
	names: list of strings
		Atom name of each atom ["NZ", "CA", "N", ...]
	indices: list of strings
		VMD based index for each atom ["12304", "1231", ...]
	"""

	chains = map(str, evaltcl("$%s get chain" % (selection_id)).split(" "))
	resnames = map(str, evaltcl("$%s get resname" % (selection_id)).split(" "))
	resids = map(str, evaltcl("$%s get resid" % (selection_id)).split(" "))
	names = map(str, evaltcl("$%s get name" % (selection_id)).split(" "))
	indices = map(str, evaltcl("$%s get index" % (selection_id)).split(" "))

	return chains, resnames, resids, names, indices


def gen_index_to_atom_label(TOP, TRAJ):
	"""
	Read in first frame of simulation and generate mapping from 
	VMD index to atom labels

	Parameters
	----------
	TOP: MD Topology
	TRAJ: MD Trajectory

	Returns
	-------
	index_to_label: dict mapping int to string 
		Maps VMD atom index to label "chain:resname:resid:name:index"
		{11205: "A:ASP:114:CA:11205, ...}

	"""
	### Select all atoms from first frame of trajectory
	trajid = load_traj(TOP, TRAJ, 1, 2, 1)
	all_atom_sel = "set all_atoms [atomselect %s \" all \" frame %s]" % (trajid, 0)
	all_atoms = evaltcl(all_atom_sel)
	chains, resnames, resids, names, indices = get_atom_selection_properties("all_atoms")
	evaltcl('$all_atoms delete')

	### Generate mapping
	index_to_label = {}

	for idx, index in enumerate(indices):
		chain = chains[idx]
		resname = resnames[idx]
		resid = resids[idx]
		name = names[idx]
		atom_label = "%s:%s:%s:%s:%s" % (chain, resname, resid, name, index)
		index_key = int(index)
		index_to_label[index_key] = atom_label

	molecule.delete(trajid)
	return index_to_label

def get_anion_atoms(traj_frag_molid, frame_idx, chain_id):
	"""
	Get list of anion atoms that can form salt bridges

	Returns
	-------
	anion_list: list of strings
		List of atom labels for atoms in ASP or GLU that
		can form salt bridges
	"""
	anion_list = []

	if(chain_id == None):
		evaltcl("set ASP [atomselect %s \" (resname ASP) and (name OD1 OD2) \" frame %s]" % (traj_frag_molid, frame_idx))
		evaltcl("set GLU [atomselect %s \" (resname GLU) and (name OE1 OE2) \" frame %s]" % (traj_frag_molid, frame_idx))
	else:
		evaltcl("set ASP [atomselect %s \" (resname ASP) and (name OD1 OD2) and (chain %s) \" frame %s]" % (traj_frag_molid, chain_id, frame_idx))
		evaltcl("set GLU [atomselect %s \" (resname GLU) and (name OE1 OE2) and (chain %s) \" frame %s]" % (traj_frag_molid, chain_id, frame_idx))

	anion_list += get_atom_selection_labels("ASP")
	anion_list += get_atom_selection_labels("GLU")

	evaltcl('$ASP delete')
	evaltcl('$GLU delete')

	return anion_list

def get_cation_atoms(traj_frag_molid, frame_idx, chain_id):
	"""
	Get list of cation atoms that can form salt bridges or pi cation contacts

	Returns
	-------
	cation_list: list of strings
		List of atom labels for atoms in LYS, ARG, HIS that
		can form salt bridges
	"""
	cation_list = []
	if(chain_id == None):
		evaltcl("set LYS [atomselect %s \" (resname LYS) and (name NZ) \" frame %s]" % (traj_frag_molid, frame_idx))
		evaltcl("set ARG [atomselect %s \" (resname ARG) and (name NH1 NH2) \" frame %s]" % (traj_frag_molid, frame_idx))
		evaltcl("set HIS [atomselect %s \" (resname HIS HSD HSE HSP HIE HIP HID) and (name ND1 NE2) \" frame %s]" % (traj_frag_molid, frame_idx))
	else:
		evaltcl("set LYS [atomselect %s \" (resname LYS) and (name NZ) and (chain %s) \" frame %s]" % (traj_frag_molid, chain_id, frame_idx))
		evaltcl("set ARG [atomselect %s \" (resname ARG) and (name NH1 NH2) and (chain %s) \" frame %s]" % (traj_frag_molid, chain_id, frame_idx))
		evaltcl("set HIS [atomselect %s \" (resname HIS HSD HSE HSP HIE HIP HID) and (name ND1 NE2) and (chain %s) \" frame %s]" % (traj_frag_molid, chain_id, frame_idx))

	cation_list += get_atom_selection_labels("LYS")
	cation_list += get_atom_selection_labels("ARG")
	cation_list += get_atom_selection_labels("HIS")

	evaltcl('$LYS delete')
	evaltcl('$ARG delete')
	evaltcl('$HIS delete')

	return cation_list


def get_aromatic_atom_triplets(traj_frag_molid, frame_idx, chain_id):
	"""
	Get list of aromatic atom triplets 

	Returns
	-------
	aromatic_atom_triplet_list: list of tuples corresponding to three equally spaced points
	on the 6-membered rings of TYR, TRP, or PHE residues. 
		[(A:PHE:72:CG:51049, A:PHE:72:CE1:51052, A:PHE:72:CE2:51058), ...]
	"""

	aromatic_atom_list = []
	if(chain_id == None):
		evaltcl("set PHE [atomselect %s \" (resname PHE) and (name CG CE1 CE2) \" frame %s]" % (traj_frag_molid, frame_idx))
		evaltcl("set TRP [atomselect %s \" (resname TRP) and (name CD2 CZ2 CZ3) \" frame %s]" % (traj_frag_molid, frame_idx))
		evaltcl("set TYR [atomselect %s \" (resname TYR) and (name CG CE1 CE2) \" frame %s]" % (traj_frag_molid, frame_idx))
	else:
		evaltcl("set PHE [atomselect %s \" (resname PHE) and (name CG CE1 CE2) and (chain %s)\" frame %s]" % (traj_frag_molid, frame_idx, chain_id))
		evaltcl("set TRP [atomselect %s \" (resname TRP) and (name CD2 CZ2 CZ3) and (chain %s)\" frame %s]" % (traj_frag_molid, frame_idx, chain_id))
		evaltcl("set TYR [atomselect %s \" (resname TYR) and (name CG CE1 CE2) and (chain %s)\" frame %s]" % (traj_frag_molid, frame_idx, chain_id))

	aromatic_atom_list += get_atom_selection_labels("PHE")
	aromatic_atom_list += get_atom_selection_labels("TRP")
	aromatic_atom_list += get_atom_selection_labels("TYR")

	evaltcl("$PHE delete")
	evaltcl("$TRP delete")
	evaltcl("$TYR delete")

	aromatic_atom_triplet_list = []

	### Generate triplets of the three equidistant atoms on an aromatic ring
	for i in range(0, len(aromatic_atom_list), 3): 
		aromatic_atom_triplet_list.append(aromatic_atom_list[i:i+3])

	return aromatic_atom_triplet_list




def calc_water_to_residues_map(water_hbonds, solvent_resn):
	"""
	Returns
	-------
	frame_idx: int
		Specify frame index with respect to the smaller trajectory fragment
	water_to_residues: dict mapping string to list of strings
		Map each water molecule to the list of residues it forms
		contacts with (ie {"W:TIP3:8719:OH2:29279" : ["A:PHE:159:N:52441", ...]})
	solvent_bridges: list
		List of hbond interactions between two water molecules
		[("W:TIP3:757:OH2:2312", "W:TIP3:8719:OH2:29279"), ...]
	"""
	water_to_residues = {}
	_solvent_bridges = []
	for frame_idx, atom1_label, atom2_label, itype in water_hbonds:
		if(solvent_resn in atom1_label and solvent_resn in atom2_label): 
			# print atom1_label, atom2_label
			_solvent_bridges.append((atom1_label, atom2_label))
			continue
		elif(solvent_resn in atom1_label and solvent_resn not in atom2_label):
			water = atom1_label
			protein = atom2_label
		elif(solvent_resn not in atom1_label and solvent_resn in atom2_label):
			water = atom2_label
			protein = atom1_label

		if(water not in water_to_residues):
			water_to_residues[water] = set()
		water_to_residues[water].add(protein)

	### Remove duplicate solvent bridges (w1--w2 and w2--w1 are the same)
	solvent_bridges = set()
	for water1, water2 in _solvent_bridges:
		key1 = (water1, water2)
		key2 = (water2, water1)
		if(key1 not in solvent_bridges and key2 not in solvent_bridges):
			solvent_bridges.add(key1)
	solvent_bridges = sorted(list(solvent_bridges))

	return frame_idx, water_to_residues, solvent_bridges


def compute_distance(molid, frame_idx, atom1_label, atom2_label):
	"""
	Compute distance between two atoms in a specified frame of simulation

	Parameters
	----------
	molid: int 
		Denotes trajectory id in VMD
	frame_idx: int 
		Frame of simulation in trajectory fragment
	atom1_label: string 
		Atom label (ie "A:GLU:323:OE2:55124")
	atom2_label: string 
		Atom label (ie "A:ARG:239:NH1:53746")

	Returns
	-------
	distance: float 
	"""
	atom_index1 = atom1_label.split(":")[-1]
	atom_index2 = atom2_label.split(":")[-1]
	distance = float(evaltcl("measure bond {%s %s} molid %s frame %s" % (atom_index1, atom_index2, molid, frame_idx)))
	return distance

def compute_angle(molid, frame_idx, atom1, atom2, atom3):
	"""
	Compute distance between two atoms in a specified frame of simulation

	Parameters
	----------
	molid: int 
		Denotes trajectory id in VMD
	frame_idx: int 
		Frame of simulation in trajectory fragment
	atom1: string 
		Atom label (ie "A:GLU:323:OE2:55124")
	atom2: string 
		Atom label (ie "A:ARG:239:NH1:53746")
	atom2: string 
		Atom label (ie "A:GLU:118:OE1:51792")

	Returns
	-------
	angle: float
		Expressed in degrees
	"""
	atom_index1 = atom1.split(":")[-1]
	atom_index2 = atom2.split(":")[-1]
	atom_index3 = atom3.split(":")[-1]
	
	angle = float(evaltcl("measure angle {%s %s %s} molid %s frame %s" % (atom_index1, atom_index2, atom_index3, molid, frame_idx)))
	return angle


### Atom property getter functions
def get_chain(traj_frag_molid, frame_idx, index):
	"""
	Parse atom label and return element 

	Parameters
	----------
	traj_frag_molid: int 
		Denotes trajectory id in VMD
	frame_idx: int 
		Frame of simulation in trajectory fragment
	index: string
		VMD atom index

	Returns
	-------
	chain: string (ie "A", "B")
	"""

	evaltcl("set sel [atomselect %s \" index %s \" frame %s]" % (traj_frag_molid, index, frame_idx))
	chain = evaltcl("$sel get chain")
	evaltcl("$sel delete")
	return chain


def get_resname(traj_frag_molid, frame_idx, index):
	"""
	Parse atom label and return element 

	Parameters
	----------
	traj_frag_molid: int 
		Denotes trajectory id in VMD
	frame_idx: int 
		Frame of simulation in trajectory fragment
	index: string
		VMD atom index

	Returns
	-------
	resname: string (ie "ASP", "GLU")
	"""

	evaltcl("set sel [atomselect %s \" index %s \" frame %s]" % (traj_frag_molid, index, frame_idx))
	resname = evaltcl("$sel get resname")
	evaltcl("$sel delete")
	return resname


def get_resid(traj_frag_molid, frame_idx, index):
	"""
	Parse atom label and return element 

	Parameters
	----------
	traj_frag_molid: int 
		Denotes trajectory id in VMD
	frame_idx: int 
		Frame of simulation in trajectory fragment
	index: string
		VMD atom index

	Returns
	-------
	resid: string (ie "115", "117")
	"""

	evaltcl("set sel [atomselect %s \" index %s \" frame %s]" % (traj_frag_molid, index, frame_idx))
	resid = evaltcl("$sel get resid")
	evaltcl("$sel delete")
	return resid

def get_name(traj_frag_molid, frame_idx, index):
	"""
	Parse atom label and return element 

	Parameters
	----------
	traj_frag_molid: int 
		Denotes trajectory id in VMD
	frame_idx: int 
		Frame of simulation in trajectory fragment
	index: string
		VMD atom index

	Returns
	-------
	name: string (ie "CA", "NZ", )
	"""

	evaltcl("set sel [atomselect %s \" index %s \" frame %s]" % (traj_frag_molid, index, frame_idx))
	name = evaltcl("$sel get name")
	evaltcl("$sel delete")
	return name


def get_element(traj_frag_molid, frame_idx, index):
	"""
	Parse atom label and return element 

	Parameters
	----------
	traj_frag_molid: int 
		Denotes trajectory id in VMD
	frame_idx: int 
		Frame of simulation in trajectory fragment
	index: string
		VMD atom index

	Returns
	-------
	element: string (ie "C", "H", "O", "N", "S")
	"""

	evaltcl("set sel [atomselect %s \" index %s \" frame %s]" % (traj_frag_molid, index, frame_idx))
	element = evaltcl("$sel get element")
	evaltcl("$sel delete")
	return element

def get_atom_label(traj_frag_molid, frame_idx, index):
	chain = get_chain(traj_frag_molid, frame_idx, index)
	resname = get_resname(traj_frag_molid, frame_idx, index)
	resid = get_resid(traj_frag_molid, frame_idx, index)
	name = get_name(traj_frag_molid, frame_idx, index)

	atom_label = "%s:%s:%s:%s:%s" % (chain, resname, resid, name, index)
	return atom_label


def parse_contacts(contact_string):
	"""
	Parameters
	----------
	contact_string: string 
		Output from measure contacts function {indices} {indices}

	Returns
	-------
	contact_index_pairs: list of tuples
		List of index int pairs
	"""

	contact_index_pairs = []

	### Handle case where only one pair of atoms form contacts
	if("} {" not in contact_string):
		atom1_index, atom2_index = map(int, contact_string.split(" "))
		contact_index_pairs.append((atom1_index, atom2_index))
	else:
		contacts_list = contact_string.split("} {")
		atom1_list_str = contacts_list[0].strip("{}")
		atom2_list_str = contacts_list[1].strip("{}")
		if(atom1_list_str == "" or atom2_list_str == ""): return []

		atom1_list = map(int, atom1_list_str.split(" "))
		atom2_list = map(int, atom2_list_str.split(" "))

		for idx in range(len(atom1_list)):
			atom1_index = atom1_list[idx]
			atom2_index = atom2_list[idx]
			contact_index_pairs.append((atom1_index, atom2_index))

	return contact_index_pairs

### Geometry Tools

def get_coord(traj_frag_molid, frame_idx, atom_label):
	"""
	Get x, y, z coordinate of an atom specified by its label 

	Parameters
	----------
	traj_frag_molid: int 
		Denotes trajectory id in VMD
	frame_idx: int 
		Frame of simulation in trajectory fragment
	atom_label: string 
		Atom label (ie "A:GLU:323:OE2:55124")

	Returns
	-------
	coord: np.array[x, y, z]
	"""

	index = atom_label.split(":")[-1]
	evaltcl("set sel [atomselect %s \" index %s \" frame %s]" % (traj_frag_molid, index, frame_idx))
	x = float(evaltcl("$sel get x"))
	y = float(evaltcl("$sel get y"))
	z = float(evaltcl("$sel get z"))
	evaltcl("$sel delete")

	coord = np.array([x, y, z])
	return coord

def points_to_vector(point1, point2):
	"""
	Return vector from point1 to point2
	"""
	vector = point2 - point1 
	return vector

def calc_vector_length(vector):
	"""
	Compute length of vector
	"""
	vector_length = math.sqrt(np.dot(vector, vector))
	return vector_length

def calc_angle_between_vectors(vector1, vector2):
	"""
	Returns
	-------
	angle_between_vectors: float
		Degrees between two vectors
	"""
	radians_between_vectors = math.acos(np.dot(vector1, vector2)/(calc_vector_length(vector1) * calc_vector_length(vector2)))
	angle_between_vectors = math.degrees(radians_between_vectors)
	return angle_between_vectors

def calc_geom_distance(point1, point2):
	"""
	Compute distance between two points 

	Returns
	-------
	distance: float
	"""
	distance = np.linalg.norm(point1 - point2)
	return distance
	
def calc_geom_centroid(point1, point2, point3):
	"""
	Compute centroid between three points 

	Returns
	-------
	centroid: np.array[x, y, z]
	"""
	centroid = (point1 + point2 + point3)/3
	return centroid

def calc_geom_normal_vector(point1, point2, point3):
	"""
	Compute normal vector to the plane constructed by three points

	Returns
	-------
	normal_vector: np.array[x, y, z]

	"""

	v1 = point3 - point1
	v2 = point2 - point1
	normal_vector = np.cross(v1, v2)
	return normal_vector
