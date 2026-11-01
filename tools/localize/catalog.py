"""Reviewed short labels and artwork wording, translated from our Spanish set.

Order in each tuple: French, German, Italian, Japanese. Runtime source banks and
image-generation prompts share these spellings.
"""
LANGUAGES = ('fr', 'de', 'it', 'ja')
LANGUAGE_NAMES = {'en': 'ENGLISH', 'es': 'ESPAÑOL', 'pt-br': 'PORTUGUÊS', 'fr': 'FRANÇAIS',
                  'de': 'DEUTSCH', 'it': 'ITALIANO', 'ja': '日本語'}

SIGNS = {
 'betl02': ('COLISÉE', 'KOLOSSEUM', 'COLOSSEO', 'コロシアム'),
 'frzl06': ('Cap Iceberg / Bois Brumeux', 'Eisbergkap / Nebelwald', 'Capo Iceberg / Bosco Nebbioso', 'ひょうざん岬 / きりの森'),
 'gcan09': ('Boutique Monochrome / de tout', 'Monochrome-Laden / Allerlei', 'Negozio Monochrome / di tutto', 'モノクロショップ / なんでも'),
 'gias06b': ('RECYCLAGE ET CARTES / BOUTIQUE DE RECYCLAGE ET CARTES / PROMOS', 'RECYCLING UND KARTEN / RECYCLING- UND KARTENLADEN / ANGEBOTE', 'RICICLO E CARTE / NEGOZIO DI RICICLO E CARTE / OFFERTE', 'リサイクルとカード / リサイクル・カードショップ / お買い得'),
 'mayo01_2': ('Mont Panorama', 'Panoramaberg', 'Monte Panorama', 'パノラマ山'),
 'mayo10': ('RÈGLES DE PÊCHE / 1. Ne salissez pas cet endroit. Il est à tous. / 2. Ne pêchez pas trop. / Bah ! Je m\'en fiche !', 'ANGELREGELN / 1. Haltet diesen Ort sauber. Er ist für alle da. / 2. Fangt nicht zu viel. / Pah! Mir doch egal!', 'REGOLE DI PESCA / 1. Non sporcare. Questo posto è di tutti. / 2. Non pescare troppo. / Bah! Non mi importa!', 'つりのルール / 1. みんなの場所。よごさない。 / 2. つりすぎない。 / へん！ しるもんか！'),
 'mayo11': ('RÈGLES DE PÊCHE / 1. Ne salissez pas cet endroit. Il est à tous. / 2. Ne pêchez pas trop. / Bah ! Je m\'en fiche !', 'ANGELREGELN / 1. Haltet diesen Ort sauber. Er ist für alle da. / 2. Fangt nicht zu viel. / Pah! Mir doch egal!', 'REGOLE DI PESCA / 1. Non sporcare. Questo posto è di tutti. / 2. Non pescare troppo. / Bah! Non mi importa!', 'つりのルール / 1. みんなの場所。よごさない。 / 2. つりすぎない。 / へん！ しるもんか！'),
 'omoc08': ('LE GANG EST PASSÉ ICI !', 'DIE BANDE WAR HIER!', 'LA BANDA È PASSATA DI QUI!', 'オレたちのなわばり！'),
 'room02': ('Bienvenue', 'Willkommen', 'Benvenuto', 'ようこそ'),
 'trai00': ('COURS DE COMBAT', 'KAMPFKURS', 'CORSO DI COMBATTIMENTO', 'バトルこうざ'),
 'twnb_open': ('OUVERT', 'OFFEN', 'APERTO', '営業中'),
 'twnb_tool': ('OUTILS', 'WERKZEUG', 'ATTREZZI', 'どうぐ'),
 'audit-0': ('ACCUEIL', 'EMPFANG', 'RECEPTION', 'うけつけ'),
 'audit-1': ('INSCRIPTION', 'ANMELDUNG', 'ISCRIZIONI', 'さんか受付'),
 'audit-2': ('INSCRIPTION', 'ANMELDUNG', 'ISCRIZIONI', 'さんか受付'),
 'audit-3': ("SALLE D'ATTENTE", 'WARTERAUM', "SALA D'ATTESA", 'ひかえ室'),
 'audit-4': ('JEU DE GLACE', 'EISSPIEL', 'GIOCO SUL GHIACCIO', 'アイスゲーム'),
 'audit-5': ('VERS LE PUBLIC', 'ZUM PUBLIKUM', 'PER IL PUBBLICO', 'かんきゃく席へ'),
 'audit-7': ("DÉPÔT D'OBJETS", 'ITEMLAGER', 'DEPOSITO OGGETTI', 'どうぐあずかり所'),
 'audit-8': ("DÉPÔT D'OBJETS", 'ITEMLAGER', 'DEPOSITO OGGETTI', 'どうぐあずかり所'),
 'audit-9': ('RESTAURANT', 'RESTAURANT', 'RISTORANTE', 'レストラン'),
 'audit-10': ('OUTILS', 'WERKZEUG', 'ATTREZZI', 'どうぐ'),
 'audit-13': ('TUNNEL DE LA FOREUSE', 'BOHRTUNNEL', 'TUNNEL DEL TRAPANO', 'ドリルトンネル'),
 'mayo11_ogre': ("TUNNEL DE L'OGRE", 'OGERTUNNEL', "TUNNEL DELL'ORCO", 'オーガトンネル'),
 'audit-14': ('GYMNASE / VERT', 'GRÜNES / FITNESSSTUDIO', 'PALESTRA / VERDE', 'グリーン / ジム'),
 'audit-22': ('ATTENTION ! / CHUTES DE PIERRES !', 'VORSICHT! / STEINSCHLAG!', 'ATTENZIONE! / CADUTA MASSI!', '注意！ / らくせき！'),
 'audit-24': ('CACA PUBLIC', 'ÖFFENTLICHES KLO', 'CACCA PUBBLICA', 'みんなのウンチ'),
 'audit-27': ('ZONE DE REJET', 'ABWURFZONE', 'ZONA DI SCARTO', 'すてる場所'),
 'audit-28': ('BIEN !!', 'GUT!!', 'BENE!!', 'いいぞ！！'),
 'audit-29': ('BIEN !!', 'GUT!!', 'BENE!!', 'いいぞ！！'),
 'audit-30': ('RATÉ', 'SCHLECHT', 'MALE', 'だめ'),
 'audit-31': ('DANGER', 'GEFAHR', 'PERICOLO', 'きけん'),
}

