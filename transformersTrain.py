#!/usr/bin/env python
# coding: utf-8
import numpy as np
import pandas as pd
import re

#
# Load data
#
train_df = pd.read_csv("./Corona_NLP_train.csv", 
                       encoding = "ISO-8859-1")
test_df  = pd.read_csv("./Corona_NLP_test.csv", 
                       encoding = "ISO-8859-1")

#
# Clean data
#
def clean_string(ss):
    ss = re.sub(r'https?://\S+', 'url', ss)
    ss = re.sub(r'#', ' # ', ss)
    ss = re.sub(r'\s+', ' ', ss)    
    return ss

train_df["ProcessedTweet"] = train_df["OriginalTweet"].apply(clean_string)
test_df["ProcessedTweet"]  = test_df["OriginalTweet"].apply(clean_string)

#
# Convert class to numerical values
#

from collections import Counter
print(Counter(train_df["Sentiment"]))

clss_lst = sorted(list(set(Counter(train_df["Sentiment"]))))
clss_to_id = {k:i for i, k in enumerate(clss_lst)}
id_to_clss = {i:k for i, k in enumerate(clss_lst)}

print(clss_lst)
print(clss_to_id)
print(id_to_clss)

train_df["y"] = train_df["Sentiment"].apply(lambda x: clss_to_id[x])
test_df["y"]  = test_df["Sentiment"].apply( lambda x: clss_to_id[x])

print("Train data {}   \nTest data  {}".format(train_df.shape, test_df.shape))
train_x, train_y = train_df["ProcessedTweet"], train_df["y"]
test_x,  test_y  = test_df["ProcessedTweet"],  test_df["y"]

#
# Do train-dev split
#
from sklearn.model_selection import train_test_split
train_x, dev_x, train_y, dev_y = train_test_split(
    train_x, train_y, test_size=0.2, stratify=train_y)

#
# create the model here
#
from numpy.lib.function_base import append
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers import BertForSequenceClassification
from sklearn.model_selection import train_test_split
import torch
from torch.utils.data import DataLoader
import copy, time
import numpy as np
from collections import Counter
import math 


from transformers import BertForSequenceClassification, AutoModelForSequenceClassification
from collections import Counter
from datasets import list_metrics, load_metric
import numpy as np
import torch
import random, os, copy
from transformers import AdamW, get_linear_schedule_with_warmup
from sklearn.metrics import f1_score, classification_report, accuracy_score
from tqdm.auto import tqdm
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

from transformers import AutoConfig, AutoModelForSequenceClassification

# Download configuration from huggingface.co and cache.
# config = AutoConfig.from_pretrained("bert-base-cased")
# print(config)

import os
os.environ["CUDA_VISIBLE_DEVICES"]= "7"

# create the tokenizer and the model
torch.cuda.empty_cache()

print("Creating model ..... ")
model_name = "bert-base-uncased"
model_bl = AutoModelForSequenceClassification.from_pretrained(
    model_name, num_labels=len(id_to_clss.keys()))
model_bl.cuda()
model_tokenizer = AutoTokenizer.from_pretrained(model_name)

torch.cuda.empty_cache()

#
# create the dataloaders here
#
class textDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels
        assert(len(self.encodings[list(self.encodings.keys())[0]]) == len(self.labels))

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx][:128]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

# create the tokenized dataloader
train_x_tok = model_tokenizer(train_x.tolist(), truncation=True, padding=True, max_length=128)
dev_x_tok   = model_tokenizer(dev_x.tolist(),   truncation=True, padding=True, max_length=128)
test_x_tok  = model_tokenizer(test_x.tolist(),  truncation=True, padding=True, max_length=128)

train_dl = DataLoader(textDataset(train_x_tok, train_y.tolist()), shuffle=True, batch_size=32)
dev_dl   = DataLoader(textDataset(dev_x_tok,   dev_y.tolist()),   shuffle=True, batch_size=32)
test_dl  = DataLoader(textDataset(test_x_tok,  test_y.tolist()),  shuffle=True, batch_size=32)

#
# create the train and evalauate functions here
#
def f1(y_true, y_pred, weighted=False, print_clfn_rpt=True):
    y_true = y_true.astype(np.int64)
    assert y_pred.size == y_true.size
    f1_macro    = f1_score(y_true, y_pred, average='macro')
    f1_micro    = f1_score(y_true, y_pred, average='micro')
    f1_weighted = f1_score(y_true, y_pred, average='weighted')
    if print_clfn_rpt:
        print(classification_report(y_true, y_pred))
    print("accuracy score : ", accuracy_score(y_true, y_pred))
    if weighted:
        return f1_macro, f1_micro, f1_weighted
    return f1_macro, f1_micro

