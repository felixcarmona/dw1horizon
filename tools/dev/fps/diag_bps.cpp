// BPS encoder for the private diagnostic disc, using the C++ standard library.
// Unchanged disc bytes use SourceRead; moved program bytes use SourceCopy.
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <map>
#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
#include <vector>
struct Image {
 int fd; size_t size; const uint8_t *p;
 Image(const char *path) {fd=open(path,O_RDONLY);if(fd<0)throw std::runtime_error("open image");struct stat s;fstat(fd,&s);size=s.st_size;p=(uint8_t*)mmap(nullptr,size,PROT_READ,MAP_PRIVATE,fd,0);if(p==MAP_FAILED)throw std::runtime_error("mmap");}
 ~Image(){munmap((void*)p,size);close(fd);}
};
std::vector<uint8_t> patch;
void vl(uint64_t n){for(;;){uint8_t b=n&127;n>>=7;if(!n){patch.push_back(b|128);return;}patch.push_back(b);n--;}}
void word(uint32_t n){for(int i=0;i<4;i++)patch.push_back(n>>(i*8));}
uint64_t key(const uint8_t *p){uint64_t n;memcpy(&n,p,8);return n;}
uint32_t crc(const uint8_t *p,size_t n){
 static uint32_t table[256];static bool ready=false;
 if(!ready){for(uint32_t i=0;i<256;i++){uint32_t c=i;for(int j=0;j<8;j++)c=(c>>1)^((c&1)?0xedb88320:0);table[i]=c;}ready=true;}
 uint32_t c=~0u;for(size_t i=0;i<n;i++)c=(c>>8)^table[(c^p[i])&255];return ~c;
}
int main(int argc,char **argv){try{
 if(argc!=5&&argc!=6)throw std::runtime_error("usage: diag_bps BASE TARGET RANGES PATCH [COPIES]");
 Image a(argv[1]),b(argv[2]);if(a.size!=b.size)throw std::runtime_error("disc size changed");
 std::unordered_map<uint64_t,uint32_t> index;std::ifstream ranges(argv[3]);size_t lo,hi;
 while(ranges>>lo>>hi){if(hi>a.size)throw std::runtime_error("range outside disc");for(size_t n=lo;n+16<=hi;n+=4)index.emplace(key(a.p+n),n);}
 std::map<size_t,std::pair<size_t,size_t>> exact;
 if(argc==6){std::ifstream copies(argv[5]);size_t target,source,length;while(copies>>target>>source>>length){if(target+length>b.size||source+length>a.size||memcmp(a.p+source,b.p+target,length))throw std::runtime_error("invalid exact object copy");exact[target]={source,length};}}
 auto protectedCopy=[&](size_t at,size_t &source){auto it=exact.upper_bound(at);if(it==exact.begin())return size_t(0);--it;if(at>=it->first+it->second.second)return size_t(0);source=it->second.first+at-it->first;return it->first+it->second.second-at;};
 patch={'B','P','S','1'};vl(a.size);vl(b.size);vl(0);
 size_t pos=0;int64_t relative=0;uint64_t copied=0,literals=0,read=0;
 auto match=[&](size_t at,size_t &source){if(at+16>b.size)return size_t(0);auto it=index.find(key(b.p+at));if(it==index.end())return size_t(0);source=it->second;size_t n=0;while(at+n<b.size&&source+n<a.size&&b.p[at+n]==a.p[source+n])n++;return n>=16?n:0;};
 while(pos<b.size){
  if(a.p[pos]==b.p[pos]){size_t end=pos;while(end<b.size&&a.p[end]==b.p[end])end++;if(end-pos>=4||end==b.size){vl(((end-pos-1)<<2)|0);read+=end-pos;pos=end;continue;}}
  size_t source=0,n=protectedCopy(pos,source);if(!n)n=match(pos,source);
  if(n){vl(((n-1)<<2)|2);int64_t delta=int64_t(source)-relative;vl((uint64_t(delta<0?-delta:delta)<<1)|(delta<0));relative=source+n;copied+=n;pos+=n;continue;}
  size_t start=pos++;
  while(pos<b.size){size_t unused;if(pos+4<=b.size&&!memcmp(a.p+pos,b.p+pos,4))break;if(protectedCopy(pos,unused)||match(pos,unused))break;pos++;}
  vl(((pos-start-1)<<2)|1);patch.insert(patch.end(),b.p+start,b.p+pos);literals+=pos-start;
 }
 word(crc(a.p,a.size));word(crc(b.p,b.size));word(crc(patch.data(),patch.size()));std::ofstream out(argv[4],std::ios::binary);out.write((char*)patch.data(),patch.size());
 std::cout<<"{\"patch_bytes\":"<<patch.size()<<",\"literal_bytes\":"<<literals<<",\"source_copy_bytes\":"<<copied<<",\"source_read_bytes\":"<<read<<"}\n";
}catch(const std::exception &e){std::cerr<<e.what()<<"\n";return 1;}}
