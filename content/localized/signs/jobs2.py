from jobs import JOBS as J1, TEMPLATE
D={j[0]:j for j in J1}
def mk(name,base,edit,src=None,box=None):
    b=D[base]; return (name,src or b[1],box or b[2],b[3],b[4],edit)
KEEP=' Keep the blue wavy scribble, the drawn poop swirl and the red splat exactly where and how they are in image 1 (same shapes, same positions), the rust stains and the frame'
JOBS=[
 mk('en_betl02','betl02','replace the Japanese letters with the English word "COLISEUM" in the same red-orange neon tube lettering, same tube thickness and glow, same height, filling the sign like the original letters do'),
 mk('en_frzl06','frzl06','replace the Japanese on the upper board with "Iceberg Cape" and on the lower board with "Misty Trees", each in two short lines if needed, in the same pale green painted lettering, same size and style as the original characters'),
 mk('en_gcan09','gcan09','replace the big black Japanese characters with "Monochrome Shop" (two lines: "Monochrome" above "Shop") in the same black brush-like lettering, and the small red text with "all goods" in the same small red style'),
 mk('en_gias06b','gias06b','replace only the big red Japanese characters with "RECYCLING & CARDS" in the same bold red lettering; keep the grey line "RECYCLING & CARD SHOP" and the vertical "SALE" banner exactly as they are'),
 mk('en_mayo01_2','mayo01_2','replace the Japanese characters with "Mt. Panorama" in the same grey lettering, same size, above the same red arrow'),
 mk('en_mayo11','mayo11','replace all the Japanese writing with English written horizontally, in the same hand-painted styles and colours: the red title at the top "FISHERMON\'S CODE"; the black rules "1. Thou shalt not litter this place: it belongs to all." and "2. Thou shalt not overfish."; and the vandal\'s black scrawl at the bottom "Shut up! Who cares!".'+KEEP),
 mk('en_mayo10','mayo10','replace all the Japanese writing with English written horizontally, in the same hand-painted styles and colours: the red title at the top "FISHERMON\'S CODE"; the black rules "1. Thou shalt not litter this place: it belongs to all." and "2. Thou shalt not overfish."; and the vandal\'s black scrawl at the bottom "Shut up! Who cares!".'+KEEP),
 mk('en_omoc08','omoc08','replace the Japanese graffiti with the English tag "THE GANG WAS HERE!" in the same red spray paint with drips, written in short lines down the wall in the same area'),
 mk('en_trai00','trai00','replace the Japanese characters with the English "BATTLE CLASS" (two lines: "BATTLE", "CLASS") in the same bold blue-purple lettering, following the board\'s perspective'),
 mk('es2_mayo11','mayo11','replace all the Japanese writing with Spanish written horizontally, in the same hand-painted styles and colours: the red title at the top "NORMAS DEL PESCADOR"; the black rules "1. No ensuciarás este lugar, que es de todos." and "2. No pescarás más de la cuenta."; and the vandal\'s black scrawl at the bottom "¡Bah! ¡Me da igual!".'+KEEP),
 mk('es2_mayo10','mayo10','replace all the Japanese writing with Spanish written horizontally, in the same hand-painted styles and colours: the red title at the top "NORMAS DEL PESCADOR"; the black rules "1. No ensuciarás este lugar, que es de todos." and "2. No pescarás más de la cuenta."; and the vandal\'s black scrawl at the bottom "¡Bah! ¡Me da igual!".'+KEEP),
 mk('es2_twnb_open','twnb_open','replace the text with the Spanish single word "ABIERTO" in the same big red lettering as "OPEN", centred on the plate (no second word)'),
]
