from pypeflow.common import * 
from pypeflow.data import PypeLocalFile, makePypeLocalFile, fn
from pypeflow.task import PypeTask, PypeThreadTaskBase, PypeTaskBase
from pypeflow.controller import PypeWorkflow, PypeMPWorkflow, PypeThreadWorkflow
from falcon_kit.FastaReader import FastaReader
from falcon_kit.fc_asm_graph import AsmGraph
import glob
import sys
import subprocess as sp
import shlex
import os

rawread_dir = os.path.abspath( "./0-rawreads" )
pread_dir = os.path.abspath( "./1-preads_ovl" )
asm_dir = os.path.abspath( "./2-asm-falcon" )

PypeMPWorkflow.setNumThreadAllowed(12, 12)
wf = PypeMPWorkflow()

rawread_db = makePypeLocalFile( os.path.join( rawread_dir, "raw_reads.db" ) )
rawread_id_file = makePypeLocalFile( os.path.join( rawread_dir, "raw_reads_ids" ) )

@PypeTask( inputs = {"rawread_db": rawread_db}, 
           outputs =  {"rawread_id_file": rawread_id_file},
           TaskType = PypeThreadTaskBase,
           URL = "task://localhost/dump_rawread_ids" )
def dump_rawread_ids(self):
    rawread_db = fn( self.rawread_db )
    rawread_id_file = fn( self.rawread_id_file )
    os.system("DBshow -n %s | tr -d '>' | awk '{print $1}' > %s" % (rawread_db, rawread_id_file) )

wf.addTask( dump_rawread_ids )

pread_db = makePypeLocalFile( os.path.join( pread_dir, "preads.db" ) )
pread_id_file = makePypeLocalFile( os.path.join( pread_dir, "preads_ids" ) )

@PypeTask( inputs = {"pread_db": pread_db}, 
           outputs =  {"pread_id_file": pread_id_file},
           TaskType = PypeThreadTaskBase,
           URL = "task://localhost/dump_pread_ids" )
def dump_pread_ids(self):
    pread_db = fn( self.pread_db )
    pread_id_file = fn( self.pread_id_file )
    os.system("DBshow -n %s | tr -d '>' | awk '{print $1}' > %s" % (pread_db, pread_id_file) )

wf.addTask( dump_pread_ids )

all_raw_las_files = {}
for las_fn in glob.glob( os.path.join( rawread_dir, "raw_reads.*.las") ):
    idx = las_fn.split("/")[-1] # well, we will use regex someday to parse to get the number
    idx = int(idx.split(".")[1]) 
    las_file = makePypeLocalFile( las_fn )
    all_raw_las_files["r_las_%s" % idx] = las_file 

all_pread_las_files = {}
for las_fn in glob.glob( os.path.join( pread_dir, "preads.*.las") ):
    idx = las_fn.split("/")[-1] # well, we will use regex someday to parse to get the number
    idx = int(idx.split(".")[1]) 
    las_file = makePypeLocalFile( las_fn )
    all_pread_las_files["p_las_%s" % idx] = las_file 

wf.refreshTargets() # block

# need new workflow
PypeMPWorkflow.setNumThreadAllowed(1, 1)
wf = PypeMPWorkflow()

sg_edges_list = makePypeLocalFile( os.path.join(asm_dir, "sg_edges_list") )
utg_data = makePypeLocalFile( os.path.join(asm_dir, "utg_data") )
ctg_paths = makePypeLocalFile( os.path.join(asm_dir, "ctg_paths") )

inputs = { "rawread_id_file": rawread_id_file,
           "pread_id_file": pread_id_file,
           "sg_edges_list": sg_edges_list,
           "utg_data": utg_data,
           "ctg_paths": ctg_paths }

contig_to_read_map = makePypeLocalFile( os.path.join(asm_dir, "contig_to_read_map_2") )

@PypeTask( inputs = inputs, 
           outputs = {"contig_to_read_map": contig_to_read_map}, 
           TaskType = PypeThreadTaskBase, 
           URL = "task://localhost/get_ctg_read_map" )
def gen_ctg_to_read_map(self):
    rawread_id_file = fn( self.rawread_id_file )
    pread_id_file = fn( self.pread_id_file )
    contig_to_read_map = fn( self.contig_to_read_map )
    
    pread_did_to_rid = open(pread_id_file).read().split("\n")
    rid_to_oid = open(rawread_id_file).read().split("\n")

    asm_G = AsmGraph(fn(self.sg_edges_list), 
                     fn(self.utg_data),
                     fn(self.ctg_paths) )

    pread_to_contigs = {}

    with open(contig_to_read_map, "w") as f:
        for ctg in asm_G.ctg_data:
            rid_set = set()
            ctg_to_preads = {}
            if ctg[-1] == "R":
                continue
            ctg_g = asm_G.get_sg_for_ctg(ctg)
            for n in ctg_g.nodes():
                frg0 = int(n.split(":")[0])

                rid = pread_did_to_rid[frg0].split("/")[1]
                rid = int(int(rid)/10)
                oid = rid_to_oid[rid]
                k = (frg0, rid, oid)
                pread_to_contigs.setdefault( k, set() )
                pread_to_contigs[ k ].add( ctg )


        for k in pread_to_contigs:
            frg0, rid, oid = k
            for ctg in list(pread_to_contigs[ k ]):
                print >>f, "%09d %09d %s %s" % (frg0, rid, oid, ctg)