def evaluate_fn(model, eval_dataloader, name, device, return_lbls=False, return_probs=False):
    model.eval()
    tot_loss = []
    y_tr, y_pr, y_probs = [], [], []
    sftmx = torch.nn.Softmax(dim=1)
    for batch in eval_dataloader:
        batch = {k: v.to(device) for k, v in batch.items()}
        batch['labels'] = batch['labels'].type(torch.LongTensor).to(model.device)
        with torch.no_grad():
            outputs = model(**batch)
        loss, logits = outputs[0], outputs[1]
        predictions = torch.argmax(logits, dim=-1)
        y_probs.extend(sftmx(logits).tolist())
        y_pr.extend(predictions.tolist()); y_tr.extend(batch["labels"].tolist())
        tot_loss.append(loss.mean().item())
    f1_macro, f1_micro, f1_weighted = f1(np.array(y_tr), np.array(y_pr), True)
    print("Obtained a loss / f1 score of {:.3f} / {:.3f} on {} dataset.".format(
        np.mean(tot_loss), f1_weighted, name))
    print("Obtained a f1 score {} macro / micro / weighted : {} / {} / {} \n\n".format(
        name, f1_macro, f1_micro, f1_weighted))
    model.train()
    print("********************************")
    
    if return_lbls:
        return y_pr
    
    if return_probs:
        return y_probs
    
    return f1_weighted

def train_fn(model, train_dataloader, eval_dataloader, device, n_epochs=5, lr=2e-5, 
             eval_per_epoch=4, load_best=True, weights=None, use_probab=False, eval_train=True):
    # Create optimizer and the scheduler.
    no_decay = ['bias', 'LayerNorm.weight']
    optimizer_grouped_parameters = [
        {'params': [p for n, p in model.named_parameters() if not any(
            nd in n for nd in no_decay)], 'weight_decay': 0.01},
        {'params': [p for n, p in model.named_parameters() if any(
            nd in n for nd in no_decay)], 'weight_decay': 0.0}
        ]
    optimizer = AdamW(optimizer_grouped_parameters, lr=lr, eps=1e-8)
    num_training_steps = n_epochs * len(train_dataloader)
    lr_scheduler = get_linear_schedule_with_warmup(optimizer=optimizer, 
                                                   num_warmup_steps=num_training_steps//10, 
                                                   num_training_steps=num_training_steps)

    # write the train loop
    progress_bar = tqdm(range(num_training_steps))
    model.train(); eval_at = 1/eval_per_epoch;
    best_f1 = 0.0
    import random
    import time
    import uuid; 
    import os 

    aaaa = uuid.uuid4().hex.upper()
    pth = "./results/wts_{}".format(aaaa)
    
    for epoch in range(n_epochs):
        print("\nTraining for epoch {} .....".format(epoch))
        next_eval_at = eval_at
        for i, batch in enumerate(train_dataloader):
            # evaluate_fn(model, train_dataloader, "train", device); next_eval_at += eval_at
            batch = {k: v.to(device) for k, v in batch.items()}
            labels_old = copy.deepcopy(batch['labels'])
            batch['labels'] = batch['labels'].type(torch.LongTensor).to(model.device)
            wts = batch.get('wts', None)
            if 'wts' in batch:
                batch.pop('wts')
            
            outputs = model(**batch)

            loss = outputs[0]
            
            loss.backward(); 
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step(); lr_scheduler.step(); optimizer.zero_grad()
            progress_bar.update(1)

        eval_f1 = evaluate_fn(model, eval_dataloader, " eval dl 1 ", device)
        if eval_f1 > best_f1:
            print("new best eval_f1 {}, saving the model ..... ".format(eval_f1))
            model_to_save = model.module if hasattr(model, "module") else model
            model_to_save.save_pretrained(pth)
            best_f1 = eval_f1

    if load_best:
        print("Loading best model with f1 score of .... {} .".format(best_f1))
        model_to_load = model.module if hasattr(model, "module") else model
        model_to_load.from_pretrained(pth)
        model.to(device)
        print("Best path .... ", pth)
        # os.system("rm -rf {}".format(pth))
        return model_to_load

# instantiate the model here;
model_name = "bert-base-uncased"
model_bl = AutoModelForSequenceClassification.from_pretrained(
    model_name, num_labels=len(id_to_clss.keys()))
model_bl.cuda()
model_tokenizer = AutoTokenizer.from_pretrained(model_name)

torch.cuda.empty_cache()

#
# call the train function on the dataloaders
#
train_fn(model_bl, train_dl, dev_dl, model_bl.device, eval_train=False)

#
# call the evaluate function on the test dataloader
#
evaluate_fn(model_bl, test_dl, " test dl ", model_bl.device)

