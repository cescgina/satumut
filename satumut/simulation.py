"""
This script is used to create and control the simulations
"""
import argparse
import shutil

from mutate_pdb import generate_mutations
from pele_files import create_20sbatch
from subprocess import call
from os.path import abspath
import os
import time
from analysis import consecutive_analysis
from helper import neighbourresidues, Log, find_log
from rs_analysis import consecutive_analysis_rs


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the mutant PDB and the corresponding running files")
    # main required arguments
    parser.add_argument("-i", "--input", required=True, help="Include PDB file's path")
    parser.add_argument("-p", "--position", required=False, nargs="+",
                        help="Include one or more chain IDs and positions -> Chain ID:position")
    parser.add_argument("-lc", "--ligchain", required=True, help="Include the chain ID of the ligand")
    parser.add_argument("-ln", "--ligname", required=True, help="The ligand residue name")
    parser.add_argument("-at", "--atoms", required=False, nargs="+",
                        help="Series of atoms of the residues to follow in this format -> chain ID:position:atom name")
    parser.add_argument("-cpm", "--cpus_per_mutant", required=False, default=25, type=int,
                        help="Include the number of cpus desired")
    parser.add_argument("-tcpus", "--total_cpus", required=False, type=int,
                        help="Include the number of cpus desired")
    parser.add_argument("-po", "--polarize_metals", required=False, action="store_true",
                        help="used if there are metals in the system")
    parser.add_argument("-fa", "--polarization_factor", required=False, type=int,
                        help="The number to divide the charges")
    parser.add_argument("-n", "--nord", required=False, action="store_true",
                        help="used if LSF is the utility managing the jobs")
    parser.add_argument("-m", "--multiple", required=False, action="store_true",
                        help="if you want to mutate 2 residue in the same pdb")
    parser.add_argument("-s", "--seed", required=False, default=12345, type=int,
                        help="Include the seed number to make the simulation reproducible")
    parser.add_argument("-d", "--dir", required=False,
                        help="The name of the folder for all the simulations")
    parser.add_argument("-pd", "--pdb_dir", required=False, default="pdb_files",
                        help="The name for the mutated pdb folder")
    parser.add_argument("-hy", "--hydrogen", required=False, action="store_false", help="leave it to default")
    parser.add_argument("-co", "--consec", required=False, action="store_true",
                        help="Consecutively mutate the PDB file for several rounds")
    parser.add_argument("-st", "--steps", required=False, type=int, default=1000,
                        help="The number of PELE steps")
    parser.add_argument("--dpi", required=False, default=800, type=int,
                        help="Set the quality of the plots")
    parser.add_argument("-tr", "--trajectory", required=False, default=10, type=int,
                        help="Set how many PDBs are extracted from the trajectories")
    parser.add_argument("--out", required=False, default="summary",
                        help="Name of the summary file created at the end of the analysis")
    parser.add_argument("--plot", required=False,
                        help="Path of the plots folder")
    parser.add_argument("-an", "--analyse", required=False, choices=("energy", "distance", "both"), default="distance",
                        help="The metric to measure the improvement of the system")
    parser.add_argument("--thres", required=False, default=0.0, type=float,
                        help="The threshold for the improvement which will affect what will be included in the summary")
    parser.add_argument("-sm", "--single_mutagenesis", required=False,
                        help="Specifiy the name of the residue that you want the "
                             "original residue to be mutated to. Both 3 letter "
                             "code and 1 letter code can be used. You can even specify the protonated states")
    parser.add_argument("-PR", "--plurizyme_at_and_res", required=False,
                        help="Specify the chain ID, residue number and the PDB atom name that"
                             "will set the list of the neighbouring residues for the"
                             "next round. Example: chain ID:position:atom name")
    parser.add_argument("-r", "--radius", required=False, default=5.0, type=float,
                        help="The radius around the selected atom to search for the other residues")
    parser.add_argument("-f", "--fixed_resids", required=False, default=(), nargs='+',
                        help="Specify the list of residues that you don't want"
                             "to have mutated (Must write the list of residue"
                             "numbers)")
    parser.add_argument("-re", "--restart", required=False, action="store_true",
                        help="to place the restart flag")
    parser.add_argument("-are", "--adaptive_restart", required=False, action="store_true",
                        help="to place the adaptive restart flag")
    parser.add_argument("-x", "--xtc", required=False, action="store_true",
                        help="Change the pdb format to xtc")
    parser.add_argument("-cd", "--catalytic_distance", required=False, default=3.5, type=float,
                        help="The distance considered to be catalytic")
    parser.add_argument("-tem", "--template", required=False, nargs="+",
                        help="Path to external forcefield templates")
    parser.add_argument("-sk", "--skip", required=False, nargs="+",
                        help="skip the processing of ligands by PlopRotTemp")
    parser.add_argument("-rot", "--rotamers", required=False, nargs="+",
                        help="Path to external rotamers templates")
    parser.add_argument("-e", "--equilibration", required=False, action="store_true",
                        help="Set equilibration")
    parser.add_argument("-l", "--log", required=False, action="store_true",
                        help="write logs")
    parser.add_argument("-da", "--dihedral_atoms", required=False, nargs="+",
                        help="The 4 atom necessary to calculate the dihedrals in format chain id:res number:atom name")
    parser.add_argument("-im", "--improve", required=False, choices=("R", "S"), default="R",
                        help="The enantiomer that should improve")
    parser.add_argument("-tu", "--turn", required=False, type=int,
                        help="the round of plurizyme generation, not needed for the 1st round")
    parser.add_argument("-en", "--energy_threshold", required=False, type=int, help="The number of steps to analyse")
    parser.add_argument("--QM", required=False, help="The path to the QM charges")
    parser.add_argument("-br","--box_radius", required=False, type=int, help="Radius of the exploration box")
    parser.add_argument("-mut", "--mutation", required=False, nargs="+",
                        choices=('ALA', 'CYS', 'GLU', 'ASP', 'GLY', 'PHE', 'ILE', 'HIS', 'LYS', 'MET', 'LEU', 'ASN',
                                 'GLN', 'PRO', 'SER', 'ARG', 'THR', 'TRP', 'VAL', 'TYR'),
                        help="The aminoacid in 3 letter code")
    parser.add_argument("-cst", "--conservative", required=False, choices=(1, 2), default=None, type=int,
                        help="How conservative should the mutations be, choises are 1 and 2")
    args = parser.parse_args()

    return [args.input, args.position, args.ligchain, args.ligname, args.atoms, args.cpus_per_mutant,
            args.polarize_metals, args.multiple, args.seed, args.dir, args.nord, args.pdb_dir, args.hydrogen,
            args.consec, args.steps, args.dpi, args.trajectory, args.out, args.plot, args.analyse, args.thres,
            args.single_mutagenesis, args.plurizyme_at_and_res, args.radius, args.fixed_resids,
            args.polarization_factor, args.total_cpus, args.restart, args.xtc, args.catalytic_distance, args.template,
            args.skip, args.rotamers, args.equilibration, args.log, args.improve,
            args.turn, args.energy_threshold, args.QM, args.dihedral_atoms, args.adaptive_restart, args.box_radius,
            args.mutation, args.conservative]