wf.addTask( gen_ctg_to_read_map )
wf.refreshTargets()


def dump_rawread_to_ctg(self):
    rawread_db = fn( self.rawread_db )
    rawread_id_file = fn( self.rawread_id_file )
    #pread_id_file = fn( self.pread_id_file )
    las_file = fn( self.las_file )
    rawread_to_contig_file = fn( self.rawread_to_contig_file )
    contig_to_read_map = fn( self.contig_to_read_map )
    rid_to_oid = open(rawread_id_file).read().split("\n")
    #pread_did_to_rid = open(pread_id_file).read().split("\n")


    ovlp_data = []
    ovlp_count = 0
    longest_ovlp = 0
    a_id = None
    rid_to_contigs = {}
    
    with open(contig_to_read_map) as f:
        for row in f:
            row = row.strip().split()
            frg0, rid, oid, ctg = row
            rid = int(rid)
            rid_to_contigs.setdefault( rid, (oid, set() ) )
            rid_to_contigs[ rid ][1].add( ctg )

    with open(rawread_to_contig_file, "w") as f:
        ovlp_data = {}
        cur_read_id = None
        for row in sp.check_output(shlex.split("LA4Falcon -mo %s %s " % (rawread_db, las_file)) ).splitlines():

            row = row.strip().split()
            t_id = int(row[1])
            q_id = int(row[0])
            if q_id != cur_read_id:
                if cur_read_id == None:
                    cur_read_id = q_id
                else:
                    if len(ovlp_data) == 0:
                        o_id = rid_to_oid[ cur_read_id ]
                        print >>f, "%09d %s %s %d %d %d %d" % (cur_read_id, o_id, "NA", 0, 0, 0, 0)
                    else:
                        ovlp_v = ovlp_data.values()
                        ovlp_v.sort()
                        rank = 0
                        for score, count, q_id_, o_id, ctg, in_ctg in ovlp_v:
                            print >> f, "%09d %s %s %d %d %d %d" % (q_id_, o_id, ctg, count, rank, score, in_ctg)
                            rank += 1
                    ovlp_data = {}
                    cur_read_id = q_id

            if q_id in rid_to_contigs and len(ovlp_data) == 0: #if the query is in some contig....
                t_o_id, ctgs = rid_to_contigs[ q_id ]
                o_id = rid_to_oid[ q_id ]
                for ctg in list(ctgs):
                    ovlp_data.setdefault(ctg, [0, 0, q_id, o_id, ctg, 1])
                    ovlp_data[ctg][0] = -int(row[7]) 
                    ovlp_data[ctg][1] += 1

            if t_id not in rid_to_contigs:
                continue

            t_o_id, ctgs = rid_to_contigs[ t_id ]
            o_id = rid_to_oid[ q_id ]
            
            for ctg in list(ctgs):
                ovlp_data.setdefault(ctg, [0, 0, q_id, o_id, ctg, 0])
                ovlp_data[ctg][0] += int(row[2])
                ovlp_data[ctg][1] += 1

        if len(ovlp_data) != 0:
            ovlp_v = ovlp_data.values()
            ovlp_v.sort()
            rank = 0
            for score, count, q_id_, o_id, ctg, in_ctg in ovlp_v:
                print >> f, "%09d %s %s %d %d %d %d" % (q_id_, o_id, ctg, count, rank, score, in_ctg)
                rank += 1

