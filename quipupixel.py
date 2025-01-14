#!/usr/bin/env python
# Quipu database to dot graphs
# Copyright (C) 2015 Dave Griffiths, Florian Zeeh
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from PIL import Image
from PIL import ImageDraw
import numpy as np
from matplotlib import pyplot as plt

import sys
import os
import xlrd
from quipulib import *
import entropy
import operator

_NUMERALS = '0123456789abcdefABCDEF'
_HEXDEC = {v: int(v, 16) for v in (x+y for x in _NUMERALS for y in _NUMERALS)}

_max_entropy = 0
_min_entropy = 999

max_height = 80

def reset_entropy():
    global _max_entropy
    global _min_entropy
    _max_entropy = 0
    _min_entropy = 999


def rgb(triplet):
    return _HEXDEC[triplet[0:2]], _HEXDEC[triplet[2:4]], _HEXDEC[triplet[4:6]]

def empty_collect():
    return {
        "ply":[],
        "attach":[],
        "length":[],
        "colours":[],
        "knot_value":[],
        "knot_type":[],
        "knot_position":[],
        "knot_spin":[]
    }

## pendant tree class
class pendant:
    def __init__(self,pid,ply,attach,knots,length,colours,value):
        self.pid = pid
        self.children = []
        self.ply = ply
        self.attach = attach
        self.knots = knots
        if length=="": self.length=0
        else: self.length = float(length)
        if self.length==0: self.length=5; # default
        self.colours = []
        for c in colours:
            # convert to triples
            self.colours.append(rgb(c[2:-1]))
        self.value = value
        self.entropy = -1

    def add(self,child):
        self.children.append(child)

    def find(self,pid):
        if self.pid==pid: return self
        else:
            for p in self.children:
                f = p.find(pid)
                if f: return f
            return False

    def calc_entropy(self):
        collect=empty_collect()
        self.as_raw(collect)

        self.entropy=0
        for i in collect.values():
            self.entropy += entropy.calc(i)

        global _min_entropy
        global _max_entropy

        if self.entropy<_min_entropy: _min_entropy=self.entropy
        if self.entropy>_max_entropy: _max_entropy=self.entropy

        for p in self.children:
            p.calc_entropy()

    def safe_plot(self,pixels,x,y,c):
        if x>0 and x<pixels.shape[1] and y>0 and y<pixels.shape[0]:
            if self.entropy!=-1:
                v=(self.entropy-_min_entropy)/(_max_entropy-_min_entropy)
                v*=225
                v+=25
                pixels[y,x]=(v,v,v)
            else:
                pixels[y,x]=c

    # slice the data for entropy calc
    def as_raw(self, collect):
        collect["ply"]+=[self.ply]
        collect["attach"]+=[self.attach]
        #collect["length"]+=[self.length]
        collect["colours"]+=self.colours
        collect["knot_value"]+=map(lambda k: k.value, self.knots)
        collect["knot_type"]+=map(lambda k: k.type, self.knots)
        #collect["knot_position"]+=map(lambda k: k.position, self.knots)
        collect["knot_spin"]+=map(lambda k: k.spin, self.knots)
        for c in self.children:
            c.as_raw(collect)

    # produce a json string of this pendant
    def as_json(self,depth):
        out=""
        header=""
        pheader=""
        for i in range(0,depth-1): pheader+=" "
        for i in range(0,depth): header+=" "
        out+=pheader+"{ \n"
        out+=header+"\"id\": \""+self.pid+"\", \"ply\": \""+self.ply+"\", \"attach\": \""+self.attach+"\", \n"
        cc = ""
        for i,c in enumerate(self.colours):
              cc+="["+str(c[0])+", "+str(c[1])+", "+str(c[2])+"]"
              if i!=len(self.colours)-1: cc+=", "

        out+=header+"\"colours\": ["+cc+"],\n"

        if (len(self.knots)==0):
            out+=header+"\"knots\": [],"
        else:
            out+=header+"\"knots\": [\n"
            for i,k in enumerate(self.knots):
                out+=header+"{ \"value\": "+str(k.value)+", \"type\": \""+k.type+"\", \"position\": "+str(k.position)+", \"spin\": \""+k.spin+"\" }"
                if i==len(self.knots)-1: out+="\n"
                else: out+=",\n"
            out+=header+"],\n"

        if (len(self.children)==0):
            out+=header+"\"children\": []\n"
        else:
            out+=header+"\"children\": [\n"
            for i,p in enumerate(self.children):
                out+=p.as_json(depth+2)
                if i==len(self.children)-1: out+="\n"
                else: out+=",\n"

            out+=header+"]\n"
        out+=pheader+"}"
        return out

    def num_pendants(self):
        count = 1
        for p in self.children:
            count+=p.num_pendants()
        return count

    def longest_pendant(self,depth):
        length = self.length+depth*3 # account for heirarchical position
        for p in self.children:
            l = p.longest_pendant(depth+1)
            if l>length: length=l
        return length

    def render_data(self,pixels,x,y):
        for i in range(0,int(self.length)):
            self.safe_plot(pixels,x,y+i,self.colours[i%len(self.colours)])

        kcol = self.colours[0]
        for k in self.knots:
            i = int(k.position)
            v = 25+k.value*25
            c = (255,255,0)
            if k.type=="S": c = (v,0,0)
            if k.type=="L": c = (0,v,0)
            if k.type=="E": c = (0,0,v)
            self.safe_plot(pixels,x+1,y+i,c)

    def render(self,pixels,sx,x,y):
        self.render_data(pixels,x,y)
        sx = x # where we started from
        tx = sx
        for p in self.children:
            for i in range(tx,x+3):
                self.safe_plot(pixels,i,y+3,p.colours[i%len(p.colours)])
            x+=3
            tx+=3
            tx,x=p.render(pixels,tx,x,y+3)
        return (sx,x)