class SimulationRunner:
    """
    A class that configures and runs simulations
    """

    def __init__(self, input_, dir_=None, turn=None):
        """
        Initialize the Simulation Runner class

        Parameters
        ___________
        input_: str
            The path to the PDB file
        dir_: str, optional
            The name of the directory for the simulations to run and the outputs to be stored
        turn: int, optional
            The round of the plurizyme generation
        """

        self.input = input_
        self.proc = None
        self.dir = dir_
        self.log = Log("simulation_time")
        self.turn = turn

    def side_function(self):
        """
        Change the working directory to store all the simulations in one place

        Returns
        _______
        input_: str
            The new path of the input
        """
        self.input = abspath(self.input)
        if not self.dir:
            base = self.input.replace(".pdb", "")
        else:
            base = self.dir.replace(".pdb", "").replace("_mut", "")
        if not os.path.exists("{}_mut".format(base)):
            os.makedirs("{}_mut".format(base))
        if self.turn:
            shutil.copy(self.input, "{}_mut".format(base))
        os.chdir("{}_mut".format(base))

        return self.input

    def pele_folders(self):
        """
        Creates a file with the names of the different folders where the pele simulations are contained
        """
        os.chdir("../")
        if not self.dir:
            base = self.input.replace(".pdb", "")
        else:
            base = self.dir.replace(".pdb", "").replace("_mut", "")

        folder, original = find_log("{}_mut".format(base))
        return folder, original

    def submit(self, yaml):
        """
        Tries to parallelize the call to the pele_platform

        Parameters
        __________
        yaml_list: list[path]
            A list of paths to the yaml files
        """
        command = ["python", "-m", "pele_platform.main", "{}".format(yaml)]
        start = time.time()
        return_code = call(command, close_fds=False)
        end = time.time()
        # creating a log
        self.log.info("It took {} min to run the simulation with return code {}".format((end - start), return_code))


