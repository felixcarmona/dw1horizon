#!/usr/bin/env python3
"""Packed engine sector tables retain exact sizes, keys, and bounds."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import isowriter as iw
class PackedTable(unittest.TestCase):
 def table(self,names):
  data=bytearray(b'DWFH\x02\0\0\0')
  for name in names:data.extend((2048<<19 | ((iw.filename_hash(name)&0xffffff)<<40)).to_bytes(8,'little'))
  return data+bytes(8)
 def test_exact_sizes_and_boundaries(self):
  names=['DG.SCN','OP1.STR','LANGJA.BIN'];data=self.table(names)
  where=dict(zip(names,[(0,1),((1<<19)-1,(1<<26)-64),(383087,43318784)]))
  n,_,missing,found=iw.rewrite_file_table(data,0,where)
  self.assertEqual((n,missing,found),(3,[],set(names)))
  self.assertEqual({name:(sector,size) for _,sector,size,name in iw.file_table_entries(data,0,names=names)},where)
  self.assertEqual(data[:8],b'DWFH\x02\0\0\0')
 def test_size_threshold(self):
  sizes=[(1<<20)-1,1<<20,(1<<20)+64,(1<<26)-64]
  names=[f'X{i}.BIN' for i in range(len(sizes))]
  data=self.table(names);where={name:(200+i,size) for i,(name,size) in enumerate(zip(names,sizes))}
  iw.rewrite_file_table(data,0,where)
  self.assertEqual([size for _,_,size,_ in iw.file_table_entries(data,0,names=names)],sizes)
 def test_overflow_rejected(self):
  for values in [(1<<19,1),(1,1<<26),(1,(1<<20)+1),(-1,1),(1,-1)]:
   with self.subTest(values=values),self.assertRaises(ValueError): iw.rewrite_file_table(self.table(['DG.SCN']),0,{'DG.SCN':values})
 def test_collisions_rejected(self):
  pair=['BV69XUCZ.BIN','0DAGVPP3.BIN']
  with self.assertRaises(ValueError):iw.file_table_entries(self.table(pair),0,names=pair)
 def test_unknown_names_preserve_keys(self):
  data=self.table(['DG.SCN']);key=iw.filename_hash('DG.SCN')&0xffffff
  self.assertEqual(iw.file_table_entries(data,0)[0][-1],f'@{key:08X}')
if __name__=='__main__':unittest.main()