########################################################

# just store the width and height for box fitting
def prerender(primary,filename,store):
    h = int(primary.longest_pendant(0))+10
    w = primary.num_pendants()*3
    h = min(h,max_height)
    store[filename] = [0,0,w,h]

# render a quipu, save the image and return it
def render(primary,filename):
    h = int(primary.longest_pendant(0))+10;
    h = min(h,max_height)
    im = Image.new("RGB", (primary.num_pendants()*3,h), "black")

    pixels=np.array(im)
    primary.render(pixels,0,0,0)
#    plt.imshow(pixels)
#    plt.show()
#    im.putdata(pixels)

    image = Image.fromarray(np.uint8(pixels))
    d_usr = ImageDraw.Draw(image)
    qname = os.path.basename(filename)[:-4]
    d_usr = d_usr.text((0,h-10),qname,(100,100,100))

    print("saving: pixel/"+qname+".png")
    image.save("pixel/"+qname+".png")
    return image


# convert a database spreadsheet into a dot file for visualisation
def parse_to_pendant_tree(quipu):
    primary = pendant("primary","?","?",[],0,["\"#ffffff\""],0)

    # skip the gumpf at the top, start on the 6th line
    for curr_row in range(6,quipu.nrows):
        # get the stuff from the row
        pid = quipu.cell_value(curr_row, 0)
        if quipu.cell_type(curr_row, 0)==2: # convert a number to text
            pid = str(int(pid))
        ply = quipu.cell_value(curr_row, 1)
        attach = quipu.cell_value(curr_row, 2)
        knots = parse_knots(quipu.cell_value(curr_row, 3))
        length = quipu.cell_value(curr_row, 4)
        if quipu.cell_type(curr_row, 4)==2: # convert a number to text
            length = str(length)
        colours = parse_colour(quipu.cell_value(curr_row, 7))
        value = quipu.cell_value(curr_row, 8)

        p = pendant(pid,ply,attach,knots,length,colours,value)

        if has_parent(pid):
            ppid = get_parent_pendant(pid)
            parent=primary.find(ppid)
            if parent:
                parent.add(p)
            else:
                print("parent "+ppid+" not found!")
                primary.add(p)
        else:
            primary.add(p)


    return primary

# box fitting algo for the big image - store in rows, and
# look for rows with enough space in, make new rows where
# required
def find_row(rows,w,maxw):
    for i,r in enumerate(rows):
        if (r+w+20)<maxw:
            rows[i]+=w+20
            return i
    rows.append(0)
    return len(rows)-1

def fit(store):
    widest=2000 # max width of a row
    rows = [0]
    for r in store.values():
        row = find_row(rows,r[2],widest)
        r[0]=rows[row]-r[2] # store the position
        r[1]=row*max_height

    return (widest,len(rows)*max_height)

# create the box fit coordinates using width/heights
def prerun(filename,store):
    # open the spreadsheet
    try:
        workbook = xlrd.open_workbook(filename)
        quipu = workbook.sheet_by_name('Pendant Detail')
    except Exception:
        print "problem"
        return False
    primary = parse_to_pendant_tree(quipu)
    #primary.calc_entropy()
    prerender(primary,filename,store)
    return store

