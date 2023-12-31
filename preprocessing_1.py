# -*- coding: utf-8 -*-

import re
import numpy as np
from tqdm import tqdm
from tensorflow.keras.preprocessing.sequence import pad_sequences
from keras.utils import to_categorical
import nltk

from nltk import pos_tag

def read_data(inpFile):
  """Reads a BIO data. Every sentence in the file is separated with an empty line."""
  inpFilept = open(inpFile,encoding='ISO-8859-1')
  tag_sent = []
  docs = []
  for line in inpFilept:
    contents = re.split("\t|\n", line)
    if (contents[0] != ""):
      w = contents[0]
      l = contents[1]
      tag_sent.append((w,l))
    else:
      docs.append(tag_sent)
      tag_sent = []
  print("Total number of sentences: {} ".format(len(docs)))
  return docs

"""### Superclass Preprocessing ###"""

class PreprocessingDocs(object): #passo come input un oggetto
  """Superclass for preprocessing."""
  def __init__(self, data): #definisco che tipo di oggetto
    self.data = data #list of sentences that are list of words in the tuple format (word, BIO label)
    self.sentences = [[w[0] for w in s] for s in data]
    self.tokens = [w for s in self.sentences for w in s]
    self.sent_labels = [[w[1] for w in s] for s in data]
    self.tagset = list(set([l for s in self.sent_labels for l in s]))
    self.vocabulary = set(self.tokens)
    sentences_len = [len(s) for s in self.sentences]
    self.max_seq_len = max(sentences_len)
    self.avg_seq_len = np.array(sentences_len).mean()
    self.std_seq_len = np.std(sentences_len)

"""###Neural networks###"""

class PreprocessingDocsNN(PreprocessingDocs): #passo come input un oggetto
  """Class utility to preprocess text for neural networks training."""
  def __init__(self, data): #definisco che tipo di oggetto
    super().__init__(data)


  def from_labels_2_idx(self):
    """From a tagset to a dict that map every word to an integer and viceversa."""
    tagset = self.tagset
    tag2idx = {t: i + 1 for i, t in enumerate(tagset)}
    tag2idx["PAD"] = 0 #pad value for padding input length
    idx2tag = {i: w for w, i in tag2idx.items()}
    
    return tag2idx, idx2tag

    
  def pad_list_of_sents(self, word2idx, max_seq_len = None): #bisogna convertire sents in integers
    """This function map every word in the sentences to an integer and returns a
     padded list of sentences (words) with len fixed to the max sentence length.
     
     Parameters
      ----------
    word2idx : dict
        Mapping of words to integers.
    max_seq_len : int (optional)
        None to pad sentences with the value of the most length sent in the list.
        Integer to set a different value. """
    
    list_of_sents = self.sentences
    if max_seq_len == None:
      padded_list_of_sents = pad_sequences(maxlen=self.max_seq_len, sequences=list_of_sents, padding="post", value="", dtype=object, truncating = "post")
    else:
      padded_list_of_sents = pad_sequences(maxlen=max_seq_len, sequences=list_of_sents, padding="post", value="", dtype=object, truncating = "post")
    return padded_list_of_sents

  def padded_and_encoded_labels(self, tag2idx, max_seq_len = None):
    """This function returns a padded list of sentences (labels) and 
    encode using one-hot encoding for the integer representation.
    
    Parameters
      ----------
    tag2idx : dict
        Mapping of labels to integers.
    max_seq_len : int (optional)
        None to pad sentences with the value of the most length sent in the list.
        Integer to set a different value."""

    list_of_sents_tags = self.sent_labels
    mapped_sents_tags = [[tag2idx[w] for w in s] for s in list_of_sents_tags]
    n_classes = len(tag2idx)
    if max_seq_len == None:
      padded_list_of_sents_tags = pad_sequences(maxlen=self.max_seq_len, sequences=mapped_sents_tags, padding="post", value=tag2idx["PAD"])
    else:
      padded_list_of_sents_tags = pad_sequences(maxlen=max_seq_len, sequences=mapped_sents_tags, padding="post", value=tag2idx["PAD"])
   # y = [to_categorical(i, num_classes=n_classes) for i in padded_list_of_sents_tags] #np.argmax(true, axis = -1 to reverse encoding.
    return np.array(padded_list_of_sents_tags)

"""###CRF###"""

class PreprocessingDocsCRF(PreprocessingDocs):
  """Subclass for CRF models."""
  def __init__(self, data):
    super().__init__(data)

  def addPOStags(self): #25s ET
    """Add Pos Tags as a feature."""
    sents = self.data
    docs = []
    print("Adding part-of-speech tags to the original corpus (word, label)...")
    for i, s in tqdm(enumerate(sents)):
      tokens = [t for t, label in s]
      tagged = pos_tag(tokens, tagset ='universal')
      docs.append([(w, pos, label) for (w, label), (word, pos) in zip(s, tagged)])
    print("Done.")
    return docs

  global word2features
  def word2features(sent, i):
    """Map words to dict of features. Code from sklearn-crfsuite API documentation."""
    word = sent[i][0]
    postag = sent[i][1]

    features = {
        'bias': 1.0,
        'word.lower()': word.lower(),
        'word[-3:]': word[-3:],
        'word[-2:]': word[-2:],
        'word.isupper()': word.isupper(),
        'word.istitle()': word.istitle(),
        'word.isdigit()': word.isdigit(),
        'postag': postag,
        'postag[:2]': postag[:2],
    }
    if i > 0:
        word1 = sent[i-1][0]
        postag1 = sent[i-1][1]
        features.update({
            '-1:word.lower()': word1.lower(),
            '-1:word.istitle()': word1.istitle(),
            '-1:word.isupper()': word1.isupper(),
            '-1:postag': postag1,
            '-1:postag[:2]': postag1[:2],
        })
    else:
        features['BOS'] = True

    if i < len(sent)-1:
        word1 = sent[i+1][0]
        postag1 = sent[i+1][1]
        features.update({
            '+1:word.lower()': word1.lower(),
            '+1:word.istitle()': word1.istitle(),
            '+1:word.isupper()': word1.isupper(),
            '+1:postag': postag1,
            '+1:postag[:2]': postag1[:2],
        })
    else:
        features['EOS'] = True

    return features

  global sent2features
  def sent2features(sent):
    """Map sent to dict of features for each word. Code from sklearn-crfsuite API documentation."""
    return [word2features(sent, i) for i in range(len(sent))]

  def transformDataInFeatureDict(self):
    """Method to trasform X input in a dict of features. Word --> Dict of features."""
    datawithPos = self.addPOStags()
    return [sent2features(s) for s in datawithpos]
