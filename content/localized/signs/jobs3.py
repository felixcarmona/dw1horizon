from jobs import JOBS as J1, TEMPLATE
D={j[0]:j for j in J1}
def mk(name,base,edit):
    b=D[base]; return (name,b[1],b[2],b[3],b[4],edit)
KEEP=(' Remove every Japanese character, including the red vertical Japanese title along the right edge: no Japanese may remain. '
      'Keep exactly as in image 1, same shape and same position: the black drawn poop swirl near the top right, the blue wavy scribble, '
      'the red splat, the rust stains and the frame.')
JOBS=[
 mk('es3_mayo11','mayo11','replace all the Japanese writing with Spanish written horizontally, in the same hand-painted styles and colours: the red title at the top "NORMAS DEL PESCADOR"; the black rules "1. No ensuciarás este lugar, que es de todos." and "2. No pescarás más de la cuenta."; and the vandal\'s black scrawl at the bottom "¡Bah! ¡Me da igual!".'+KEEP),
 mk('en3_mayo11','mayo11','replace all the Japanese writing with English written horizontally, in the same hand-painted styles and colours: the red title at the top "FISHERMON\'S CODE"; the black rules "1. Thou shalt not litter this place: it belongs to all." and "2. Thou shalt not overfish."; and the vandal\'s black scrawl at the bottom "Shut up! Who cares!".'+KEEP),
]
