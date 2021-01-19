import glob
import json
import os
import subprocess
from pathlib import Path

import pyTigerDriver as tg
from flask import Flask
from flask import request


############# DEBUG T/F ########################
DEBUG = True
if DEBUG:
    import time


############# LOCAL/REMOTE ####################
MODE = "L"
############# CONF TigerGraph Box #############
TG_Host = "127.0.0.1"
TG_User = "tigergraph"
TG_Pass = "tigergraph"
TG_Vers = "3.0.5"
################################################

############## KAFKA Related ###################
tigergraph_log_root = ""  # default check the .tg.cf in home folder logroot
home_folder = str(Path.home()) # /home/tigergraph
if os.path.exists(home_folder+"/.tg.cf"):
    # read log root from .tg.cf
    f = open(home_folder+"/.tg.cfg")
    conf = json.load(f)
    try:
        tigergraph_log_root = conf["System"]["LogRoot"]
        if DEBUG:
            print("The log root ( from tg cfg ) is :{}".format(tigergraph_log_root))
            time.sleep(2)
    except Exception as e:
        if DEBUG:
            print("Error getting CFG :{}".format(e))
            time.sleep(2)

if tigergraph_log_root == "":
    tigergraph_log_root = "/opt/tigergraph/log"
progress_files_path =  tigergraph_log_root + "/restpp/restpp_tg_app_kafkaldr_logs/"
progress_files_exte = "*.progress"
#################################################


# Flask Endpoint 5000 <-> 9000 => nginx conf 
app = Flask(__name__)

# tgCl : TigerGraph Python Client
tgCl = tg.Client(server_ip=TG_Host,username=TG_User,password=TG_Pass,version=TG_Vers)


def file_lister(graph_list):
    files_list = {}
    for graph in graph_list:
        temp = []
        try:
            os.chdir(progress_files_path + graph + "/")
            for file in glob.glob(progress_files_exte):
                temp.append(file)
        except:
            print("This graph doesn't have Kafka progress Logs!")
        files_list[graph] = temp
    return files_list


def Files_Progress_Getter(graph_list,files):
    content_files = {}
    for graph in files.keys():
        temp = []
        for file in files[graph]:
            f = open(file)
            # reading the
            f = open(file, "rb")
            js = f.readline()
            Read_file = json.loads(js)
            temp.append(Read_file)
            f.close()

        content_files[graph] = temp
    return content_files


def GSQL_Progress_Getter(graph_list):
    progress = {}
    for graph in graph_list:
        print("Started !!")
        if MODE == "R":
            # PROCESS GSQL Through Python Driver - Todo : Check the output format
            from io import StringIO
            import sys
            result = StringIO()
            old_stdout = sys.stdout
            sys.stdout = result
            tgCl.Gsql.query("USE GRAPH {}".format(graph))
            res = tgCl.Gsql.query("show loading status all", out=True)
            sys.stdout = old_stdout
            progress[graph] = res
        elif MODE == "L":
            # PROCESS GSQL Directly
            # Example ::
            # tigergraph@box:~$ gsql USE GRAPH FraudGraph show loading status all
            p = subprocess.Popen('timeout 1 gsql USE GRAPH {} show loading status all'.format(graph).split(), shell=False,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)

            stdout, stderr = p.communicate()

            list_res = stdout.decode("utf-8").replace("-","").replace("+","").split("\n")
            print(list_res)
            progress[graph] = list_res
    return progress

@app.route('/kafka/', methods = ['GET', 'POST', 'DELETE'])
def kafka():
    if request.method == 'GET':
        gsql_result = {}

        # Getting the catalog
        Schema = tgCl.Gsql.catalog()
        # Getting the Graphs
        graph_list = Schema["graphs"]
        # Listing all the *.progress files
        files = file_lister(graph_list)
        # parsing the *.progress files
        File_results = Files_Progress_Getter(graph_list,files)

        # getting the gsql load status
        gsql_result = GSQL_Progress_Getter(graph_list)

        # Formatting
        # Result combine GSQL + *.progress

        return {
            "overall": gsql_result ,
            "details" : File_results
        }
    if request.method == 'POST':
        data = request.form 
        return data
    if request.method == 'DELETE':
        return "DELETE"
    else:
        return "405"


app.run(debug=True)