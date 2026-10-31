JOBS = [
 ('betl02','BETL02',(336,112,528,240),'3:2',
  'a curved neon sign over an arena entrance: Japanese katakana letters in red-orange neon tubes inside a green neon border, glowing on a dark background',
  'replace the Japanese letters with the Spanish word "COLISEO" in the same red-orange neon tube lettering, same tube thickness and glow, same height, filling the sign like the original letters do'),
 ('frzl06','FRZL06',(500,48,620,128),'3:2',
  'a wooden signpost in snow with two dark green arrow-shaped boards with pale green Japanese characters: the upper board points right, the lower board points left',
  'replace the Japanese on the upper board with "Cabo Iceberg" and on the lower board with "Árboles de Niebla", each in two short lines if needed, in the same pale green painted lettering, same size and style as the original characters'),
 ('gcan09','GCAN09',(524,40,644,120),'3:2',
  'a shop signboard with a white face and red border hanging on a dark wall: big black Japanese characters and a small red stamp-like Japanese text at the right',
  'replace the big black Japanese characters with "Tienda Monocromática" (two lines: "Tienda" above "Monocromática") in the same black brush-like lettering, and the small red text with "de todo" in the same small red style'),
 ('gias06b','GIAS06B',(168,16,376,155),'3:2',
  'a shop front: a large white sign with big red Japanese characters and a smaller grey English line "RECYCLING & CARD SHOP" under them; below it, a narrow vertical red banner with the white letters "SALE"',
  'replace the big red Japanese characters with "RECICLAJE Y CARTAS" in the same bold red lettering; replace the grey line with "TIENDA DE RECICLAJE Y CARTAS" in the same small grey capitals; replace the vertical "SALE" with "OFERTAS" written vertically, one letter under another, in the same white letters on the red banner'),
 ('mayo01_2','MAYO01_2',(256,32,352,96),'3:2',
  'a small white wooden sign nailed to a rock face with a red arrow pointing left and grey Japanese characters above the arrow',
  'replace the Japanese characters with "Monte Panorama" in the same grey lettering, same size, above the same red arrow'),
 ('mayo11','MAYO11',(528,480,688,640),'1:1',
  'a weathered white notice board with a rusty frame, leaning on a rock: a red Japanese title written vertically at the right, black handwritten Japanese rules in vertical lines, and vandal scribbles over it (a blue wavy line, a drawn poop swirl, a red splat, and black scrawled words at the bottom)',
  'replace all the Japanese writing with Spanish written horizontally, in the same hand-painted styles and colours: the red title at the top "NORMAS DEL PESCADOR"; the black rules "1. No ensuciarás este lugar, que es de todos." and "2. No pescarás más de la cuenta."; and the vandal\'s black scrawl at the bottom "¡Bah! ¡Me da igual!". Keep the blue scribble, the poop drawing, the red splat, the rust stains and the frame as they are'),
 ('mayo10','MAYO10',(472,0,632,160),'1:1',
  'the same weathered white notice board with a rusty frame, seen from another angle: a red Japanese title written vertically at the right, black handwritten Japanese rules in vertical lines, and vandal scribbles over it (a blue wavy line, a drawn poop swirl, a red splat, and black scrawled words at the bottom)',
  'replace all the Japanese writing with Spanish written horizontally, in the same hand-painted styles and colours: the red title at the top "NORMAS DEL PESCADOR"; the black rules "1. No ensuciarás este lugar, que es de todos." and "2. No pescarás más de la cuenta."; and the vandal\'s black scrawl at the bottom "¡Bah! ¡Me da igual!". Keep the blue scribble, the poop drawing, the red splat, the rust stains and the frame as they are'),
 ('omoc08','OMOC08',(258,0,384,224),'9:16',
  'a white brick wall in a toy town with red spray-painted Japanese graffiti written vertically (a gang tag meaning "the gang was here")',
  'replace the Japanese graffiti with the Spanish tag "¡AQUÍ ESTUVO LA BANDA!" in the same red spray paint with drips, written in short lines down the wall in the same area'),
 ('trai00','TRAI00',(32,0,176,144),'1:1',
  'a large dark green signboard with a blue frame standing on grass, seen in perspective: a yellow sun emblem with a face on the left, and big Japanese characters in purple-blue and blue at the right',
  'replace the Japanese characters with the Spanish "CURSO DE COMBATE" (three lines: "CURSO", "DE", "COMBATE") in the same bold blue-purple lettering, following the board\'s perspective'),
 ('twnb_open','TWNB10',(100,136,172,184),'3:2',
  'a small white plate on a red wall with the black-and-red English text "WE\'RE OPEN" (small "WE\'RE" above a big red "OPEN")',
  'replace the text with the Spanish "ABIERTO" (small black "ESTAMOS" above a big red "ABIERTO")'),
 ('twnb_tool','TWNB10',(196,152,268,200),'3:2',
  'a small white plate on the floor with a black icon on the left and the black English text "TOOL SHOP" in two lines',
  'replace the text with the Spanish "FERRETERÍA" in two lines, "FERRE-" above "TERÍA", in the same black lettering; keep the icon'),
]
TEMPLATE = '''Image 1 is a crop of a pre-rendered 3D background from a 1990s PlayStation game: {desc}.

Edit only the lettering: {edit}. Match the original lettering's colour, stroke, weight, size, perspective and the slight blur of the low-resolution render, so the new text looks painted in the same scene.

Keep everything else identical: the shapes, positions, colours and textures of every object, the background, the lighting. No new effects, no glow beyond the original, no added shadows, no text anywhere else. Output the same framing and aspect ratio as image 1.
'''
