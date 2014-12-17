import re, string, unicodedata, time, urllib, os.path
import cPickle as pickle
import numpy as np
from scipy.stats import chisquare
from htmlentitydefs import name2codepoint
from selenium import webdriver
from nltk.stem.snowball import SnowballStemmer
from nltk.corpus import stopwords
from My_Objects import Doc, Action, Act_Object, Word

from multiprocessing import Pool
from bs4 import BeautifulSoup
from math import log
from bisect import bisect_left
from string import lower
from random import shuffle, uniform

domain = "freecell"
task_file = 'ace_freecell_solved.pl'
progs = ["is", "are", "was", "were"] # list of progressive forms
stops = set(stopwords.words("english"))
stemmer = SnowballStemmer("english")

link_list = set() # load with the links from existing files
to_save_link_list = set() # place to store new links
actions = {} # actions and their objects
# object lists
doc_pages = [] 
action_pages = [] 
object_pages = []
word_pages = []
feature_pages = []

picked_feats = {}
total_docs = 0

# Pre: task_file contains a plan trace from observations or a planning engine.
#      Can be extended to read many task files; for now I am reading only one
# Post: actions contains all the actions and its corresp. objects from task_file as strings
#       all links from previous runs have been loaded
def get_from_task_file():
    with open(task_file, 'rb') as f:
        whole_doc = f.read() # this may be a bug as well
    # example: pickup_from_card_in_column(card_2_hearts,card_6_spades,col_4),
    act_objs = whole_doc[(whole_doc.index("[") + 1) : whole_doc.index("]")].split()
    for act_obj in act_objs:
        action = act_obj[:act_obj.index("(")]
        objects_str = act_obj[act_obj.index("(") + 1 : act_obj.index(")")]
        objects = tuple(''.join(x for x in objects_str if not x.isdigit()).replace("_", " ").replace("  ", " ").split(","))
        global actions
        # same action, different tuple? will that happen?
        actions[action] = objects  # assign tuple of objects (strings) to the action
    global total_docs
    total_docs = restore_docs()
    fl = open("links_from_google.txt", "wb")
    for l in link_list:
        fl.write(l + "\n")

# restores pickle files as arrays and moves them into primary storage
def restore_docs():
    num_docs = 130      # SET TO 0
    file_name = "{0}.p"
    # get links from existing docs if they are there
    doc_contents = []
    while (os.path.isfile(file_name.format(num_docs))):
        with open(file_name.format(num_docs), 'rb') as f:
            doc_contents = pickle.load(f)  # the array of everything 
        global link_list

        #        if doc_contents[0] not in link_list: can include this but need to increment num_docs to avoid loop
        link_list.add(doc_contents[0])
        num_docs += store_primarily(doc_contents, num_docs)

    return num_docs

def store_primarily(the_doc, num_docs):
    # don't need to sort; just need to remove duplicate words
    action = the_doc[1]
    objects = the_doc[2] # expected to be a tuple
    read_doc = the_doc[3:]

    doc = [x for x in set(read_doc)]
    for word in doc:
        if len(word) > 2 and word not in stops and not any(char.isdigit() for char in word):
            stem_word = stemmer.stem(word)
            global word_pages
            if stem_word in word_pages:
                word_pages[word_pages.index(stem_word)].add_doc(num_docs) 
            else:
                word_pages.append(Word(stem_word, num_docs))
        else:
            doc.remove(word)
    global doc_pages
    doc_pages.append(Doc(str(num_docs), doc))

    # this doc is associated with this action
    global action_pages
    if action not in action_pages:
        # objects is the tuple associated with the action 
        action_pages.append(Action(action, num_docs, objects)) 
    else:
        action_pages[action_pages.index(action)].add_doc(num_docs) 

    # this doc is associated this action's set of objects        
    global object_pages
    # objects is a list of strings
    for obj in objects:
        if obj not in object_pages:
            object_pages.append(Act_Object(obj, num_docs))
        else:
            object_pages[object_pages.index(obj)].add_doc(num_docs)
    print "doc {0} in primary storage".format(num_docs)
    return 1

