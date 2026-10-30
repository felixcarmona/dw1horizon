# SPDX-License-Identifier: MIT
"""Regression tests for GPU transparency, packing and collision false passes.

Run: build/sam-venv/bin/python -m unittest discover -s tools/maps -p 'test_*.py'
No checkpoint, disc, network or emulator required.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from tools.image import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cutout
import reach


def tim8(width=64,height=64):
    return (struct.pack('<II',16,9)+struct.pack('<I4H',524,0,484,256,1)+bytes(512)+
            struct.pack('<I4H',12+width*height,384,0,width//2,height)+bytes(width*height))


def map_stub():
    return SimpleNamespace(collision=[128]*10000,warps=[],tims=[tim8()],sprites=[],instances=[])


class PaletteTests(unittest.TestCase):
    def tfs(self, palettes, rows):
        return SimpleNamespace(cluts=palettes,tiles=[(0,bytes(np.array(rows,dtype='uint8').flatten()))],
                               image_indices=lambda m:(2,2,rows))

    def test_black_alias_preserves_day_and_night(self):
        rows=[[0,1],[2,0]]; palettes=[[0,31,1024]+[0]*253,[0,10,200]+[0]*253]
        t=self.tfs(palettes,rows);mask=np.ones((2,2),bool)
        idx,aliases=cutout.palette_indices(SimpleNamespace(tiles=[0],width=1),t,{'a':mask})
        self.assertEqual(aliases,{0:3})
        for p in t.cluts:self.assertEqual(p[3],0x8000)
        self.assertTrue(np.all(idx[mask]>0));self.assertEqual(idx[0,1],1)

    def test_alias_must_match_every_palette(self):
        rows=[[0,1],[2,0]];palettes=[[0,31,1024,0x8000]+[0]*252,[0,10,200,31]+[0]*252]
        t=self.tfs(palettes,rows)
        _,aliases=cutout.palette_indices(SimpleNamespace(tiles=[0],width=1),t,{'a':np.ones((2,2),bool)})
        self.assertEqual(t.cluts[1][aliases[0]],0x8000)

    def test_palette_alias_preserves_existing_background_clut_animation(self):
        m=map_stub();m.tiles=[0];m.width=1
        raw=bytearray(m.tims[0]);raw[8+524+12]=3;m.tims=[bytes(raw)]
        m.sprites=[dict(texX=0,texY=0,width=2,height=2,clut=-1)]
        m.instances=[dict(flag=0,frames=[0]+[-1]*7)]
        rows=[[0,1],[2,0]];palettes=[[0,31,1024]+[0]*253]
        t=self.tfs(palettes,rows)
        _,aliases=cutout.palette_indices(m,t,{'a':np.ones((2,2),bool)})
        self.assertEqual(aliases[0],4);self.assertEqual(t.cluts[0][3],0)
        t=self.tfs([[0,31,1024]+[0]*253],rows)
        _,aliases=cutout.palette_indices(m,t,{'a':np.ones((2,2),bool)},hidden_instances=[0])
        self.assertEqual(aliases[0],3)

    def test_exhausted_palette_fails(self):
        rows=np.arange(256,dtype='uint8').reshape(16,16).tolist()
        t=self.tfs([list(range(256))],rows)
        with self.assertRaisesRegex(ValueError,'unused palette'):
            cutout.palette_indices(SimpleNamespace(tiles=[0],width=1),t,{'a':np.ones((16,16),bool)})

    def test_missing_donor_tile_fails(self):
        with self.assertRaisesRegex(ValueError,'missing background'):
            cutout.palette_indices(SimpleNamespace(tiles=[-1],width=1),self.tfs([[0]+[31]*255],[[1]*2]*2),{'a':np.ones((2,2),bool)})


class PackingTests(unittest.TestCase):
    def cfg(self):
        return dict(packing=[dict(tim=0,x=0,y=0,width=64,height=64)],chunk_size=16,
                    objects=[dict(name='post',depth_world=[1,0,2])])

    def test_packed_pixels_and_zero_guards(self):
        m=map_stub();cfg=self.cfg();mask=np.zeros((32,32),bool);mask[2:27,4:12]=True
        before=len(m.tims[0]);places=cutout.pack(m,cfg,{'post':mask},np.ones((32,32),dtype='uint8')*7)
        self.assertEqual(len(m.tims[0]),before)
        tim=cutout.dwmap.TIM(m.tims[0]);pixels=np.frombuffer(tim.pixels,np.uint8).reshape(64,64)
        self.assertEqual(int((pixels==7).sum()),int(mask.sum()))
        self.assertTrue(np.all(pixels[0]==0));self.assertEqual(len(places),len(m.sprites))
        self.assertTrue(all(s['clut']==-1 and s['transparency']==4 for s in m.sprites))

    def test_vram_overflow_is_failure(self):
        m=map_stub();cfg=self.cfg();cfg['packing'][0].update(width=8,height=8)
        with self.assertRaisesRegex(ValueError,'space exhausted'):
            cutout.pack(m,cfg,{'post':np.ones((32,32),bool)},np.ones((32,32),dtype='uint8'))

    def test_overlapping_areas_fail(self):
        cfg=self.cfg();cfg['packing']*=2
        with self.assertRaisesRegex(ValueError,'overlapping'):
            cutout.pack(map_stub(),cfg,{'post':np.ones((2,2),bool)},np.ones((2,2),dtype='uint8'))

    def test_preserved_animation_cannot_be_overwritten(self):
        m=map_stub();m.sprites=[dict(texX=0,texY=0,width=8,height=8)]
        for flag in (0,128):
            m.instances=[dict(flag=flag,frames=[0]+[-1]*7)]
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError,'preserved sprite'):
                cutout.pack(m,self.cfg(),{'post':np.ones((2,2),bool)},np.ones((2,2),dtype='uint8'))

    def test_rectangular_frame_mask_rejected(self):
        self.assertTrue(cutout.rectangle_errors(np.ones((40,60),bool),'bad'))
        mask=np.zeros((40,60),bool);mask[4:35,25:29]=True;mask[8:11,10:50]=True
        self.assertFalse(cutout.rectangle_errors(mask,'cross'))


class CheckSabotageTests(unittest.TestCase):
    def test_black_box_alpha_and_transparency_are_detected(self):
        m=map_stub();mask=np.zeros((32,32),bool)
        mask[3:18,5:15]=True;mask[7:12,8:12]=False
        obj=dict(name='post',depth_world=[0,0,0],tiles=dict(behind=[],blocked=[]))
        cfg=dict(objects=[obj],chunk_size=32,packing=[dict(tim=0,x=0,y=0,width=64,height=64)])
        places=cutout.pack(m,cfg,{'post':mask},np.ones((32,32),dtype='uint8')*7)
        pal=[0]+[31]*255
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);np.savez_compressed(out/'masks.npz',post=mask)
            rgba=np.zeros((32,32,4),dtype='uint8');rgba[:,:,3]=mask*255
            Image.fromarray(rgba).save(out/'post.png')
            (out/'placements.json').write_text(json.dumps(places));(out/'candidate.TFS').write_bytes(b'')
            with patch.object(cutout.dwmap,'camera_basis',return_value=([0]*3,)*4), patch.object(cutout.dwmap,'TfsFile',return_value=SimpleNamespace(cluts=[pal])):
                self.assertEqual(cutout.check(cfg,out,m),[])
                p=places[0];tx,ty=p['texture'];ox,oy,w,h=p['source']
                raw=bytearray(m.tims[0]);offset=8+524+12
                raw[offset+(ty+8-oy)*64+tx+9-ox]=7;m.tims[0]=bytes(raw)
                self.assertTrue(any('black box' in e for e in cutout.check(cfg,out,m)))
                pal[7]=0
                self.assertTrue(any('transparent colour' in e for e in cutout.check(cfg,out,m)))
                rgba[:,:,3]=255;Image.fromarray(rgba).save(out/'post.png')
                self.assertTrue(any('alpha' in e for e in cutout.check(cfg,out,m)))

    def test_behind_declarations_require_walkable_floor_and_correct_depth(self):
        m=map_stub();mask=np.zeros((20,20),bool);mask[3:17,8:12]=True;mask[6:9,4:16]=True
        obj=dict(name='post',depth_world=[0,0,-100],tiles=dict(behind=[[50,49]],blocked=[]))
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);np.savez_compressed(out/'masks.npz',post=mask)
            rgba=np.zeros((20,20,4),dtype='uint8');rgba[:,:,3]=mask*255;Image.fromarray(rgba).save(out/'post.png')
            basis=(np.zeros(3),np.array([1,0,0]),np.array([0,1,0]),np.array([0,0,1]))
            with patch.object(cutout.dwmap,'camera_basis',return_value=basis), patch.object(cutout.dwmap,'project',return_value=None):
                self.assertTrue(any('is blocked' in e for e in cutout.check(dict(objects=[obj]),out,m)))
                m.collision[49*100+50]=0
                self.assertEqual(cutout.check(dict(objects=[obj]),out,m),[])
                obj['depth_world']=[0,0,500]
                self.assertTrue(any('in front of depth' in e for e in cutout.check(dict(objects=[obj]),out,m)))

    def test_suggest_hidden_floor_beyond_depth_anchor(self):
        mask=np.zeros((20,20),bool);mask[2:10,6:9]=True
        m=SimpleNamespace(collision=[128])
        obj=dict(name='post',depth_world=[0,0,0],tiles=dict(behind=[],blocked=[]))
        basis=(np.zeros(3),np.array([1,0,0]),np.array([0,1,0]),np.array([0,0,1]))
        with patch.object(cutout.dwmap,'camera_basis',return_value=basis), patch.object(cutout.dwmap,'project',return_value=(7,12)):
            result=cutout.suggestions(m,dict(objects=[obj]),{'post':mask})[0]
            self.assertEqual(result['suggestion'],'behind');self.assertTrue(result['hidden'])
            self.assertFalse(result['reviewed']);self.assertEqual(result['value'],0)
            obj['depth_world']=[0,0,6000]
            self.assertEqual(cutout.suggestions(m,dict(objects=[obj]),{'post':mask})[0]['suggestion'],'review')

    def test_floor_subtraction_precedes_cleanup_and_holes_are_optional(self):
        raw=np.zeros((20,20),bool);raw[2:17,2:17]=True;raw[7:12,7:12]=False
        floor=np.zeros_like(raw);floor[:,16:]=True
        obj=dict(name='post',subtract=['floor'],min_component=3)
        cfg=dict(objects=[obj]);masks={'post':raw,'floor':floor}
        clean=cutout.clean_masks(cfg,masks)['post'];self.assertFalse(clean[8,8]);self.assertFalse(clean[:,16:].any())
        obj['fill_holes']=True
        self.assertTrue(cutout.clean_masks(cfg,masks)['post'][8,8])


class ArrivalTests(unittest.TestCase):
    def warp(self,x,z):return dict(x=x,y=0,z=z,targetMap=1)

    def room(self,m,left,top,right,bottom):
        for tz in range(top,bottom):
            for tx in range(left,right):m.collision[tz*100+tx]=0

    def test_union_of_arrivals_cannot_hide_disconnection(self):
        m=map_stub();self.room(m,30,30,37,37);self.room(m,60,60,67,67)
        m.warps=[self.warp(-1650,1650),self.warp(1350,-1350)]
        self.assertTrue(any('unreachable' in e for e in reach.check_arrivals(m)))

    def test_blocked_spawn_is_not_a_reach_seed(self):
        m=map_stub();m.warps=[self.warp(50,-50)]
        self.assertFalse(reach.reach(m));self.assertTrue(reach.check_arrivals(m))

    def test_free_room_connects(self):
        m=map_stub();self.room(m,47,47,55,55)
        m.warps=[self.warp(50,-50),self.warp(250,-250)]
        self.assertEqual(reach.check_arrivals(m),[])

    def test_wall_adjacent_arrival_can_walk_out_to_the_room(self):
        m=map_stub();self.room(m,47,47,55,55)
        m.warps=[self.warp(50,-50),self.warp(450,-50)]
        connected=reach.reach(m,[(50,-50)])
        self.assertNotIn((450,-50),connected)
        self.assertTrue(connected.intersection(reach.reach(m,[(450,-50)])))
        self.assertEqual(reach.check_arrivals(m),[])

    def test_isolated_free_arrival_still_fails(self):
        m=map_stub();self.room(m,47,47,55,55);self.room(m,60,60,61,61)
        m.warps=[self.warp(50,-50),self.warp(1050,-1050)]
        errors=reach.check_arrivals(m)
        self.assertTrue(any('unreachable' in e for e in errors))
        self.assertTrue(any('cannot move' in e for e in errors))

    def test_bounce_and_height_fail(self):
        m=map_stub();self.room(m,47,47,55,55);m.warps=[self.warp(50,-50)]
        m.collision[50*100+50]=110;m.warps[0]['y']=2600
        errors=reach.check_arrivals(m)
        self.assertTrue(any('height' in e for e in errors));self.assertTrue(any('own exit' in e for e in errors))

    def test_one_tile_corridor_is_impassable(self):
        m=map_stub();self.room(m,30,40,38,48);self.room(m,50,40,58,48);self.room(m,38,44,50,45)
        m.warps=[self.warp(-1650,550),self.warp(350,550)]
        self.assertTrue(any('unreachable' in e for e in reach.check_arrivals(m)))


if __name__=='__main__':unittest.main()
