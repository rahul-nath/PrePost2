class Action(object):
    name = ""
    associated_docs = set()
    act_obj_docs = set()
    # need to store objects as tuples in this set
    # need to associate the pmi to the word and the specific objects
    objects = set()
    pmi_dict = []
    cand_words = []
    act_feat_chsq_dict = []
    feat_vectors = [] # just a list of dictionaries

    def __init__(self, action_name, doc_num, jects):
        self.name = action_name
        self.associated_docs.add(doc_num)
        self.objects.add(jects)

    def __eq__(self, other_name):
        return self.name == other_name

    def add_doc(self, doc_num):
        self.associated_docs.add(doc_num)

    def add_pmi(self, dic):
        # dic is { 'word' : word, 'pmi' : pmi, 'objects' : objects, 'mut_docs' : mutual docs}
        self.pmi_dict.append(dic)

    def add_cand_word(self, dic, label = 'a'):
        dic["label"] = label
        self.cand_words.append(dic)

    def add_feature(self, chsq, feat):
        dic = {}
        dic["chsq"] = chsq
        dic["feat"] = feat
        self.act_feat_chsq_dict.append(dic)

    def add_feat_vector(self, feat_dict):
        self.feat_vectors.append(feat_dict)

class Act_Object(object):
    name = ""
    associated_docs = set()
    pmi_dict = []

    def __init__(self, object_name, doc_num):
        self.name = object_name
        self.associated_docs.add(doc_num)

    def __eq__(self, other_name):
        return self.name == other_name

    def add_doc(self, doc_num):
        self.associated_docs.add(doc_num)

    def add_pmi(self, dic):
        self.pmi_dict.append(dic)

class Doc(object):
    name = ""
    word_list = []
    # to get the total count, take the lengh of the array

    def __init__(self, doc_name, word_list):
        self.name = doc_name
        self.word_list = word_list

    def __eq__(self, other_name):
        return self.name == other_name

    def __contains__(self, word):
        return word in self.word_list

class Word(object):
    name = ""
    associated_docs = set()
    doc_and_freq = {}
    total_doc_freq = 0
    
    def __init__(self, word_name, doc_name):
        self.name = word_name
        self.add_doc(doc_name)

    def __eq__(self, other_name):
        return self.name == other_name

    def add_doc(self, doc_name):
        if doc_name in self.associated_docs:
            self.doc_and_freq[doc_name] = self.doc_and_freq[doc_name] + 1
        else:
            self.associated_docs.add(doc_name)
            self.doc_and_freq[doc_name] = 1
        self.total_doc_freq += 1

    def get_freq(self, doc_name):
        return self.doc_and_freq[doc_name]

    def get_total(self):
        return self.total_doc_freq

#    def __contains__(self, word):
#        return word in self.word_list
