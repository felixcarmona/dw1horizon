#!/usr/bin/env python3
"""Dump final locomotion sound events and render their routed tones for listening.

Use --species DIR with the final provider species records (after overlays), and
--out build/steps. Original samples and rendered audio stay in ignored build/.
The renderer approximates pitch, ADSR and gain; it omits reverb and the engine's
14-voice round robin. Animation note is an effect ID for banks 0/1/8.
"""
import argparse
import hashlib
import json
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import animsheet
import mmd
import sound
import species


def route(bank, note):
    return (note // 16, 60 + note % 16) if bank in (0, 1, 8) else (0, note)


def tones(vab, bank, note):
    program, key = route(bank, note)
    rows = []
    # startSound selects by max == key, not a MIDI key-range lookup.
    for t in vab.tones_of(program):
        if t['max'] != key:
            continue
        raw = vab.vags[t['vag'] - 1]
        pcm, loop, end = sound.adpcm_decode(raw, with_loop=True)
        rate = sound.note_rate(t, key)
        rows.append(dict(program=program, key=key, sample=t['vag'],
                         root=sound.tone_pitch(t), semitones=key-sound.tone_pitch(t),
                         tone_volume=t['vol'], program_volume=vab.progs[program]['mvol'],
                         adsr1=t['adsr1'], adsr2=t['adsr2'], bytes=len(raw),
                         pcm_samples=len(pcm), end_sample=end, loop_sample=loop,
                         rate=rate, seconds=(end or len(pcm))/rate,
                         sample_sha256=hashlib.sha256(raw).hexdigest()))
    return rows


def audit_record(record):
    record = dict(record, _path='audit')
    raw, _ = species.species_model(record)
    sid = record['id']
    sk = record['model'].get('skeleton') or mmd.exe().skeleton[sid]
    if sk is None:
        raise ValueError(f'{sid}: no skeleton')
    model = mmd.MMD.parse(raw, len(sk))
    clips = {}
    for slot in (2, 3, 4):
        frames, loop, events = animsheet.slot_frames(model, len(sk), slot)
        period = len(frames) - 1
        cues = [dict(tick=t, bank=i['bank'], note=i['note'])
                for t, kind, i in events if kind == 'sound']
        times = [c['tick'] for c in cues]
        gaps = [b-a for a,b in zip(times, times[1:] + ([times[0]+period] if times else []))]
        clips[str(slot)] = dict(period=period, loop=loop, count=len(cues),
                                events=cues, min_gap_ticks=min(gaps) if gaps else None,
                                events_per_second=20*len(cues)/period if period else None)
    return dict(id=sid, name=record['name'], partner_voice=record.get('partner', {}).get('voice'), voice=record.get('voice'), model_sha256=hashlib.sha256(raw).hexdigest(), clips=clips)


def render(vab, bank, note, ticks, out, seconds):
    """Wrap the unchanged VAB as a temporary font for sound.py's SPU renderer."""
    program, key = route(bank, note)
    # Keep only max-matching tones, exactly as startSound does.
    import copy
    vab = copy.deepcopy(vab)
    for t in vab.tones_of(program):
        if t['max'] != key:
            t['min'] = t['max'] = 127
    timeline = [(0, 0xC0, bytes([program]))]
    timeline += [(round(t*50), 0x90, bytes([key,127])) for t in ticks]
    timeline.append((round(seconds*1000)+1000, 0xFF, b'\x2f'))
    timeline.sort(key=lambda e:e[0])
    last=0; events=[]
    for at, status, data in timeline:
        events.append((at-last,status,data));last=at
    chunk = object.__new__(sound.Chunk)
    chunk.nhdr=4;chunk.vab=vab
    chunk.seqs=[sound.Seq.build(1, 1000, 1000000, [4,2], events)]
    with tempfile.TemporaryDirectory(prefix='step-font-', dir=out.parent) as tmp:
        font = Path(tmp)/'FAALL.VHB'
        raw = chunk.build()
        font.write_bytes(raw+bytes(-len(raw)%(39*2048)))
        pcm, rate = sound.render(1,0,seconds,str(font))
    with wave.open(str(out),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--species',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--render',type=int,nargs='*',default=[])
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    banks={1:sound.VhbFile(sound.resolve('SL')).chunks[0].vab,
           0:sound.VhbFile(sound.resolve('SS')).chunks[0].vab}
    records=[json.loads(f.read_text()) for f in sorted(a.species.glob('*.json'))]
    rows=[audit_record(r) for r in records]
    tone_rows = {}; unresolved = set()
    vlall = sound.VhbFile(sound.resolve('VLALL'))
    vball = sound.VhbFile(sound.resolve('VBALL'))
    for row in rows:
        for clip in row['clips'].values():
            for cue in clip['events']:
                bank, note = cue['bank'], cue['note']
                vab = banks.get(bank)
                chunk = row['partner_voice'] if bank == 3 else row['voice']
                key = f'{bank}:{note}'
                if bank in (3, 4) and chunk is not None:
                    vab = (vlall if bank == 3 else vball).chunks[chunk].vab
                    key = f'{bank}/{chunk}:{note}'
                cue['tone_route'] = key
                if vab is None:
                    unresolved.add(bank)
                elif key not in tone_rows:
                    tone_rows[key] = tones(vab, bank, note)
    result=dict(logic_hz=20, rows=rows, tones=tone_rows,
                unresolved_banks=sorted(unresolved),
                bank3_context='Partner VLALL assumed; NPC bank 3 uses the current partner bank')
    (a.out/'events.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['id,name,slot,cycle_ticks,count,tick,bank,effect_id,tone_route,program,key,sample,seconds,loop_sample']
    for r in rows:
        for slot,c in r['clips'].items():
            for e in c['events']:
                for t in (tone_rows.get(e['tone_route']) or [{}]):
                    lines.append(','.join(map(str,[r['id'],r['name'],slot,c['period'],c['count'],e['tick'],e['bank'],e['note'],e['tone_route'],t.get('program'),t.get('key'),t.get('sample'),t.get('seconds'),t.get('loop_sample')])))
        if r['id'] in a.render:
            cues=r['clips']['2'];period=cues['period']
            for bank,note in sorted({(c['bank'],c['note']) for c in cues['events']}):
                if bank not in banks:continue
                stem=f"{r['id']}-{r['name']}-bank{bank}-effect{note}"
                render(banks[bank],bank,note,[0],a.out/f'{stem}-single.wav',4)
                ticks=[e['tick']+k*period for k in range(1+100//period) for e in cues['events'] if (e['bank'],e['note'])==(bank,note)]
                render(banks[bank],bank,note,ticks,a.out/f'{stem}-walk.wav',6)
    print(f'{len(rows)} species; {len(tone_rows)} tone routes; unresolved banks: {result["unresolved_banks"]}')


if __name__=='__main__':
    main()