# main logo, secondary logo, small lettering (all lettering in the reference is replaced).
CUPS = {
 'AN': (('ANIMAUX', 'COUPE', 'VENEZ TOUS ! ANIMAUX DEMI-DEMI'), ('TIER', 'POKAL', 'KOMMT ALLE! HALB UND HALB'), ('ANIMALE', 'COPPA', 'VENITE TUTTI! ANIMALI A METÀ'), ('どうぶつ', 'カップ', 'みんな あつまれ！ はんぶん どうぶつ')),
 'BT': (('SCARABÉE', 'COUPE', 'VENEZ TOUS ! COUPE SCARABÉE !!'), ('KÄFER', 'POKAL', 'KOMMT ALLE! KÄFERPOKAL!!'), ('SCARABEO', 'COPPA', 'VENITE TUTTI! COPPA SCARABEO!!'), ('カブト', 'カップ', 'みんな あつまれ！ カブトカップ！！')),
 'CO': (('STYLE', 'COUPE', 'QUI A LE PLUS DE STYLE ? VENEZ À LA COUPE STYLE'), ('STIL', 'POKAL', 'WER HAT DEN BESTEN STIL? KOMMT ZUM STILPOKAL'), ('STILE', 'COPPA', 'CHI HA PIÙ STILE? VENITE ALLA COPPA STILE'), ('おしゃれ', 'カップ', 'だれが いちばん おしゃれ？ みんな あつまれ')),
 'DT': (('CRASSE', 'COUPE', 'BEURK ! PARDON... QUELLE CRASSE ! VENEZ TOUS'), ('DRECK', 'POKAL', 'IGITT! VERZEIHUNG... SO EIN DRECK! KOMMT ALLE'), ('SPORCO', 'COPPA', 'BLEAH! SCUSATE... CHE SPORCO! VENITE TUTTI'), ('よごれ', 'カップ', 'うわっ！ ごめん... よごれだらけ！ みんな あつまれ')),
 'DY': (('DINO', 'COUPE', 'VENEZ TOUS !! COUPE DINOSAURE'), ('DINO', 'POKAL', 'KOMMT ALLE!! DINOSAURIERPOKAL'), ('DINO', 'COPPA', 'VENITE TUTTI!! COPPA DINOSAURO'), ('きょうりゅう', 'カップ', 'みんな あつまれ！！ きょうりゅうカップ')),
 'FR': (('FEU', 'COUPE', 'VENEZ TOUS, DIGIMON DE FEU !'), ('FEUER', 'POKAL', 'KOMMT ALLE, FEUER-DIGIMON!'), ('FUOCO', 'COPPA', 'VENITE TUTTI, DIGIMON DI FUOCO!'), ('ほのお', 'カップ', 'ほのおの デジモン みんな あつまれ！')),
 'GP': (('COMBAT', 'COUPE', 'QUI EST LE MEILLEUR COMBATTANT ?'), ('KAMPF', 'POKAL', 'WER IST DER BESTE KÄMPFER?'), ('LOTTA', 'COPPA', 'CHI È IL MIGLIOR LOTTATORE?'), ('かくとう', 'カップ', 'さいきょうの かくとうかは だれだ？')),
 'HU': (('HUMAINE', 'COUPE', 'VENEZ TOUS ! COUPE SEMI-HUMAINE'), ('MENSCHEN', 'POKAL', 'KOMMT ALLE! HALBMENSCHENPOKAL'), ('UMANA', 'COPPA', 'VENITE TUTTI! COPPA SEMIUMANI'), ('にんげん', 'カップ', 'みんな あつまれ！ はんぶん にんげん')),
 'MT': (('MÉTAL', 'COUPE', 'BLINDÉS, MACHINES, MÉTALLIQUES... QUI SERA LE NUMÉRO 1 ?'), ('METALL', 'POKAL', 'GEPANZERT, MASCHINELL, METALLISCH... WER WIRD NUMMER 1?'), ('METALLO', 'COPPA', 'CORAZZATI, MACCHINE, METALLICI... CHI SARÀ IL NUMERO 1?'), ('メタル', 'カップ', 'よろいに マシンに メタル... いちばんは だれ？')),
 'NT': (('NATURE', 'COUPE', 'LES INSECTES GÉANTS MARCHENT ! L\'HERBE BOUGE ! CHANTONS LA COUPE NATURE'), ('NATUR', 'POKAL', 'RIESENINSEKTEN MARSCHIEREN! DAS GRAS BEWEGT SICH! SINGT VOM NATURPOKAL'), ('NATURA', 'COPPA', 'GRANDI INSETTI IN MARCIA! L\'ERBA SI MUOVE! CANTIAMO LA COPPA NATURA'), ('しぜん', 'カップ', 'でっかい ムシが やってくる！ くさが うごく！ しぜんカップを うたおう')),
 'TW': (('TONNERRE ET VENT', 'COUPE', 'ÉLECTRIQUES / AILÉS / MULTI-QUEUES / VENT ET TONNERRE'), ('DONNER UND WIND', 'POKAL', 'ELEKTRISCH / GEFLÜGELT / VIELE SCHWÄNZE / WIND UND DONNER'), ('TUONO E VENTO', 'COPPA', 'ELETTRICI / ALATI / MOLTE CODE / VENTO E TUONO'), ('かみなりと かぜ', 'カップ', 'でんき / つばさ / たくさんの しっぽ / かぜと かみなり')),
 'WI': (('AILES', '~COUPE~', 'VENEZ TOUS ! COUPE DES AILÉS !'), ('FLÜGEL', '~POKAL~', 'KOMMT ALLE! POKAL DER GEFLÜGELTEN!'), ('ALI', '~COPPA~', 'VENITE TUTTI! COPPA DEGLI ALATI!'), ('つばさ', '～カップ～', 'みんな あつまれ！ つばさの カップ！')),
}

