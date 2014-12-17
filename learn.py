import re, string, unicodedata, time, urllib
from My_Objects import Doc, Action, Act_Object
from bs4 import BeautifulSoup
from math import log
from bisect import bisect_left
from string import lower
from random import shuffle, uniform

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
            print labeled_feats
            i -= 1
            if i == 0:
                fin = True


