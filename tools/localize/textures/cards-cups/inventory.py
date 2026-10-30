# kind: T = English text line (redraw), L = Japanese katakana logo art (image generator), A = Latin art letter/numeral (keep)
G6=lambda logo,letter:[('L',(4,0,250,62),logo,'CATEGORÍA %s (logo)'%letter if letter else ''),
  ('T',(25,66,213,9),'the DIGITALMONSTER COLISEUM','el COLISEO DIGITALMONSTER'),
  ('T',(57,81,132,9),'OPEN TOURNAMENT','TORNEO ABIERTO')]
INV={}
for L in 'DCBA':
    INV['GRADE'+L]=G6('グレード'+L,L)+[('T',(76,96,90,18),'* GRADE %s *'%L,'· CATEGORÍA %s ·  (drawn; %s art kept and moved)'%(L,L))]
INV['GRADES']=G6('グレードS','SÚPER')+[('T',(80,95,92,19),'* SUPER GRADE * (big S art + UPER + GRADE)','· SUPER / CATEGORÍA ·  (S art kept; UPER kept; GRADE -> CATEGORÍA)')]
INV['GRADER']=G6('グレードR','REAL')+[('T',(80,94,88,22),'* ROYAL GRADE * (big R art + OYAL + GRADE)','· R+EAL / CATEGORÍA ·  (R art kept; OYAL -> EAL; GRADE -> CATEGORÍA)')]
for n in '1234O':
    k='CAPV'+n; v='0' if n=='O' else n
    INV[k]=[('T',(78,30,22,14),'for','solo'),('T',(60,44,60,13),'LIMIT of','DIGIMON de'),
            ('T',(18,57,104,17),'ver %s DIGIMON'%v,'la ver %s'%v),
            ('A',(112,8,112,88) if n!='O' else (112,24,116,64),'V%s (brick V + pipe numeral)'%v,'keep (version mark)'),
            ('T',(94,95,60,17),'~CUP~','~COPA~')]
INV['CAPVO'].insert(3,('T',(36,74,41,10),'RIGINAL (ver 0RIGINAL)','RIGINAL (same in Spanish: 0RIGINAL)'))
INV['FR']=[('L',(10,4,192,100),'ファイア (Fire)','FUEGO'),('T',(96,69,74,25),'CUP (red serif)','COPA'),
  ('T',(136,55,116,56),'COME / TOGETHER / BURNING / DIGIMON\'s','¡VENID, / TODOS, / DIGIMON / DE FUEGO!  (drawn)')]
INV['GP']=[('T',(31,2,186,14),'WHO\'s FIRST GRAPPLER ?','¿QUIÉN ES EL MEJOR LUCHADOR?'),('L',(12,12,234,52),'グラップル (Grapple)','LUCHA'),
  ('T',(62,58,114,38),'CUP (chrome)','COPA')]
INV['TW']=[('L',(12,4,206,106),'サンダウインド / 風雷 (Thunder Wind)','TRUENO Y VIENTO'),('T',(144,33,74,27),'CUP','COPA'),
  ('T',(148,58,74,36),'3 lines mostly hidden under the logo (…ELECTRIC… / …WINGS… / …MULTIPLATES…?)','leave, or 3 Spanish lines under the logo (unreadable either way)'),
  ('T',(74,93,94,24),'WIND&THUNDER / CUP','VIENTO Y TRUENO / COPA')]
INV['CO']=[('L',(22,14,180,68),'クール (Cool)','GUAY'),('T',(178,17,64,30),'CUP','COPA'),
  ('T',(66,78,124,11),'WHO\'s a MOST COOLER ?','¿QUIÉN ES EL MÁS GUAY?'),('T',(66,88,126,11),'COME COME TOGETHER','VENID, VENID TODOS'),
  ('T',(98,97,64,12),'the "COOL" CUP','la COPA "GUAY"')]
INV['NT']=[('L',(18,10,216,58),'ネイチャー (Nature)','NATURALEZA'),('T',(94,55,100,36),'CUP','COPA'),
  ('T',(22,70,120,10),'MOVING BIG INSECT\'s!','¡GRANDES INSECTOS EN MARCHA!'),('T',(22,79,120,10),'MOVING GRASS… (part hidden)','¡LA HIERBA SE MUEVE!'),
  ('T',(22,88,152,12),'SING TOGETHER NATURE CUP','CANTAD JUNTOS: COPA NATURALEZA')]
INV['MT']=[('L',(20,22,210,56),'メタリック (Metallic)','METÁLICA'),('T',(38,75,74,32),'CUP (chrome)','COPA'),
  ('T',(114,72,106,35),'ARMER\'s / MACHINERY\'s / METALER\'s…','BLINDADOS, / MÁQUINAS, / METÁLICOS…'),('T',(42,105,176,13),'WHO\'s FIRST DIGIMON?','¿QUIÉN SERÁ EL Nº 1?')]
INV['DT']=[('L',(12,4,202,74),'ダーティ (Dirty)','SUCIA'),('T',(50,63,62,24),'CUP','COPA'),
  ('T',(106,55,130,50),'AAGH..GHA… SORRY / …K SO… DIRTY / …ES..COME TOGETHER / "CRAPPER\'s" CUP','¡PUAJ! PERDÓN… / ¡QUÉ SUCIOS! / VENID TODOS / LA COPA "GUARRA"')]
INV['DY']=[('L',(36,4,202,64),'ダイノ (Dino)','DINO'),('T',(82,68,82,30),'CUP','COPA'),
  ('T',(64,94,124,12),'COME TUGETHER !!','¡¡VENID TODOS!!'),('T',(68,104,112,12),'DINOSAUR\'s CUP','COPA DINOSAURIO')]
INV['WI']=[('L',(12,4,226,70),'ヴイング (Wing)','ALAS'),('T',(138,65,100,29),'~CUP~','~COPA~'),
  ('T',(20,58,146,36),'COME / TOGETHER / HAVE a WING\'s CUP','VENID / TODOS / ¡COPA DE LOS ALADOS!')]
INV['AN']=[('L',(14,14,232,60),'アニマル (Animal)','ANIMAL'),('T',(38,66,72,30),'CUP','COPA'),
  ('T',(82,81,156,12),'(CO)ME COME TOGETHER','VENID, VENID TODOS'),('T',(92,92,120,12),'DEMI DEMI ANIMAL\'s','DEMI DEMI ANIMALES')]
INV['HU']=[('L',(38,8,192,54),'ヒューマン (Human)','HUMANA'),('T',(98,49,86,30),'cup (script)','copa'),
  ('T',(56,75,116,12),'COME TOGETHER','VENID TODOS'),('T',(56,86,128,14),'DEMIHUMAN\'s CUP','COPA SEMIHUMANOS')]
INV['BT']=[('L',(36,0,194,96),'ビートル (Beetle)','ESCARABAJO'),('T',(92,79,68,24),'CUP','COPA'),
  ('T',(60,95,132,13),'COME TOGETHER','VENID TODOS'),('T',(64,106,126,13),'BEETLE\'s CUP !!','¡¡COPA ESCARABAJO!!')]
ORDER='GRADED GRADEC GRADEB GRADEA GRADES GRADER CAPV1 CAPV2 CAPV3 CAPV4 CAPVO FR GP TW CO NT MT DT DY WI AN HU BT'.split()
