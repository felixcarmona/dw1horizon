// Developer-only alignment-insensitive 16-byte literal search. No game bytes in the report.
// Build: c++ -O3 -std=c++17 literal_scan.cpp -o literal_scan
// Arguments: blob, literal ranges TSV (offset length), sources TSV
// Sources rows: image path TAB file tag TAB LBA TAB ISO size TAB mode.
// Modes: 0 ISO data file, 1 XA file/license, 2 complete raw image, 3 every 2048-byte sector data area.
// Output: blob offset, source row index, offset within logical file.
#include <array>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
using Key = std::array<uint64_t, 2>;
struct Hash { size_t operator()(const Key& k) const {
    uint64_t x = k[0] ^ (k[1] * 0x9e3779b97f4a7c15ULL);
    x ^= x >> 30; x *= 0xbf58476d1ce4e5b9ULL; x ^= x >> 27;
    return x;
}};
Key key(const char* p) { Key k; std::memcpy(k.data(), p, 16); return k; }
int main(int argc, char** argv) {
    if (argc != 4) return 2;
    std::ifstream bf(argv[1], std::ios::binary);
    std::string blob((std::istreambuf_iterator<char>(bf)), {});
    std::unordered_map<Key, std::vector<uint32_t>, Hash> queries;
    std::ifstream ranges(argv[2]); size_t off, len;
    while (ranges >> off >> len) {
        if (off + len > blob.size()) return 3;
        for (size_t p = off; p + 16 <= off + len; ++p) queries[key(blob.data()+p)].push_back(p);
    }
    std::array<std::vector<uint32_t>,256> uniform;
    struct Best { size_t length=0, row=0, offset=0; };
    std::array<Best,256> best;
    for (unsigned v=0; v<256; ++v) {
        Key k = {0x0101010101010101ULL*v, 0x0101010101010101ULL*v};
        auto it=queries.find(k);
        if(it!=queries.end()) { uniform[v]=std::move(it->second); queries.erase(it); }
    }
    constexpr size_t MASK = (1<<26)-1;
    std::vector<bool> bloom(MASK+1);
    for (const auto& q : queries) bloom[Hash{}(q.first)&MASK] = true;
    std::ifstream sources(argv[3]); std::string line, current; int fd=-1; char* raw=nullptr; size_t rawlen=0, row=0;
    while (std::getline(sources, line)) {
        std::istringstream ss(line); std::string path, rest;
        std::getline(ss,path,'\t'); size_t fileid,lba,n; unsigned mixed; ss>>fileid>>lba>>n>>mixed;
        if (path!=current) {
            if (raw) { munmap(raw,rawlen); close(fd); }
            current=path; fd=open(path.c_str(),O_RDONLY); struct stat st;
            if(fd<0 || fstat(fd,&st)) return 4;
            rawlen=st.st_size; raw=(char*)mmap(nullptr,rawlen,PROT_READ,MAP_PRIVATE,fd,0);
            if(raw==MAP_FAILED) return 5;
            std::cerr<<path<<" remaining unique windows "<<queries.size()<<std::endl;
        }
        size_t stride=mixed==1?2336:2048, skip=mixed==1?16:24;
        size_t size=mixed==2?rawlen:mixed==3?(rawlen/2352)*2048:mixed==1?(n/2048)*2336:n;
        std::vector<char> data(size);
        if(mixed==2) std::memcpy(data.data(),raw,size);
        else for(size_t p=0; p<size; p+=stride) {
            size_t at=(lba+p/stride)*2352+skip, take=std::min(stride,size-p);
            if(at+take>rawlen) return 6;
            std::memcpy(data.data()+p,raw+at,take);
        }
        for(size_t p=0;p+16<=size;++p) {
            Key k=key(data.data()+p);
            unsigned v=(unsigned char)data[p];
            if(k[0]==k[1] && k[0]==0x0101010101010101ULL*v) {
                size_t end=p+16;
                while(end<size && (unsigned char)data[end]==v) ++end;
                if(end-p>best[v].length) best[v]={end-p,row,p};
                p=end-16; continue;
            }
            if(!bloom[Hash{}(k)&MASK]) continue;
            auto it=queries.find(k); if(it==queries.end()) continue;
            for(auto q:it->second) std::cout<<q<<'\t'<<row<<'\t'<<p<<'\n';
            queries.erase(it);
        }
        ++row;
    }
    for(unsigned v=0; v<256; ++v) if(best[v].length>=16)
        for(auto q:uniform[v]) std::cout<<q<<'\t'<<best[v].row<<'\t'<<best[v].offset<<'\n';
    size_t missing_uniform=0;
    for(unsigned v=0; v<256; ++v) if(!uniform[v].empty() && best[v].length<16) ++missing_uniform;
    std::cerr<<"Unmatched unique windows: "<<queries.size()+missing_uniform<<std::endl;
    if(raw) { munmap(raw,rawlen); close(fd); }
}
