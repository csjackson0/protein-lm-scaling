import torch
import os
from protein_lm.modeling.getters.model import get_model
from protein_lm.modeling.getters.tokenizer import get_tokenizer
from protein_lm.tokenizer.tokenizer import EsmTokenizer
from protein_lm.evaluation.scripts.utils import *
import yaml

import sys
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd
torch.set_grad_enabled(False)

import esm

def predict_contacts_jacobian(modelname,model,x,ln,device):
	with torch.no_grad():
		#model.logits returns batch_size x seq_len x vocab_size tensor
		if modelname=="APT":
			f = lambda x: model(x.to(device)).logits[...,1:(ln+1),3:23].cpu().numpy()
		elif modelname=="ESM":
			f = lambda x: model(x)["logits"][...,1:(ln+1),4:24].cpu().numpy()	
		fx = f(x.to(device))[0]
		x = torch.tile(x,[20,1]).to(device)
		fx_h = np.zeros((ln,20,ln,20))
		for n in range(ln): # for each position
			x_h = torch.clone(x)
			if modelname=="APT":
				x_h[:,n] = torch.arange(3,23) # mutate to all 20 aa
			elif modelname=="ESM":
				x_h[:,n+1] = torch.arange(4,24)
			fx_h[n] = f(x_h)
		jac=fx-fx_h
	# center & symmetrize
	for i in range(4): jac -= jac.mean(i,keepdims=True)
	jac = (jac + jac.transpose(2,3,0,1))/2
	return get_contacts(jac)

def predict_contacts_regression(model,inputs,tokenizer,device):
	with torch.no_grad():
		token_ids = tokenizer.encode(inputs[1],add_special_tokens=True)
		token_ids = torch.tensor(token_ids, dtype=torch.long)
		token_ids = token_ids.to(device)  # Move token_ids to the same device as the model
		token_ids=token_ids.unsqueeze(0)
	return model.predict_contacts(token_ids)[0].cpu()


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--input", type=str,help="dir containing data for contact prediction")
	parser.add_argument("--configfile",default="protein_lm/configs/train/toy_localcsv.yaml",type=str, help="path to config file")
	parser.add_argument("--model", help="APT or ESM")
	parser.add_argument("--tokenizer", type=str,help="EsmTokenizer or AptTokenizer")
	parser.add_argument("--type",type=str,help="jacobian or regression")
	args = parser.parse_args()
	device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
	
	with open(args.configfile, "r") as cf:
	    config_dict = yaml.safe_load(cf)
	    print(config_dict)

	if args.model=="APT":
		model = get_model(
	        config_dict=config_dict["model"],
	    )
	elif args.model=="ESM":
		model, _ = esm.pretrained.esm2_t33_650M_UR50D()

	if args.tokenizer=="AptTokenizer":
		tokenizer = get_tokenizer(config_dict=config_dict["tokenizer"])
	elif args.tokenizer=="EsmTokenizer":
		tokenizer = EsmTokenizer()
	
	model.to(device)
	
	if args.type=="jacobian":
		for f in os.listdir(args.input):

			data=args.input+f
			if data.endswith(".a3m"):
				headers, seqs = parse_fasta(data, a3m = True)
				seq=seqs[0]
				x,ln = tokenizer.batch_encode([seq],add_special_tokens=True),len(seq)
				x=torch.tensor(x)
				contacts=predict_contacts_jacobian(args.model,model,x,ln,device)

				plt.figure(figsize=(10,5))
				plt.title("jac("+args.model+"(msa[0]))")
				plt.imshow(contacts)
				plt.show()

	
	elif args.type=="regression":
	
		PDB_IDS = [f.split("_")[0]  for f in os.listdir(args.input) if f.endswith(".a3m")]

		structures = {
		    name.lower(): get_structure(PDBxFile.read(rcsb.fetch(name, "cif")))[0]
		    for name in PDB_IDS
		}

		contacts = {
		    name: contacts_from_pdb(structure, chain="A")
		    for name, structure in structures.items()
		}

		msas = {
		    name: read_msa(args.input+f"{name.lower()}_1_A.a3m")
		    for name in PDB_IDS
		}

		sequences = {
		    name: msa[0] for name, msa in msas.items()}
		
		predictions = {}
		results = []
		for name, inputs in sequences.items():
			predictions[name]=predict_contacts_regression(model,inputs,tokenizer,device)

			metrics = {"id": name, "model": args.model+"(Unsupervised)"}
			metrics.update(evaluate_prediction(predictions[name], contacts[name]))
			results.append(metrics)

		results = pd.DataFrame(results)
		print(results)