# Pre: depth is the num of pages to be scraped
# Post: retrieves the text from the links retrieved from google
#       and writes the working links back to file
def make_text_docs():
    for action, objects in actions.items():
        #print "main action", action
        query = action + " "
        # objects are tuples
        for x in objects:
            query += x + " "
        # links in to_save_link_list
        links = getRealLinks(query)
        #print "got all the links from google"
        # the links associated with this action and its objects
        # need to make sure links are written to file
        pool = Pool(processes = 4)
        for link in links:
            text = "" # using static scope to ensure htmltext is stored as calls are passed around
            pool.apply_async(get_many_sites, args = (link, text, action, objects), callback = process_links)
        pool.close()
        pool.join()
        global to_save_link_list
        to_save_link_list = set()
        print "processed all the links for this action"
    print total_docs

# Pre: query is the string concatenation of the action and its objects
#      depth is the number of pages from google to be scraped
# Post: returns the set of links retrieved from the web
# took out depth for now
def getRealLinks(query):
    pool  = Pool(processes = 4)
    depth = 0
    for prog in progs:
        pool.apply_async(getLinks, args = (query, prog, depth), callback = join_results)
        depth = depth + 5 # change to 25 soon
    pool.close()
    pool.join()
    print "all the links: ", len(to_save_link_list)
    return to_save_link_list

# Pre: progs is the list of progressive additions to the front of the word
# Post: return a set of the links
def getLinks(search_term, prog, depth):
    driver = webdriver.Firefox()
    results = set()
    temp = search_term.split("_")
    temp[0] =  temp[0] + "ing"
    search = domain + " " + prog + " " +  " ".join(temp) #add the 'ing'
    term = search.replace(",", " ").replace("(", " ").replace("_", "+").replace(" ", "+").strip(")")
    # bing: query = "http://www.bing.com/search?q=" + term + "&go=Submit&first={0}".format(depth)
    query = "http://www.google.com/search?num=5&q=" + term + "&start=" + str(depth)
    connected = False
    while not connected:
        num = uniform(10, 15)
        try:
            time.sleep(num)
            driver.implicitly_wait(10) # may not need this; not sure
            driver.get(query)
            connected = True
        except Exception, e:
            print "first except"
            if "503" in e:
                # can't get this query, salvage what I have
                return results 
            else:
                continue
    htmltext = driver.page_source
    soup = BeautifulSoup(htmltext)
    search = soup.findAll('li', 'g')
    for result in search:
        title_a = result.find('a')
        title = ''.join(title_a.findAll(text=True))
        title = html_unescape(title)
        url = title_a['href']
        match = re.match(r'/url\?q=(http[^&]+)&', url)
        if match:
            url = urllib.unquote(match.group(1)).encode("utf8")
        if ".gz" not in url and ("http" or "www" in url):
            results.add(url) # maybe ascii or whatever
    driver.close()
    return results

# Pre: st is a url
# Post: the url is returned free of escape characters
def html_unescape(st):
    def entity_replacer(m):
        entity = m.group(1)
        if entity in name2codepoint:
            return unichr(name2codepoint[entity])
        else:
            return m.group(0)
    def ascii_replacer(m):
        cp = int(m.group(1))
        if cp <= 255:
            return unichr(cp)
        else:
            return m.group(0)
    s = re.sub(r'&#(\d+);',  ascii_replacer, st, re.U)
    return re.sub(r'&([^;]+);', entity_replacer, s, re.U)
 
# Pre: callback function for pool process for RealLinks. Results are the links retrieved.
# Post: link_list is updated with the links found in one process
def join_results(results):
    global to_save_link_list
    # only good links are stored
    to_save_link_list = to_save_link_list.union(results)

def get_many_sites(link, htmltext, action, objects):
    try:
        global link_list
        if link not in link_list:
            driver = webdriver.Firefox()
            driver.set_page_load_timeout(30)
            driver.get(link)
            htmltext = driver.page_source
            link_list.add(link)
            driver.close()
        else:
            # gets rid of bad link or existing link
            return (htmltext, action, objects, link)
        print "got the page"
        return (htmltext, action, objects, link)
    except Exception, e:
        driver.close()
        return (htmltext, action, objects, link)

