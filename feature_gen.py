import mechanize, re, string, unicodedata, time
from xgoogle.search import GoogleSearch, SearchError
from random import shuffle, uniform
from nltk.stem.snowball import SnowballStemmer
from nltk.corpus import stopwords
from Doc import Doc
from Action import Action
from Act_Object import Act_Object
from bs4 import BeautifulSoup
from math import log
from bisect import bisect_left
from string import lower

br = mechanize.Browser()
br.set_handle_robots(False)
br.addheaders = [('User-agent', 'chrome')]

domain = "freecell"
progs = ["is", "are", "was", "were"] # list of progressive forms
reqs = ["before", "must", "require", "first", "essential"] # feature words

# need list of all the actions with objects
# have to parse the objects
actions = {} # actions and their objects
doc_pages = [] # the doc objects
action_pages = [] # the action objects
object_pages = [] # the object objects
word_set = {} # set of unique words
sorted_word_set = {} # the unique words, sorted by their frequency
picked_features = {}
labeled_feats = {}
unlabeled_feats = []
total_docs = 0

def get_from_task_file():
    act_l = set()
    f = open('ace_freecell_solved.pl', 'r')
    whole_doc = f.read()
    f.close()
    act_objs = whole_doc[(whole_doc.index("[") + 1) : whole_doc.index("]")].split()
    for thing in act_objs:
        action = thing[:thing.index("(")]
        objects_str = thing[thing.index("(") + 1 : thing.index(")")]
        objects = ''.join(x for x in objects_str if not x.isdigit()).replace("_", " ").replace("  ", " ").split(",")
        #3-tuples with the original action and original objects?
        global actions
        actions[action] = objects  # assign array of objects to the action

def getLinks(domain, search_term, depth, prog_forms, num_pages):
    results = set()
    for prog in prog_forms:
        temp = search_term.split("_")
        temp[0] =  temp[0] + "ing"
        search = domain + " " + prog + " " +  " ".join(temp) #add the 'ing'
        for i in range(0, num_pages):
            try:
                wt = 5
                gs = GoogleSearch(search, random_agent=True)
                time.sleep(wt)
                gs.results_per_page = 25 # results per page, not the next page
                gs.page = i
                search_pages = []
                while True:
                    tmp = gs.get_results()
                    if not tmp: # no more results were found
                        break
                    search_pages.extend(tmp)
                    time.sleep(wt)
                    print wt
                for res in search_pages:
                    url = res.url.encode("utf8")
                    if url:
                        results.add(url)
            except SearchError, e:
                print "here", "Search failed: %s" % e
                continue
    return results

def make_text_docs(domain, depth, progs, num_pages):
    i = 0
    stops = set(stopwords.words("english"))
    for action, objects in actions.items():
        query = action + " "
        for x in objects:
                query += x + " "
        all_links = getLinks(domain, query, depth, progs, num_pages)
        links = (x for x in all_links if x)
        for link in links:
            try:
                htmltext = br.open(link).read()
                soup = BeautifulSoup(htmltext)
                for script in soup(["script", "style"]):
                        script.extract()
                string_text = unicodedata.normalize('NFKD', soup.get_text()).encode('ascii','ignore')
                lower_case_str = lower(string_text.translate(string.maketrans("",""), string.punctuation))
                # all docs are now stored internally
                doc = [x for x in set(sorted(lower_case_str.split()))]
                for word in doc:
                    # words are all unique, without integers
                    if len(word) > 2 and word not in stops and not any(char.isdigit() for char in word):
                        global word_set
                        if word in word_set:
                            word_set[word] = (word_set.get(word)[0] + 1, 0)
                        else:
                            word_set[word] = (1, 0)
                global doc_pages
                doc_pages.append(Doc(str(i), doc))

                global action_pages
                if action not in action_pages:
                    # objects is a list of strings
                    action_pages.append(Action(action, i, objects))
                else:
                    action_pages[action_pages.index(action)].add_doc(i)
                    action_pages[action_pages.index(action)].add_count()

                for obj in objects:
                    # obj is a string!
                    if obj not in object_pages:
                        object_pages.append(Act_Object(obj, i))
                    else:
                        # after retrieving the list of nums related to docs,
                        object_pages[object_pages.index(obj)].add_doc(i)
                        object_pages[object_pages.index(obj)].add_count()
                i += 1

            except Exception, e:
                print "second except"
                print e
                continue
    global total_docs
    total_docs = i
    print total_docs

def binary_search(a, x, lo=0, hi=None):   # can't use a to specify default for hi
    hi = hi if hi is not None else len(a) # hi defaults to len(a)   
    pos = bisect_left(a,x,lo,hi)          # find insertion position
    return (pos if pos != hi and a[pos] == x else -1) # don't walk off the end