UI = {
 'PERFIL': ('PROFIL', 'PROFIL', 'PROFILO', 'プロフィール'),
 'ESTADO': ('ÉTAT', 'ZUSTAND', 'STATO', 'じょうたい'),
 'ATRIBUTOS': ('STATS', 'WERTE', 'VALORI', 'のうりょく'),
 'PESO': ('POIDS', 'GEW.', 'PESO', 'おもさ'),
 'TIPO': ('TYPE', 'TYP', 'TIPO', 'タイプ'),
 'OBJETOS': ('OBJETS', 'ITEMS', 'OGGETTI', 'どうぐ'), 'JUGADOR': ('JOUEUR', 'SPIELER', 'GIOCAT.', 'ひと'),
 'ALABAR': ('FÉLIC.', 'LOBEN', 'LODA', 'ほめる'), 'REÑIR': ('GRONDER', 'RÜGEN', 'SGRIDA', 'しかる'),
 'DORMIR': ('DORMIR', 'SCHLAF', 'DORMI', 'ねる'), 'PESCAR': ('PÊCHER', 'ANGELN', 'PESCA', 'つる'),
 'NOMBRE': ('NOM', 'NAME', 'NOME', 'なまえ'), 'ESPECIE': ('TYPE', 'ART', 'SPECIE', 'しゅるい'),
 'EDAD': ('ÂGE', 'ALTER', 'ETÀ', 'とし'), 'ACTIVO': ('ACTIF', 'AKTIV', 'ATTIVO', 'かつどう'),
 'ESPECIAL': ('SPÉCIAL', 'SPEZIAL', 'SPECIALE', 'とくい'),
 'FELICIDAD': ('BONHEUR', 'FREUDE', 'FELICITÀ', 'きげん'), 'VELOCIDAD': ('VITESSE', 'TEMPO', 'VELOCITÀ', 'すばやさ'),
 'INTELECTO': ('ESPRIT', 'KLUGHEIT', 'INGEGNO', 'かしこさ'), 'RAPIDEZ': ('VITESSE', 'TEMPO', 'VELOCITÀ', 'すばやさ'),
 'POTENCIA': ('FORCE', 'KRAFT', 'POTENZA', 'いりょく'), 'ALC.': ('PORT.', 'REICH.', 'RAG.', 'はんい'),
 'ALCANCE': ('PORTÉE', 'REICHW.', 'RAGGIO', 'はんい'), 'EFECTO': ('EFFET', 'EFFEKT', 'EFFETTO', 'こうか'),
 'DATOS TÉC.': ('TECH.', 'TECHNIK', 'TECNICA', 'わざ'), 'OBJETO': ('OBJET', 'ITEM', 'OGGETTO', 'どうぐ'),
 'PRECIO': ('PRIX', 'PREIS', 'PREZZO', 'ねだん'), 'TÍTULO': ('TITRE', 'TITEL', 'TITOLO', 'なまえ'),
 'LUGAR': ('LIEU', 'ORT', 'LUOGO', 'ばしょ'), 'PUNTOS': ('POINTS', 'PUNKTE', 'PUNTI', 'てん'),
 'CANT.': ('QTÉ', 'ANZ.', 'QTÀ', 'かず'), 'Nº': ('No', 'NR.', 'N.', 'ばん'),
 'FUEGO': ('FEU', 'FEUER', 'FUOCO', 'ほのお'), 'COMBATE': ('COMBAT', 'KAMPF', 'LOTTA', 'かくとう'),
 'AIRE': ('AIR', 'LUFT', 'ARIA', 'くうき'), 'TIERRA': ('TERRE', 'ERDE', 'TERRA', 'だいち'),
 'HIELO': ('GLACE', 'EIS', 'GELO', 'こおり'), 'MECA': ('MÉCA', 'MECHA', 'MECCA', 'きかい'),
 'MUGRE': ('CRASSE', 'DRECK', 'SPORCO', 'よごれ'),
}