def saturated_simulation(input_, ligchain, ligname, atoms, position=None, cpus=25, dir_=None, hydrogen=True,
                         multiple=False, pdb_dir="pdb_files", consec=False, cu=False, seed=12345,
                         nord=False, steps=1000, dpi=800, traj=10, output="summary",
                         plot_dir=None, opt="distance", thres=-0.1, factor=None, plurizyme_at_and_res=None,
                         radius=5.0, fixed_resids=(), total_cpus=None, restart=False, cata_dist=3.5, xtc=False,
                         template=None, skip=None, rotamers=None, equilibration=True, log=False, improve="R",
                         energy_threshold=None, QM=None, dihedral=None, adaptive_restart=False, box_radius=None,
                         mut=None, conservative=None):
    """
    A function that uses the SimulationRunner class to run saturated mutagenesis simulations

    Parameters
    __________
    input_: str
        The wild type PDB file path
    ligchain: str
        the chain ID where the ligand is located
    ligname: str
        the residue name of the ligand in the PDB
    atoms: list[str]
            list of atom of the residue to follow, in this format --> chain ID:position:atom name
    position: list[str]
        [chain ID:position] of the residue, for example [A:139,..]
    cpus: int, optional
        how many cpus do you want to use
    dir_: str, optional
        Name of the folder ofr the simulations
    hydrogens: bool, optional
        Leave it true since it removes hydrogens (mostly unnecessary) but creates an error for CYS
    multiple: bool, optional
        Specify if to mutate 2 positions at the same pdb
    pdb_dir: str, optional
        The name of the folder where the mutated PDB files will be stored
    consec: bool, optional
        Consecutively mutate the PDB file for several rounds
    cu: bool, optional
        Set it to true if there are coppers in the system
    seed: int, optional
        A seed number to make the simulations reproducible
    nord: bool, optional
        True if the system is managed by LSF
    steps: int, optional
        The number of PELE steps
    dpi : int, optional
       The quality of the plots
    traj : int, optional
       how many top pdbs are extracted from the trajectories
    output : str, optional
       name of the output file for the pdfs
    plot_dir : str
       Name for the results folder
    opt : str, optional
       choose if to analyse distance, energy or both
    thres : float, optional
       The threshold for the mutations to be included in the pdf
    factor: int, optional
        The number to divide the metal charges
    plurizyme_at_and_res: str
        Chain_ID:position:atom_name, which will be the center around the search for neighbours
    radius: float, optional
        The radius for the neighbours search
    fixed_resids. list[position_num]
        A list of residues positions to avoid mutating
    total_cpus: int, optional
        Set the total number of cpus, it should be a multiple of the number of cpus
    restart: bool, optional
        True if the simulation has already run once
    cata_dist: float, optional
        The catalytic distance
    xtc: bool, optional
        Set to True if you want to change the pdb format to xtc
    template: str, optional
        Path to the external forcefield templates
    skip: str, optional
        Skip the processing of ligands by PlopRotTemp
    rotamers: str: optional
        Path to the external rotamers
    equilibration: bool, optional
        True to set equilibration before PELE
    log: bool, optional
        True to recover pele running logs
    improve: str
        The enantiomer to improve
    energy_thres: int, optional
        The binding energy to consider for catalytic poses
    QM: str, optional
        The path to the QM charges
    dihedral: list[str]
        The 4 atoms that form the dihedral in format chain ID:position:atom name
    adaptive_restart: bool, optional
        Placing the adaptive restart flag
    box_radius: int, optional
        The radius of the exploration box
    mut: list[str]
        The list of mutations to perform
    """
    simulation = SimulationRunner(input_, dir_)
    input_ = simulation.side_function()
    if not position and plurizyme_at_and_res:
        position = neighbourresidues(input_, plurizyme_at_and_res, radius, fixed_resids)
    if not restart and not adaptive_restart:
        pdb_names = generate_mutations(input_, position, hydrogens=hydrogen, multiple=multiple, pdb_dir=pdb_dir,
                                       consec=consec, mut=mut, conservative=conservative)
        yaml = create_20sbatch(pdb_names, ligchain, ligname, atoms, cpus=cpus, initial=input_, cu=cu, seed=seed,
                               nord=nord, steps=steps, factor=factor, total_cpus=total_cpus, xtc=xtc, template=template,
                               skip=skip, rotamers=rotamers, equilibration=equilibration, log=log, consec=consec, QM=QM,
                               box_radius=box_radius)
    elif adaptive_restart:
        yaml = "yaml_files/simulation.yaml"
        with open(yaml, "r") as yml:
            lines = yml.readlines()
            if "adaptive_restart: true\n" not in lines:
                with open(yaml, "a") as yam:
                    yam.write("adaptive_restart: true\n")
            if "restart: true\n" in lines:
                with open(yaml, "w") as yam:
                    lines.remove("restart: true\n")
                    yam.writelines(lines)
    else:
        yaml = "yaml_files/simulation.yaml"
        with open(yaml, "r") as yml:
            if "restart: true\n" not in yml.readlines():
                with open(yaml, "a") as yam:
                    yam.write("restart: true\n")

    simulation.submit(yaml)
    dirname, original = simulation.pele_folders()
    if dir_ and not plot_dir:
        plot_dir = dir_
    consecutive_analysis(dirname, original, dpi, traj, output, plot_dir, opt, cpus, thres, cata_dist, xtc,
                         energy_thres=energy_threshold)
    if dihedral:
        consecutive_analysis_rs(dirname, dihedral, input_, original, dpi, traj, output, plot_dir, opt, cpus,
                                thres, cata_dist, xtc, improve, energy=energy_threshold)


