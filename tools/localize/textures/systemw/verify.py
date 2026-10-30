from tex import *; from words import *
g=grid()
def cmp(name,arr,u,v,mask_bg=None):
    bad=[]
    for y,row in enumerate(arr):
        for x,val in enumerate(row):
            o=g[v+y][u+x]
            if o!=val and not (mask_bg and o in mask_bg and val in mask_bg): bad.append((x,y,o,val))
    print(name,'w',len(arr[0]),'h',len(arr),'mismatch',len(bad),bad[:8])
# small font: words with their rect u
for w,u,v in [('MENU',0,34),('PRICE',20,34),('No.',40,34),('TITLE',52,34),('NAME',72,34),('MP',116,34),('SPEC',0,48),('TECH.',17,48),('DATA',37,48),('PLACE',56,48),('POINT',80,48),('COUNT',100,48),('RANG',76,41)]:
    if w=='No.': continue
    cmp(w,r_small(w),u,v,{0,15})
for j,w in enumerate(['FIRE','ICE','MECH']):
    pass
cmp('FIRE',r_elem('FIRE'),3,24,{0,15}); cmp('ICE',r_elem('ICE'),85,24,{0,15}); cmp('MECH',r_elem('MECH'),100,24,{0,15})
cmp('SPEED',r_stat('SPEED'),212,70,{0,15}); cmp('BRAINS',r_stat('BRAINS'),212,82,{0,15}); cmp('HAPPINESS',r_stat('HAPPINESS'),214,58,{0,15})
cmp('NAME',r_tag('NAME'),129,48,{0,15}); cmp('AGE',r_tag('AGE'),129,58,{0,15}); cmp('WEIGHT',r_tag('WEIGHT'),180,48,{0,15}); cmp('DIGI',r_tag('DIGI'),155,48,{0,15})
cmp('TYPE',r_tsa('TYPE',12,13),4,56,{0,15}); cmp('ACTIVE',r_tsa('ACTIVE',8,9),52,56,{0,15})

import words
words.DIAG=''
for w,u in [('NAME',129),('DIGI',155),('WEIGHT',180)]: cmp(w+'-4n',r_tag(w),u,48,{0,15})
cmp('AGE-4n',r_tag('AGE'),129,58,{0,15})
