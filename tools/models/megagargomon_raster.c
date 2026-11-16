/* Scoped offline evidence accelerator. Same affine RGB5 rules as psx_blend.py. */
#include <stdint.h>
#include <math.h>
static double edge(const double *a,const double *b,double x,double y) {
    return (b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]);
}
void raster(int count,const double *commands,int size,const uint8_t *texture,
            int width,int height,const uint16_t *palette,uint8_t *image) {
    for(int y=0;y<size;y++) for(int x=0;x<size;x++) {
        int checker=(x/24+y/24)%2, k=(y*size+x)*3;
        image[k]=checker?7:14; image[k+1]=checker?11:17; image[k+2]=checker?14:20;
    }
    /* command: xy[6], uv[6], rgb[9], row, textured, gouraud, abe, abr */
    for(int t=0;t<count;t++) {
        const double *cmd=commands+t*26;
        double xy[3][2],uv[3][2],rgb[3][3];
        int order[3]={0,1,2};
        double area=edge(cmd,cmd+2,cmd[4],cmd[5]);
        if(fabs(area)<=1e-9) continue;
        if(area<0) {order[1]=2;order[2]=1;area=-area;}
        for(int j=0;j<3;j++) {
            for(int k=0;k<2;k++) {xy[j][k]=cmd[2*order[j]+k];uv[j][k]=cmd[6+2*order[j]+k];}
            for(int k=0;k<3;k++) rgb[j][k]=cmd[12+3*order[j]+k];
        }
        int low[2],high[2];
        for(int k=0;k<2;k++) {
            low[k]=(int)fmax(0,floor(fmin(xy[0][k],fmin(xy[1][k],xy[2][k]))));
            high[k]=(int)fmin(size-1,ceil(fmax(xy[0][k],fmax(xy[1][k],xy[2][k]))));
        }
        for(int y=low[1];y<=high[1];y++) for(int x=low[0];x<=high[0];x++) {
            double weights[3]; int inside=1;
            for(int j=0;j<3;j++) {
                double *a=xy[(j+1)%3],*b=xy[(j+2)%3];
                double e=edge(a,b,x+.5,y+.5);
                int top=b[1]<a[1] || (b[1]==a[1] && b[0]>a[0]);
                if(!(e>1e-8 || (fabs(e)<=1e-8 && top))) {inside=0;break;}
                weights[j]=e/area;
            }
            if(!inside) continue;
            uint16_t word;
            if(cmd[22]) {
                int u=(int)(weights[0]*uv[0][0]+weights[1]*uv[1][0]+weights[2]*uv[2][0]);
                int v=(int)(weights[0]*uv[0][1]+weights[1]*uv[1][1]+weights[2]*uv[2][1]);
                if(u<0)u=0;if(u>=width)u=width-1;if(v<0)v=0;if(v>=height)v=height-1;
                word=palette[(int)cmd[21]*16+texture[v*width+u]];
            } else {
                word=0x8000;
                for(int k=0;k<3;k++) {
                    double color=cmd[23] ? weights[0]*rgb[0][k]+weights[1]*rgb[1][k]+weights[2]*rgb[2][k] : rgb[0][k];
                    int val=(int)fmax(0,fmin(255,color));word|=(val>>3)<<(k*5);
                }
            }
            if(!word)continue;
            for(int k=0;k<3;k++) {
                int ix=(y*size+x)*3+k, front=(word>>(5*k))&31,back=image[ix],result=front;
                if(cmd[24] && (word&0x8000)) {
                    switch((int)cmd[25]) {
                        case 0:result=(back>>1)+(front>>1);break;
                        case 1:result=back+front;break;
                        case 2:result=back-front;break;
                        case 3:result=back+(front>>2);break;
                    }
                    if(result<0)result=0;if(result>31)result=31;
                }
                image[ix]=result;
            }
        }
    }
}
