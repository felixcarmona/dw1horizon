// Offline Raidenmon audit rasterizer; mirrors psx_blend.render.
// This changes no runtime code. Compile with floating point contraction off.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
struct Packet { int bucket, ordinal; };
extern "C" void raiden_render(const double* points, const double* uv, const double* colors,
 const int* packets, int count, const uint8_t* texture, int width, int height,
 const uint16_t* palettes, int palette_width, double scale, double ox, double oy,
 double phase, int size, uint8_t* image) {
 for(int y=0;y<size;y++) for(int x=0;x<size;x++) {
  const int c=((x/24+y/24)%2); const int bg[2][3]={{14,17,20},{7,11,14}};
  for(int k=0;k<3;k++) image[3*(y*size+x)+k]=bg[c][k];
 }
 std::vector<Packet> order;
 for(int i=0;i<count;i++) {
  const int* p=packets+6*i; const double* q=points+9*p[0];
  const double x0=q[0]*scale+ox, y0=q[1]*scale+oy;
  const double x1=q[3]*scale+ox, y1=q[4]*scale+oy;
  const double x2=q[6]*scale+ox, y2=q[7]*scale+oy;
  if((x1-x0)*(y2-y0)-(y1-y0)*(x2-x0)<=1e-9) continue;
  double z=q[2]+q[5]+q[8];
  if(p[1]>=0) z=(z+points[9*p[1]+5])/4.; else z/=3.;
  order.push_back({int(std::floor((z+phase)/4.)),i});
 }
 std::sort(order.begin(),order.end(),[](Packet a,Packet b){
  return a.bucket!=b.bucket ? a.bucket>b.bucket : a.ordinal>b.ordinal;
 });
 for(Packet item:order) {
  const int* p=packets+6*item.ordinal;
  for(int half=0;half<(p[1]>=0?2:1);half++) {
   const int tri=p[half]; const double* q=points+9*tri;
   double x[3], y[3]; int corner[3]={0,1,2};
   for(int k=0;k<3;k++){x[k]=q[3*k]*scale+ox;y[k]=q[3*k+1]*scale+oy;}
   double area=(x[1]-x[0])*(y[2]-y[0])-(y[1]-y[0])*(x[2]-x[0]);
   if(std::abs(area)<=1e-9) continue;
   if(area<0){std::swap(x[1],x[2]);std::swap(y[1],y[2]);std::swap(corner[1],corner[2]);area=-area;}
   const int lx=std::max(0,int(std::floor(std::min({x[0],x[1],x[2]}))));
   const int ly=std::max(0,int(std::floor(std::min({y[0],y[1],y[2]}))));
   const int hx=std::min(size-1,int(std::ceil(std::max({x[0],x[1],x[2]}))));
   const int hy=std::min(size-1,int(std::ceil(std::max({y[0],y[1],y[2]}))));
   for(int iy=ly;iy<=hy;iy++) for(int ix=lx;ix<=hx;ix++) {
    double weights[3]; bool inside=true;
    for(int k=0;k<3;k++) {
     int a=(k+1)%3,b=(k+2)%3;
     double e=(x[b]-x[a])*(iy+.5-y[a])-(y[b]-y[a])*(ix+.5-x[a]);
     bool top=y[b]<y[a] || (y[b]==y[a] && x[b]>x[a]);
     if(!(e>1e-8 || (std::abs(e)<=1e-8 && top))){inside=false;break;}
     weights[k]=e/area;
    }
    if(!inside) continue;
    uint16_t word;
    if(p[4]) {
     double u=0,v=0;
     for(int k=0;k<3;k++){u+=weights[k]*uv[6*tri+2*corner[k]];v+=weights[k]*uv[6*tri+2*corner[k]+1];}
     const int iu=std::clamp(int(u),0,width-1),iv=std::clamp(int(v),0,height-1);
     word=palettes[p[5]*palette_width+texture[iv*width+iu]];
    } else {
     word=0x8000;
     for(int channel=0;channel<3;channel++) {
      double value=0;for(int k=0;k<3;k++)value+=weights[k]*colors[9*tri+3*corner[k]+channel];
      word|=(int(std::clamp(value,0.,255.))>>3)<<(5*channel);
     }
    }
    if(word==0) continue;
    for(int channel=0;channel<3;channel++) {
     int front=(word>>(5*channel))&31; uint8_t& back=image[3*(iy*size+ix)+channel];
     if(p[2] && (word&0x8000)) {
      switch(p[3]){
       case 0: front=(back>>1)+(front>>1);break;
       case 1: front=back+front;break;
       case 2: front=back-front;break;
       case 3: front=back+(front>>2);break;
      }
     }
     back=std::clamp(front,0,31);
    }
   }
  }
 }
 for(int k=0;k<size*size*3;k++)image[k]=int(image[k])*255/31;
}
