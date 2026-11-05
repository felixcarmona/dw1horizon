"""Place Chinese label constituents at their existing runtime crop boundaries."""
import re

# (source word groups, crop starts); slots are original four-pixel font cells.
ROWS = {
 'kar.KAR_D_8005ABB8':([1,1],[0,84]),
 'main.MAIN_D_801238A0':([1,1],[0,60]),
 'main.MAIN_D_801238B0':([1]*6,[24,72,120,156,180,204]),
 'main.MAIN_D_801238D8':([1]*5,[0,48,96,144,192]),
 'main.MAIN_D_80123900':([1]*3,[0,72,108]),
 'main.MAIN_D_80123914':([1,1],[0,48]),
 'main.MAIN_D_80123920':([1,2],[0,12]),
 'main.MAIN_D_80123938':([1]*4,[0,32,76,124]),
 'main.MAIN_D_8012394C':([1,1],[0,12]),
 'main.MAIN_D_80123958':([1]*4,[0,36,72,108]),
 'main.MAIN_D_80123A18':([1]*5,[0,24,60,96,132]),
 'main.MAIN_D_80123A60':([1]*3,[0,56,120]),
 'main.MAIN_D_80123A7C':([1,1],[0,96]),
 'main.MAIN_D_80123A98':([1,1],[0,84]),
 'main.MAIN_D_80123A3C':([2,1,1,1,1],[0,108,120,132,180]),
 'main.MAIN_D_80123AB0':([1,1,1],[0,72,132]),
 'main.MAIN_D_80123AD0':([1,1],[0,72]),
 'main.MAIN_D_80123AE4':([1]*4,[0,40,88,204]),
 'main.MAIN_D_80123B10':([1,1],[0,52]),
 'shop.MAIN_D_801307CC':([1,1],[0,68]),
 'main.STR_YEAR_DAY':([1,1],[0,36]),
 'main.STR_YES_NO':([1,1],[0,28]),
 'main.STR_YES_NO_SPACED':([1,1],[0,28]),
}


def cell_width(text):
    from dws.bytecode import CHARWIDTH
    return sum(CHARWIDTH.get(char,12) if ord(char) < 128 or char in '○□△×' else 12 for char in text)


def align(key, text):
    if key not in ROWS:return text
    groups, starts = ROWS[key]
    words = text.split()
    if len(words) != sum(groups):
        raise ValueError(f'{key}: Chinese packed labels changed their constituent count')
    out, pos, at = '',0,0
    for count,start in zip(groups,starts):
        word = ''.join(words[at:at+count]);at += count
        if pos > start or (start-pos)%4:
            raise ValueError(f'{key}: Chinese packed label overlaps its next crop')
        out += ' '*((start-pos)//4)+word
        pos = start+cell_width(word)
    return out