def calculate():
#    global action_pages

    for act in action_pages:
        
        set_of_act_obj_docs = act.associated_docs
        for obj in act.objects:
            # get docs that are most closely related to the action and its objects
            set_of_act_obj_docs = set_of_act_obj_docs.intersection(object_pages[object_pages.index(obj)].associated_docs)
        act.add_mutual_docs(set_of_act_obj_docs)

        stemmer = SnowballStemmer("english")
        s_word_set = {}
        for w, f in word_set.items():
            word = w
            temp_total_sum = f[0]
            temp_act_sum = f[1]
            # sum up how many docs the non-stem word is in
            for doc in set_of_act_obj_docs:
                if word in doc_pages[doc]:
                    temp_act_sum += 1

            stem_word = stemmer.stem(w)
            # now take the stem of the word
            if stem_word in s_word_set:
                s_word_set[stem_word] = (s_word_set.get(stem_word)[0] + temp_total_sum, \
                                              s_word_set.get(stem_word)[1]+ temp_act_sum)
            else:
                s_word_set[stem_word] = (temp_total_sum, temp_act_sum)
        global sorted_word_set
        sorted_word_set = sorted(word_set.items(), key=lambda x:x[1][0], reverse=True)
        ###### consolidate and sort before calculating pmi
        pmi_dict = {}
        count = 500
        
        for w, t in sorted_word_set:
            total_word_sum_in_docs = t[0]
            word_sum_in_act_docs = t[1] 
            if total_word_sum_in_docs*len(act.mutual_docs) == 0:
                raise Exception("there are no mutual docs for some reason")
                continue
            elif word_sum_in_act_docs == 0:
                pmi = float("-inf")
            else:
                pmi = log(float(word_sum_in_act_docs)/(total_word_sum_in_docs*len(act.mutual_docs)), 2)
            pmi_dict["word"] = w
            pmi_dict["pmi"] = pmi
            count-= 1
            if count == 0:
                break
        # want to associate the pmi with the action because the type of the objects are fixed
        act.add_pmi(pmi_dict)
    
def pick_candidates():
#    print "top 100 candidate words" 
    sorted_pmi_dict = []
    for act in action_pages:
#        print act.name
        i = 100
        sorted_pmi_dict = sorted(act.pmi_dict, key=lambda k: k['pmi'], reverse = True)
        for dic in sorted_pmi_dict:
            word =  dic.get("word")
            act.add_cand_word(word)
            i -= 1
            if i == 0:
                print "\n"
                break

def calculate_features():
    word_sum_act_docs = 0
    cand_sum_docs = 0
    feature_sum_docs = 0
    for act in action_pages:
        for req in reqs:
            for cand in act.cand_words:
                for doc in act.mutual_docs:
                    if req and cand in doc_pages[doc]:
                        word_sum_act_docs += 1
                for doc in doc_pages:
                    if req in doc:
                        feature_sum_docs += 1
                    elif cand in doc:
                        cand_sum_docs += 1
                    else:
                        continue
                pmi = log(float(word_sum_act_docs)/(feature_sum_docs*cand_sum_docs*len(act.mutual_docs)), 2)
#                print "pmi", "cand", "req", "act", pmi, cand, req, act.name
                act.add_feature(pmi, cand, req)
                # dict: { cand_word = key, (req, pmi) = value }

def pick_feature_candidates():
    print "top 100 feature_candidate words:"
    for act in action_pages:
        print act.name
        print act.objects
        i = 100
        sorted_pmi_dict = sorted(act.act_feat_cand_pmi_dict, key=lambda k:k['pmi'], reverse = True)
        global picked_features
        for dic in sorted_pmi_dict:
            #print "cand: ", dic.get("cand")
            picked_features[dic.get("cand")] = act
            i -= 1
            if i == 0:
                print "\n"
                break

def label_features(dom):
    global labeled_feats
    temp_features = picked_features
    shuffle(temp_features)
    i = 25
    fin = False
    value = ""
    for c, a in temp_features:
        if fin == True:
            global unlabeled_feats
            unlabeled_feats.append(c)
        else:
            value = raw_input("Given the action, {0}, its object types, ".format(a.name) + (x + " " for x in a.objects)  +  \
                                " in the domain, {0}, is {1} a good candidate for a precondition? Yes or no.".format(dom, c))
            if value == "yes":
                labeled_feats[c] = (a, 1)
            else:
                labeled_feats[c] = (a, 0)
            i -= 1
            if i == 0:
                fin = True

get_from_task_file()
make_text_docs(domain, 25, progs, 1)
calculate()
pick_candidates()
calculate_features()
pick_feature_candidates()
label_features(domain)
