"""Observe the real GPU quad relative to the condition-ring anchor on 2 MB.

The fixture holds the partner root and icon clock at identical values across
executables. It never replaces a renderer or a GPU packet.
"""
import json


def capture(e, path, expected):
    code = r'''
      CARE_PIXEL={active=false,done=false,packet=nil}
      local m=PCSX.getMemPtr()
      local function u8(a) return tonumber(m[a]) end
      local function u16(a) return u8(a)+256*u8(a+1) end
      local function u32(a) return u16(a)+65536*u16(a+2) end
      local function s16(a) local v=u16(a);return v>=32768 and v-65536 or v end
      local function w32(a,v)
        v=v%4294967296
        for i=0,3 do m[a+i]=v%256;v=math.floor(v/256) end
      end
      local tp=u32(@TAMER@+4)-2147483648
      local pp=u32(@PARTNER@+4)-2147483648
      assert(tp>=0 and tp+0x84<=2097152 and pp>=0 and pp+0x84<=2097152,
        'invalid field entity position data')
      local x=u32(tp+0x78)+100
      local y=u32(tp+0x7c)
      local z=u32(tp+0x80)
      CARE_PIXEL.entry=PCSX.addBreakpoint(@ENTRY@,'Exec',4,'care-pixel-entry',function()
        w32(@CLOCK@,100)
        w32(pp+0x78,x);w32(pp+0x7c,y);w32(pp+0x80,z)
        if CARE_PIXEL.done then return end
        CARE_PIXEL.active=true;CARE_PIXEL.packet=nil
        if not CARE_PIXEL.ret then
          local ra=tonumber(PCSX.getRegisters().GPR.n.ra)
          CARE_PIXEL.ret=PCSX.addBreakpoint(ra,'Exec',4,'care-pixel-return',function()
            if not CARE_PIXEL.active then return end
            CARE_PIXEL.active=false
            local q=CARE_PIXEL.packet
            if q then
              local ax=s16(@SHOWN@+16);local ay=s16(@SHOWN@+18)
              CARE_PIXEL.json=string.format(
                '{"x":%d,"y":%d,"dx":%d,"dy":%d,"w":%d,"h":%d,"anchor_x":%d,"anchor_y":%d,"clut":%d,"clock":%d}',
                q[1],q[2],q[1]-ax,q[2]-ay,q[3]-q[1],q[4]-q[2],ax,ay,q[5],u32(@CLOCK@))
            else CARE_PIXEL.json='null' end
            CARE_PIXEL.done=true
          end)
        end
      end)
      CARE_PIXEL.gpu=PCSX.addBreakpoint(@WORK@,'Exec',4,'care-pixel-quad',function()
        if not CARE_PIXEL.active then return end
        local p=tonumber(PCSX.getRegisters().GPR.n.a0)-40
        if p<2147483648 or p+40>2149580800 then return end
        p=p-2147483648
        if u8(p+3)==9 and u8(p+7)==46 and u16(p+22)==37 then
          CARE_PIXEL.packet={s16(p+8),s16(p+10),s16(p+16),s16(p+26),u16(p+14)}
        end
      end)
    '''
    for key, symbol, physical in [
        ('TAMER', 'TAMER_ENTITY', True), ('PARTNER', 'PARTNER_ENTITY', True),
        ('CLOCK', 'MOD_RING_CLOCK', True), ('SHOWN', 'MOD_RING_SHOWN', True),
        ('ENTRY', 'renderConditionRingObject', False), ('WORK', 'GsSetWorkBase', False),
    ]:
        address = e.A(symbol)
        code = code.replace('@'+key+'@', str(address & 0x1fffff if physical else address))
    try:
        response = e.run('lua', code)
        assert not response.startswith('error:'), response
        for _ in range(100):
            if e.run('lua', 'return CARE_PIXEL.done').strip() == 'true':
                break
            e.wait(.1)
        else:
            raise AssertionError('condition-ring renderer did not finish')
        result = json.loads(e.run('lua', 'return CARE_PIXEL.json').strip())
        assert bool(result) == expected, (expected, result)
        e.wait(.2)
        e.run('shot', str(path))
        return result
    finally:
        e.run('lua', '''if CARE_PIXEL then
          for _,name in ipairs({'entry','ret','gpu'}) do
            if CARE_PIXEL[name] then CARE_PIXEL[name]:remove() end
          end
          CARE_PIXEL=nil
        end''')


def compare(reference, restored):
    """Require identical emitted GPU pixel offsets, sizes and bubble slots."""
    assert reference['ram_bytes'] == restored['ram_bytes'] == 2097152
    assert reference['ram_probe'] == restored['ram_probe'] == 0
    assert reference['cases'].keys() == restored['cases'].keys()
    rows = []
    for name, old in reference['cases'].items():
        new = restored['cases'][name]
        assert old['condition'] == new['condition'], name
        assert old['from'] == new['from'], name
        a, b = old['badge_pixels'], new['badge_pixels']
        assert bool(a) == bool(b), name
        if a:
            assert a['clock'] == b['clock'], name
            keys = ('dx', 'dy', 'w', 'h')
            expected = [a[k] for k in keys]
            actual = [b[k] for k in keys]
            assert expected == actual, (name, expected, actual)
        else:
            expected = actual = None
        rows.append({'case': name, 'v006': expected, 'restored': actual})
    return rows


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=compare.__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('restored', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    rows = compare(json.loads(args.reference.read_text()), json.loads(args.restored.read_text()))
    if args.out:
        args.out.write_text(json.dumps(rows, indent=2)+'\n')
    print(f'PASS: {len(rows)} cases; identical GPU (dx, dy, width, height) and condition slots')
    for row in rows:
        print(row['case'], row['restored'])