def plurizyme_simulation(input_, ligchain, ligname, atoms, single_mutagenesis, plurizyme_at_and_res,
                         radius=5.0, fixed_resids=(), cpus=30, dir_=None, hydrogen=True,
                         pdb_dir="pdb_files", cu=False, seed=12345, nord=False, steps=300, factor=None,
                         total_cpus=None, xtc=False, template=None, skip=None, rotamers=None, equilibration=True,
                         log=False, turn=None, box_radius=None):
    """
    Run the simulations for the plurizyme's projct which is based on single mutations

    Parameters
    __________
    input_: str
        The wild type PDB file path
    ligchain: str
        the chain ID where the ligand is located
    ligname: str
        the residue name of the ligand in the PDB
    atoms: list[str]
        list of atom of the residue to follow, in this format --> chain ID:position:atom name
    single_mutagenesis: str
        The new residue to mutate the positions to, in 3 letter or 1 letter code
    plurizyme_at_and_res: str
        Chain_ID:position:atom_name, which will be the center around the search for neighbours
    radius: float, optional
        The radius for the neighbours search
    fixed_resids. list[position_num]
        A list of residues positions to avoid mutating
    cpus: int, optional
        how many cpus do you want to use
    dir_: str, optional
        Name of the folder ofr the simulations
    hydrogens: bool, optional
        Leave it true since it removes hydrogens (mostly unnecessary) but creates an error for CYS
    pdb_dir: str, optional
        The name of the folder where the mutated PDB files will be stored
    cu: bool, optional
        Set it to true if there are metals in the system
    seed: int, optional
        A seed number to make the simulations reproducible
    nord: bool, optional
        True if the system is managed by LSF
    steps: int, optional
        The number of PELE steps
    factor: int, optional
        The number to divide the metal charges
    total_cpus: int, optional
        Set the total number of cpus, it should be a multiple of the number of cpus
    xtc: bool, optional
        Set to True if you want to change the pdb format to xtc
    template: str, optional
        Path to the external forcefield templates
    skip: str, optional
        Skip the processing of ligands by PlopRotTemp
    rotamers: str: optional
        Path to the external rotamers
    equilibration: bool, optional
        True to set equilibration before PELE
    log: bool, optional
        True to write log files about the simulations
    turn: int, optional
        The round of plurizymer generation
    box_radius: int, optional
        The radius of the exploration box
    """
    simulation = SimulationRunner(input_, dir_)
    input_ = simulation.side_function()
    # Using the neighbours search to obtain a list of positions to mutate
    position = neighbourresidues(input_, plurizyme_at_and_res, radius, fixed_resids)
    pdb_names = generate_mutations(input_, position, hydrogen, pdb_dir=pdb_dir,
                                   single=single_mutagenesis, turn=turn)
    yaml = create_20sbatch(pdb_names, ligchain, ligname, atoms, cpus=cpus, initial=input_, cu=cu, seed=seed, nord=nord,
                           steps=steps, single=single_mutagenesis, factor=factor, total_cpus=total_cpus, xtc=xtc,
                           template=template, skip=skip, rotamers=rotamers, equilibration=equilibration, log=log,
                           input_pdb=input_, box_radius=box_radius)
    simulation.submit(yaml)


