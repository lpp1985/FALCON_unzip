# FALCON_unzip

FALCON-Unzip contains the modules that works with FALCON ( https://github.com/PacificBiosciences/FALCON,  https://github.com/PacificBiosciences/FALCON-integrate) for full diploid assembly (representing haplotype specific contigs as "haplotigs" as assembly output). A manuscript is deposited in BioRxiv (http://biorxiv.org/content/early/2016/06/03/056887) for our evalution and showing the application of the algorithms and the software on multiple diploid genomes. You can find more information here: https://github.com/PacificBiosciences/FALCON/wiki/FALCON-FALCON-Unzip-%22For-Phased-Diploid-Genome-Assembly-with-Single-Molecule-Real-Time-Sequencing%22

**Note that FALCON-Unzip is under continuous development work internally. We will be keeping improving the code and algorithm for more efficient computation and improvement on the accuracy of assembly results. We are in the process refactoring the code soon for furture maintainance purposes.** 

**Currently, the code here is in its infant stage. If you are not familiar with working from source code "as-is" and making necessary modifications for your computational environment, you might want to wait a bit for packaging and intergration to reach certain maturity before trying it out. In the meantime, you might be able to contact PacBio representives to express your interests on getting diploid assembly with PacBio data in a convenient way.** 

**If you try to run and run into problems for installation and set-ups, you could submit issues, however, due to limited bandwidth, we might not be able to address questions unless the questions are directly related to the development path. We need the time and resource for development work beyond prototype than addressing tentative issues.**

See `example/unzip.sh` for end-to-end work. You do need to have run it in a working diretory with Falcon output and all original Daligner overlap data.
For generating quiver consensus, you will need PacBio raw sequence data with "signal pulse" information in `bam` format. You can config the bam-file input using a configuration sent to `fc_quvier.py`.

To use this code to generate draft haplotig assembly, it need Falcon (please install the latest code from https://github.com/PacificBiosciences/FALCON-integrate). It also use `nucmer` for aligning contigs to find redundant contigs. You should have it in your execution path.

For "quivering" the draft haplotigs, you will need PacBio SMRTanalysis Software suit. More specifically, you need the following executables:
```
samtools
pbalign
makePbi
variantCaller
```

You will also need extra a python package `pysam`.

-
J.C. Nov, 2016