def word(spanish, language):
    values = UI.get(spanish)
    return values[LANGUAGES.index(language)] if values and language in LANGUAGES else spanish

# Catalan is appended to preserve every earlier language's tuple/save index.
CA_SIGNS = {
 'betl02':'COLISEU','frzl06':'Cap Iceberg / Bosc Boirós',
 'gcan09':'Botiga Monocroma / de tot','gias06b':'RECICLATGE I CARTES / BOTIGA DE RECICLATGE I CARTES / OFERTES',
 'mayo01_2':'Mont Panorama',
 'mayo10':"NORMES DE PESCA / 1. No embruteu aquest lloc. És de tothom. / 2. No pesqueu massa. / Bah! Tant me fa!",
 'mayo11':"NORMES DE PESCA / 1. No embruteu aquest lloc. És de tothom. / 2. No pesqueu massa. / Bah! Tant me fa!",
 'omoc08':'LA COLLA HA PASSAT PER AQUÍ!','room02':'Benvinguts','trai00':'CURS DE COMBAT',
 'twnb_open':'OBERT','twnb_tool':'EINES','audit-0':'RECEPCIÓ','audit-1':'INSCRIPCIONS','audit-2':'INSCRIPCIONS',
 'audit-3':"SALA D'ESPERA",'audit-4':'JOC DE GEL','audit-5':'CAP AL PÚBLIC',
 'audit-7':"MAGATZEM D'OBJECTES",'audit-8':"MAGATZEM D'OBJECTES",'audit-9':'RESTAURANT','audit-10':'EINES',
 'audit-13':'TÚNEL DEL TREPANT', 'mayo11_ogre':"TÚNEL DE L'OGRE",
 'audit-14':'GIMNÀS / VERD','audit-22':'ATENCIÓ! / CAIGUDA DE PEDRES!',
 'audit-24':'CACA PÚBLICA','audit-27':'ZONA DE REBUIG','audit-28':'BÉ!!','audit-29':'BÉ!!',
 'audit-30':'MALAMENT','audit-31':'PERILL',
}
CA_CUPS = {
 'AN':('ANIMALS','COPA','VENIU TOTS! ANIMALS A MITGES'),
 'BT':('ESCARABAT','COPA','VENIU TOTS! COPA ESCARABAT!!'),
 'CO':('ESTIL','COPA',"QUI TÉ MÉS ESTIL? VENIU A LA COPA ESTIL"),
 'DT':('BRUTÍCIA','COPA','ECS! PERDÓ... QUINA BRUTÍCIA! VENIU TOTS'),
 'DY':('DINO','COPA','VENIU TOTS!! COPA DINOSAURE'),
 'FR':('FOC','COPA','VENIU TOTS, DIGIMON DE FOC!'),
 'GP':('COMBAT','COPA','QUI ÉS EL MILLOR LLUITADOR?'),
 'HU':('HUMANA','COPA','VENIU TOTS! COPA SEMIHUMANA'),
 'MT':('METALL','COPA','BLINDATS, MÀQUINES, METÀL·LICS... QUI SERÀ EL NÚMERO 1?'),
 'NT':('NATURA','COPA',"ELS INSECTES GEGANTS AVANCEN! L'HERBA ES MOU! CANTEM LA COPA NATURA"),
 'TW':('TRO I VENT','COPA','ELÈCTRICS / ALATS / MOLTES CUES / VENT I TRO'),
 'WI':('ALES','~COPA~','VENIU TOTS! COPA DELS ALATS!'),
}
CA_UI = {
 'PERFIL':'PERFIL','ESTADO':'ESTAT','ATRIBUTOS':'ATRIBUTS','PESO':'PES','TIPO':'TIPUS',
 'OBJETOS':'OBJECTES','JUGADOR':'JUGADOR','ALABAR':'LLOAR','REÑIR':'RENYAR','DORMIR':'DORMIR','PESCAR':'PESCAR',
 'NOMBRE':'NOM','ESPECIE':'ESPÈCIE','EDAD':'EDAT','ACTIVO':'ACTIU','ESPECIAL':'ESPECIAL',
 'FELICIDAD':'FELICITAT','VELOCIDAD':'VELOCITAT','INTELECTO':'INTEL·LECTE','RAPIDEZ':'RAPIDESA',
 'POTENCIA':'POTÈNCIA','ALC.':'ABAST','ALCANCE':'ABAST','EFECTO':'EFECTE','DATOS TÉC.':'TÈCNIQUES',
 'OBJETO':'OBJECTE','PRECIO':'PREU','TÍTULO':'TÍTOL','LUGAR':'LLOC','PUNTOS':'PUNTS','CANT.':'QUANT.','Nº':'NÚM.',
 'FUEGO':'FOC','COMBATE':'COMBAT','AIRE':'AIRE','TIERRA':'TERRA','HIELO':'GEL','MECA':'MECA','MUGRE':'BRUTÍCIA',
}
assert set(CA_SIGNS) == set(SIGNS)
assert set(CA_CUPS) == set(CUPS)
assert set(CA_UI) == set(UI)
SIGNS = {key: values + (CA_SIGNS[key],) for key, values in SIGNS.items()}
CUPS = {key: values + (CA_CUPS[key],) for key, values in CUPS.items()}
UI = {key: values + (CA_UI[key],) for key, values in UI.items()}
LANGUAGES += ('ca',)
LANGUAGE_NAMES['ca'] = 'CATALÀ'
