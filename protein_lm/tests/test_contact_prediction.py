import torch
import esm
from protein_lm.evaluation.scripts.contact_prediction import predict_contacts_regression,predict_contacts_jacobian
from protein_lm.evaluation.scripts.utils import *
from protein_lm.tokenizer.tokenizer import EsmTokenizer
import pytest
proteins = ["1a3a", "5ahw", "1xcr"]
import os


@pytest.mark.parametrize("protein",proteins)
def test_contact_predictions_regression(protein):
	device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
	msa=read_msa("test_data/"+f"{protein.lower()}_1_A.a3m")
	seq=msa[0]
	model, _ = esm.pretrained.esm2_t33_650M_UR50D()
	tokenizer = EsmTokenizer()
	model.to(device)
	prediction=predict_contacts_regression(model,seq,tokenizer,device)
	contact_path = os.path.join(os.path.dirname(__file__),'tensors',protein+'.pkl')

	contact= torch.load(contact_path)
	torch.testing.assert_close(prediction,contact)

proteins = ["contact_pred_jacobian"]
@pytest.mark.parametrize("protein",proteins)
def test_contact_predictions_jacobian(protein):
	device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
	headers, seqs = parse_fasta("test_data/RL29.uni.1e-10.i8.i90c75.a3m", a3m = True)
	seq=seqs[0]
	model, _= esm.pretrained.esm2_t33_650M_UR50D()
	model.to(device)
	tokenizer = EsmTokenizer()
	x,ln = tokenizer.batch_encode([seq],add_special_tokens=True),len(seq)
	x=torch.tensor(x)
	prediction=predict_contacts_jacobian("ESM",model,x,ln,device)
	contact_path = os.path.join(os.path.dirname(__file__),'tensors',protein+'.pkl')

	contact= torch.load(contact_path)
	torch.testing.assert_close(prediction,contact)