# actually create the image
def run(filename):
    # open the spreadsheet
    try:
        workbook = xlrd.open_workbook(filename)
        quipu = workbook.sheet_by_name('Pendant Detail')
    except Exception:
        print "problem"
        return False

    primary = parse_to_pendant_tree(quipu)
#    reset_entropy()
#    primary.calc_entropy()

    return render(primary,filename)

# calculate separate entropy values for each type of data
def global_entropy_sliced(filenames):
    collect={
        "ply":[],
        "attach":[],
        "length":[],
        "colours":[],
        "knot_value":[],
        "knot_type":[],
        "knot_position":[],
        "knot_spin":[]
    }

    for filename in filenames:
        # open the spreadsheet
        try:
            workbook = xlrd.open_workbook(filename)
            quipu = workbook.sheet_by_name('Pendant Detail')
            primary = parse_to_pendant_tree(quipu)
            primary.as_raw(collect)
        except Exception:
            pass

    for key,value in collect.items():
        print(key+" "+str(entropy.calc(value)))

# calculate separate entropy values for each type of data
def global_entropy_comp(filenames):
    cache = {}

    for filename in filenames:
        # open the spreadsheet
        try:
            workbook = xlrd.open_workbook(filename)
            quipu = workbook.sheet_by_name('Pendant Detail')
            primary = parse_to_pendant_tree(quipu)
            primary.calc_entropy()
            cache[filename]=primary.entropy
        except Exception:
            pass
    sorted_cache = sorted(cache.items(), key=operator.itemgetter(1))
    for item in sorted_cache:
        print(item)

    plt.rc('xtick', labelsize=6)

    ind = np.arange(len(sorted_cache))  # the x locations for the groups
    label_ind = np.arange(len(sorted_cache)/2)*2  # the x locations for the groups
    fig,ax = plt.subplots()
    rects = ax.plot(ind, map(lambda i: i[1], sorted_cache))
    ax.set_ylabel('entropy bits')
    ax.set_title('entropy per quipu (all data)')
    ax.set_xticks(label_ind)

    labels = []
    for i,v in enumerate(sorted_cache):
        if i%2==0: labels.append(os.path.basename(v[0])[:-4])

    ax.set_xticklabels(labels, rotation="vertical")
    plt.show()

# calculate separate entropy values for each type of data
def pairwise_entropy_comp(filenames):
    x = []
    y = []
    l = []
    for filename in filenames:
        # open the spreadsheet
        try:
            workbook = xlrd.open_workbook(filename)
            quipu = workbook.sheet_by_name('Pendant Detail')
        except Exception:
            continue
        primary = parse_to_pendant_tree(quipu)
        collect = empty_collect()
        primary.as_raw(collect)
        x+=[entropy.calc(collect["ply"])]
        y+=[entropy.calc(collect["knot_type"])]
        l+=[os.path.basename(filename)[:-4]]

    plt.xlabel('pendant ply entropy (bits)')
    plt.ylabel('knot type entropy (bits)')

    plt.scatter(x, y)
    for i, txt in enumerate(l):
        plt.annotate(txt, (x[i],y[i]), fontsize=6)
    plt.show()

# run over all quipus and paste them in the big image
def batch_run(filenames):
    store = {}
    for filename in filenames:
        prerun(filename,store)

    size = fit(store)
    im = Image.new("RGB", size, "black")

    for filename in filenames:
        if filename in store:
            qim = run(filename)
            im.paste(qim,(store[filename][0],store[filename][1]))

    print(len(store))
    im.save("comp.png")

# calculate separate entropy values for each type of data
def json_save(filenames):
    for filename in filenames:
        # open the spreadsheet
        try:
            workbook = xlrd.open_workbook(filename)
            quipu = workbook.sheet_by_name('Pendant Detail')
            primary = parse_to_pendant_tree(quipu)
            f = open("json/"+os.path.basename(filename)[:-4]+".json","w")
            f.write(primary.as_json(0))
            f.close()
        except Exception:
            continue

# are we the script that's being run?
if __name__ == "__main__":
    if sys.argv[1]=="batch":
        batch_run(generate_quipu_list())
    if sys.argv[1]=="sliced_entropy":
        global_entropy_sliced(generate_quipu_list())
    if sys.argv[1]=="global_entropy":
        global_entropy_comp(generate_quipu_list())
    if sys.argv[1]=="pairwise_entropy":
        pairwise_entropy_comp(generate_quipu_list())
    if sys.argv[1]=="json":
        json_save(generate_quipu_list())
    else:
        run(sys.argv[1])
