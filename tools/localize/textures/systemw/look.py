import sys; from tex import *
g=grid(); u,v,w,h,row,s=map(int,sys.argv[2:8])
crop(g,u,v,w,h,row,s=s).save(sys.argv[1])