def dump_pread_to_ctg(self):
    pread_db = fn( self.pread_db )
    rawread_id_file = fn( self.rawread_id_file )
    pread_id_file = fn( self.pread_id_file )
    contig_to_read_map = fn( self.contig_to_read_map )
    las_file = fn( self.las_file )
    pread_to_contig_file = fn( self.pread_to_contig_file )
    contig_to_read_map = fn( self.contig_to_read_map )
    
    pid_to_rid = open(pread_id_file).read().split("\n")
    rid_to_oid = open(rawread_id_file).read().split("\n")


    ovlp_data = []
    ovlp_count = 0
    longest_ovlp = 0
    a_id = None
    pid_to_contigs = {}
    
    with open(contig_to_read_map) as f:
        for row in f:
            row = row.strip().split()
            pid, rid, oid, ctg = row
            pid = int(pid)
            pid_to_contigs.setdefault( pid, (oid, set() ) )
            pid_to_contigs[ pid ][1].add( ctg )

    with open(pread_to_contig_file, "w") as f:
        ovlp_data = {}
        cur_read_id = None
        for row in sp.check_output(shlex.split("LA4Falcon -mo %s %s " % (pread_db, las_file)) ).splitlines():

            row = row.strip().split()
            t_id = int(row[1])
            q_id = int(row[0])
            if q_id != cur_read_id:
                if cur_read_id == None:
                    cur_read_id = q_id
                else:
                    if len(ovlp_data) == 0:
                        rid = pid_to_rid[cur_read_id].split("/")[1]
                        rid = int(int(rid)/10)
                        o_id = rid_to_oid[ rid ]
                        print >>f, "%09d %s %s %d %d %d %d" % (cur_read_id, o_id, "NA", 0, 0, 0, 0)
                    else:
                        ovlp_v = ovlp_data.values()
                        ovlp_v.sort()
                        rank = 0
                        for score, count, q_id_, o_id, ctg, in_ctg in ovlp_v:
                            print >> f, "%09d %s %s %d %d %d %d" % (q_id_, o_id, ctg, count, rank, score, in_ctg)
                            rank += 1
                    ovlp_data = {}
                    cur_read_id = q_id

            if q_id in pid_to_contigs and len(ovlp_data) == 0: #if the query is in some contig....
                t_o_id, ctgs = pid_to_contigs[ q_id ]
                rid = pid_to_rid[q_id].split("/")[1]
                rid = int(int(rid)/10)
                o_id = rid_to_oid[ rid ]
                for ctg in list(ctgs):
                    ovlp_data.setdefault(ctg, [0, 0, q_id, o_id, ctg, 1])
                    ovlp_data[ctg][0] = -int(row[7]) 
                    ovlp_data[ctg][1] += 1

            if t_id not in pid_to_contigs:
                continue

            t_o_id, ctgs = pid_to_contigs[ t_id ]
            rid = pid_to_rid[q_id].split("/")[1]
            rid = int(int(rid)/10)
            o_id = rid_to_oid[ rid ]
            
            for ctg in list(ctgs):
                ovlp_data.setdefault(ctg, [0, 0, q_id, o_id, ctg, 0])
                ovlp_data[ctg][0] += int(row[2])
                ovlp_data[ctg][1] += 1

        if len(ovlp_data) != 0:
            ovlp_v = ovlp_data.values()
            ovlp_v.sort()
            rank = 0
            for score, count, q_id_, o_id, ctg, in_ctg in ovlp_v:
                print >> f, "%09d %s %s %d %d %d %d" % (q_id_, o_id, ctg, count, rank, score, in_ctg)
                rank += 1

for las_key, las_file in all_raw_las_files.items():
    las_fn = fn(las_file)
    idx = las_fn.split("/")[-1] # well, we will use regex someday to parse to get the number
    idx = int(idx.split(".")[1]) 
    rawread_to_contig_file = makePypeLocalFile(os.path.join(asm_dir, "raw_read_to_contigs.%s" % idx))
    make_dump_rawread_to_ctg = PypeTask( inputs = { "las_file": las_file, 
                                                    "rawread_db": rawread_db, 
                                                    "contig_to_read_map": contig_to_read_map, 
                                                    "rawread_id_file": rawread_id_file,
                                                    "pread_id_file": pread_id_file},
                                      outputs = { "rawread_to_contig_file": rawread_to_contig_file },
                                      TaskType = PypeThreadTaskBase,
                                      URL = "task://localhost/r_read_to_contigs.%s" % idx )
    dump_rawread_to_ctg_task = make_dump_rawread_to_ctg(dump_rawread_to_ctg)                           
    wf.addTask( dump_rawread_to_ctg_task )

for las_key, las_file in all_pread_las_files.items():
    las_fn = fn(las_file)
    idx = las_fn.split("/")[-1] # well, we will use regex someday to parse to get the number
    idx = int(idx.split(".")[1]) 
    pread_to_contig_file = makePypeLocalFile(os.path.join(asm_dir, "pread_to_contigs.%s" % idx))
    make_dump_pread_to_ctg = PypeTask( inputs = { "las_file": las_file, 
                                                  "pread_db": pread_db, 
                                                  "contig_to_read_map": contig_to_read_map, 
                                                  "rawread_id_file": rawread_id_file,
                                                  "pread_id_file": pread_id_file},
                                      outputs = { "pread_to_contig_file": pread_to_contig_file },
                                      TaskType = PypeThreadTaskBase,
                                      URL = "task://localhost/pread_to_contigs.%s" % idx )
    dump_pread_to_ctg_task = make_dump_pread_to_ctg(dump_pread_to_ctg)                           
    wf.addTask( dump_pread_to_ctg_task )

wf.refreshTargets() # block