# Pre: the 'array' is actually a tuple, but accessed the same way
#      it holds the html_text fetched, and the names of the action and objects
# Post: the object lists are created from the html_text
def process_links(html_text_array):
    html_text = html_text_array[0]
    global total_docs

    # crucially, htmltext will be empty if a bad link was accessed or an existing link was found, 
    # so nothing will be written to file when links are processed
    if not html_text:
        print "empty html"
        return
    else:
        action  = html_text_array[1]
        objects = html_text_array[2]
        link = html_text_array[3]
        # objects is a tuple
        prefix = [link, action, objects]
        file_name = "{0}.p".format(total_docs)
        print "total docs", total_docs
        soup = BeautifulSoup(html_text)
        for script in soup(["script", "style"]):
            script.extract()
        string_text = unicodedata.normalize('NFKD', soup.get_text()).encode('ascii','ignore')
        #print "string text", string_text
        # the entire doc with stopwords and with the link, action, and objects first in the array
        
        doc_array = string_text.translate(string.maketrans("",""), string.punctuation)
        lower_case = lower(doc_array).replace("\n", " ")
        lower_case_array = lower_case.split()
        prefix.extend(lower_case_array)
        with open(file_name, "wb") as f:
            # write link, then action#objects
            pickle.dump(prefix, f)
        print "written to secondary storage"
        total_docs += store_primarily(prefix, total_docs)

###############################################################################

def calculate():
    global action_pages
    for act in action_pages:
        calculate_help(act)

# Pre: All the object pages have been made, and links retrieved
# Post: Pmis are calculated for each word in the set of docs
#       against the mutual set of documents associated between words,
#       actions, and objects
def calculate_help(act):
        set_of_act_obj_docs = act.associated_docs
        mut_doc_set = {}
        # act.objects is a set of tuples
        print act.objects
        for tup in act.objects:
            # objects is a tuple of strings
            obj_set = set(object_pages[object_pages.index(tup[0])].associated_docs)
            for obj in tup:
                obj_set = obj_set.intersection(object_pages[object_pages.index(obj)].associated_docs)
            mut_doc_set[tup] = obj_set # each tuple of objects associated with the mutual docs
        # muts are the mutual docs between the object tuples set; l the list of objects
        for tup, muts in mut_doc_set.items():
            # mutual docs between the act and one set of objs
            set_of_act_obj_docs = set_of_act_obj_docs.intersection(muts) 
            for word in word_pages:
                pmi_dict = {}
                # all the docs that the word and the objects and the actions have in common
                mut_docs = set_of_act_obj_docs.intersection(word.associated_docs) 

                word_sum_in_act_docs = len(mut_docs) # numerator
                total_word_sum_in_docs = len(word.associated_docs) # denominator
                pmi = 0
                # set_of_act_obj_docs is still the sets mutual only to the action and its objects
                if total_word_sum_in_docs*len(set_of_act_obj_docs) == 0:
                    raise Exception("there are no mutual docs for this word")
                    continue # just go to the next word
                elif word_sum_in_act_docs == 0:
                    pmi = float("-inf")
                else:
                    pmi = log(float(word_sum_in_act_docs)/(total_word_sum_in_docs*len(set_of_act_obj_docs)), 2)
                # storing all information associated with this word
                pmi_dict["word"] = word
                pmi_dict["pmi"] = pmi
                pmi_dict["objects"] = tup
                # NOTE THAT THIS IS ONLY THE SET OF DOCS INTERSECTING WITH THE ACTION DOCS AND OBJECT DOCS
                pmi_dict["mut_docs"] = set_of_act_obj_docs 
                # want to associate the pmi with the action because the type of the objects are fixed
                act.add_pmi(pmi_dict)

def pick_candidates():
    global domain, action_pages
    for act in action_pages:
        #print "top 500 candidate words" 
        i = 500
        n = 10
        # list of dictionaries, sorted by the pmi of the candidate word
       # sorted_pmi_dict = sorted(act.pmi_dict, key=lambda k:k['pmi'], reverse = True)
        shuffle_pmi_dict = act.pmi_dict
        shuffle(shuffle_pmi_dict)
        # stores the top 100 candidate words
        for dic in shuffle_pmi_dict:
            if n != 0:
                o = ", ".join([x for x in dic["objects"]])
                # o should be in act_objects
#                print "action's objects: ", act.objects
#                print "word's objects: ", o
                # labelling a partial set of the actions in order to get a set of feature words
                value = raw_input("ACTION: \"{0}\"; OBJECTS: \"{1}\"; ".format(act.name, o) + \
                    "DOMAIN: \"{0}\".\n Is \"{1}\" ".format(domain, dic["word"].name) + \
                    " a good candidate for static precondition? y or n.\n")
              
                if value == "y":
                    # if it's labeled 'yes', then obviously we want it
                    # as part of our ultimate list
                    act.add_cand_word(dic, 1)
                    feature_pages.append(dic) # these are the candidate words we want to check every word against
                else:
                    act.add_cand_word(dic, 0)
                n -= 1
            else:
                act.add_cand_word(dic)
            i -= 1
            if i == 0:
                print "\n"
                break

