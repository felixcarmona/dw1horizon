import sys;sys.path.insert(0,'.');from idx import load
p,e,x0,y0,x1,y1=sys.argv[1],int(sys.argv[2]),*map(int,sys.argv[3:7])
w,h,px,cl,b=load(p,e)
print('    '+''.join(str((x//10)%10) for x in range(x0,x1)))
print('    '+''.join(str(x%10) for x in range(x0,x1)))
for y in range(y0,y1): print('%3d '%y+''.join('.123456789ABCDEF'[px(x,y)] if b==0 else '%02x'%px(x,y) for x in range(x0,x1)))
if len(sys.argv)>7:
  for r,row in enumerate(cl[4]): print(r,' '.join('%04x'%v for v in row))