def main():
    input_, position, ligchain, ligname, atoms, cpus, cu, multiple, seed, dir_, nord, pdb_dir, \
    hydrogen, consec, steps, dpi, traj, out, plot_dir, analyze, thres, single_mutagenesis, \
    plurizyme_at_and_res, radius, fixed_resids, factor, total_cpus, restart, xtc, cata_dist, template, \
    skip, rotamers, equilibration, log, improve, turn, energy_thres, QM, dihedral, adaptive_restart,\
    box_radius, mut, conservative = parse_args()

    if plurizyme_at_and_res and single_mutagenesis:
        # if the other 2 flags are present perform plurizyme simulations
        plurizyme_simulation(input_, ligchain, ligname, atoms, single_mutagenesis, plurizyme_at_and_res,
                             radius, fixed_resids, cpus, dir_, hydrogen, pdb_dir, cu, seed, nord, steps,
                             factor, total_cpus, xtc, template, skip, rotamers, equilibration, log, turn, box_radius)
    else:
        # Else, perform saturated mutagenesis
        saturated_simulation(input_, ligchain, ligname, atoms, position, cpus, dir_, hydrogen,
                             multiple, pdb_dir, consec, cu, seed, nord, steps, dpi, traj, out,
                             plot_dir, analyze, thres, factor, plurizyme_at_and_res, radius, fixed_resids,
                             total_cpus, restart, cata_dist, xtc, template, skip, rotamers, equilibration, log,
                              improve, energy_thres, QM, dihedral, adaptive_restart, box_radius, mut)


if __name__ == "__main__":
    # Run this if this file is executed from command line but not if is imported as API
    main()