# high chi square values indicate high frequency words observed with
# labeled preconditions means this word is likely to be a precondition
# chi square gives value of words that appear more often than by chance.
def generate_features():
    global word_pages
    global feature_pages
    threshold_cs = 7 # 75 threshold chi square value
    threshold_freq = 8 # how many times the words appears in total; stop words excluded
    for act in action_pages:
        for cand in feature_pages:
            for word in word_pages:
                if word.total_doc_freq > threshold_freq: # not words we know to be useless
                    chisq = chisquare(np.array([word.total_doc_freq, cand["word"].total_doc_freq]))[0] 
                    if (chisq > threshold_cs):
                        #print "chisq: ", chisq, "feature word: ", word.name, "candidate word: ", word_dict["word"].name
                        act.add_feature(chisq, word)
# feature_pages has all the final candidate words; need to make sure they have pmis
# have to look for words in the pmi dicts for each action. if it's there, add to the
# feature vector set; if not, then continue.

# may need to just eliminate the top 500 words requirement.

def create_feature_vectors():
    global domain
    for act in action_pages:
        #print "top 100 feature_candidate words:"
        i = 100
#        sorted_pmi_dict = sorted(act.act_feat_cand_pmi_dict, key=lambda k:k['pmi'], reverse = True)
        for dic in act.act_feat_chsq_dict:
            for cand_word in act.cand_words:
                if dic["feat"].name == cand_word["word"]:
                        cand_word["chsq"] = dic["chsq"]
                        o = ", ".join([x for x in cand_word["objects"]])
                        value = raw_input("ACTION: \"{0}\"; OBJECTS: \"{1}\"; ".format(act.name, o) + \
                                "DOMAIN: \"{0}\".\n Is \"{1}\" ".format(domain, cand_word["word"].name) + \
                                " a good candidate for static precondition? y or n.\n")
                        if value == "y":
                            cand_word["label"] = 1
                        else:
                            cand_word["label"] = 0
                        act.add_feat_vector(cand_word)
            #print cand_word["word"], cand_word["pmi"], cand_word["label"], cand_word["act"], cand_word["objects"]
            i -= 1
            if i == 0:
                print "\n"
                break
    f = open("feature_vectors.txt", "wb")
    for act in action_pages:
        for fv in act.feat_vectors:
            o = ", ".join([x for x in fv["objects"]])
            act_obj_last = fv["word"].name + ", " + act.name + ", " + o
            attribute = str(fv["pmi"]) + ", " + str(fv["chsq"]) + ", " + str(fv["label"])
            f.write(act_obj_last + "\n")
            f.write(attribute)
            f.write("\n\n")
    f.close()

# At this point, each action has a list of candidate words from the first pmi and a set of candidate
# words after the second pmi. 

get_from_task_file()
make_text_docs()
calculate()
pick_candidates()
generate_features()
create_feature_vectors()

'''
# Pre: a is an indexable container and x is the element to be found
# Post: returns the index of the element if present
# This method was created to reduce the runtime; may be used again
def binary_search(a, x, lo=0, hi=None):   # can't use a to specify default for hi
    hi = hi if hi is not None else len(a) # hi defaults to len(a)   
    pos = bisect_left(a,x,lo,hi)          # find insertion position
    return (pos if pos != hi and a[pos] == x else -1) # don't walk off the end


#remnant of my attempt at parallelization for this
def calculate_features():
    for act in action_pages:
        calculate_features_help(act)

# need some method to calculate the n-grams between the 
# candidate words and then re-store them into the list
def calculate_features_help(act):
    word_sum_act_docs = 0
    cand_sum_docs = 0
    feature_sum_docs = 0
    total_act_obj_docs = 0
    for pmi_dic in act.pmi_dict:
        for cand in act.cand_words:
            if pmi_dic["word"] == cand:
                for feat in feature_pages:
                    word_sum_act_docs = len(pmi_dic["mut_docs"].intersection(cand.associated_docs.intersection(feat.associated_docs)))
                    cand_sum_docs = len(cand.associated_docs)
                    feature_sum_docs = len(feat.associated_docs)
                    total_act_obj_docs = len(pmi_dic["mut_docs"])
                    pmi = log(float(word_sum_act_docs)/(feature_sum_docs*cand_sum_docs*total_act_obj_docs), 2)
                    act.add_feature(pmi, cand, feat, pmi_dic["objects"])
'''