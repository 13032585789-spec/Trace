"""Static isometric preview of an /api/geometry/scene JSON (walls with holes, open door leaves, fixture models).
usage: edit the two render(...) calls at the bottom, or import render(scene, out_png, title, crop=(x0,z0,x1,z1), cut=1.2)."""
import json, math, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
INK,CREAM,GREY,GOLD="#202427","#F7F6F2","#A9AFB0","#E9B949"
MAT={"ceramic":"#FFFFFF","plastic":"#F1EFE9","metal":"#C9CCCD","wood":"#E6D7B8","glass":"#CFE0EA","water":"#BFD6E4"}
C,S=math.cos(math.radians(30)),math.sin(math.radians(30))
def iso(x,z,y): return ((x-z)*C, -((x+z)*S - y))
def prism(ring,y0,y1):
    """faces of a vertical prism: list of (depth, poly, shade)"""
    out=[]
    n=len(ring)
    for i in range(n):
        a,b=ring[i],ring[(i+1)%n]
        # outward normal facing camera (camera at +x,+z)
        ex,ez=b[0]-a[0],b[1]-a[1]; nx,nz=ez,-ex
        cx=np.mean([p[0] for p in ring]); cz=np.mean([p[1] for p in ring])
        mx,mz=(a[0]+b[0])/2,(a[1]+b[1])/2
        if (mx-cx)*nx+(mz-cz)*nz<0: nx,nz=-nx,-nz
        if nx+nz<=0: continue
        shade=0.80 if abs(nx)>abs(nz) else 0.90
        out.append(((mx+mz), [iso(a[0],a[1],y0),iso(b[0],b[1],y0),iso(b[0],b[1],y1),iso(a[0],a[1],y1)], shade, y1))
    cx=np.mean([p[0] for p in ring]); cz=np.mean([p[1] for p in ring])
    out.append((cx+cz+0.001, [iso(x,z,y1) for x,z in ring], 1.0, y1))
    return out
def shade(hexc,k):
    c=np.array(matplotlib.colors.to_rgb(hexc))*k; return tuple(np.clip(c,0,1))
def prim_rings(ob,p):
    th=math.radians((ob.get("model") or {}).get("rotation_deg") or 0)
    ux=(math.cos(th),-math.sin(th)); uz=(math.sin(th),math.cos(th))
    X,_,Z=ob["position"]
    lx,ly,lz=p["at"]
    def w(px,pz): return (X+px*ux[0]+pz*uz[0], Z+px*ux[1]+pz*uz[1])
    if p["shape"]=="box":
        sx,sy,sz=p["size"]; pts=[(-sx/2,-sz/2),(sx/2,-sz/2),(sx/2,sz/2),(-sx/2,sz/2)]
        return [w(lx+a,lz+b) for a,b in pts], ly-sy/2, ly+sy/2
    r=p["radius"]; k=p.get("scale_z",1); h=p["height"]
    pts=[(r*math.cos(t), r*k*math.sin(t)) for t in np.linspace(0,2*math.pi,12,endpoint=False)]
    return [w(lx+a,lz+b) for a,b in pts], ly-h/2, ly+h/2
def render(scene,out,title,crop=None,figsize=(14,9),cut=None):
    walls,rooms,ops,objs=scene["walls"],scene["rooms"],scene["openings"],scene["objects"]
    if crop:
        x0,z0,x1,z1=crop; inb=lambda x,z: x0<=x<=x1 and z0<=z<=z1
        hit=lambda pts: not (max(p[0] for p in pts)<x0 or min(p[0] for p in pts)>x1 or max(p[1] for p in pts)<z0 or min(p[1] for p in pts)>z1)
        rooms=[m for m in rooms if len(m["polygon"])>=3 and hit(m["polygon"])]          # whole rooms that touch the view
        if rooms:
            ap=np.vstack([np.array(m["polygon"]) for m in rooms]); x0,z0=ap.min(0)-0.3; x1,z1=ap.max(0)+0.3
        walls=[w for w in walls if hit(w["points"])]
        BB=(x0,z0,x1,z1)
        inb=lambda x,z: x0<=x<=x1 and z0<=z<=z1
        ops=[o for o in ops if inb(o["position"][0],o["position"][2])]; objs=[o for o in objs if inb(o["position"][0],o["position"][2])]
    else: BB=None
    def clip(a,b):
        if BB is None: return a,b
        x0_,z0_,x1_,z1_=BB; t0,t1=0.0,1.0; dx,dz=b[0]-a[0],b[1]-a[1]
        for p_,q_ in ((-dx,a[0]-x0_),(dx,x1_-a[0]),(-dz,a[1]-z0_),(dz,z1_-a[1])):
            if abs(p_)<1e-12:
                if q_<0: return None
            else:
                r_=q_/p_
                if p_<0: t0=max(t0,r_)
                else: t1=min(t1,r_)
        if t0>t1: return None
        return (a[0]+t0*dx,a[1]+t0*dz),(a[0]+t1*dx,a[1]+t1*dz)
    fig,ax=plt.subplots(figsize=figsize,dpi=120); fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
    for m in rooms:
        if len(m["polygon"])>=3: ax.add_patch(Polygon([iso(x,z,0) for x,z in m["polygon"]],fc="#FFFFFF",ec="#E4E1D8",lw=0.5,zorder=1))
    faces=[]
    def slab(a,b,t):
        a,b=np.array(a,float),np.array(b,float); L=np.hypot(*(b-a)) or 1; n=np.array([-(b-a)[1],(b-a)[0]])/L*t/2
        return [tuple(a+n),tuple(b+n),tuple(b-n),tuple(a-n)]
    for w in walls:
        col=GREY if w.get("assumed") else "#D9D4C7"; t=w.get("thickness_m") or 0.2
        parts=w.get("pieces") or [{"from":w["points"][0],"to":w["points"][-1],"y0":0,"y1":w.get("height_m") or 2.8}]
        for pc in parts:
            cl=clip(pc["from"],pc["to"])
            if cl is None: continue
            pc={**pc,"from":cl[0],"to":cl[1]}
            y0,y1=pc["y0"],pc["y1"]
            if cut: y1=min(y1,cut)
            if y1<=y0: continue
            for d,q,k,y in prism(slab(pc["from"],pc["to"],t),y0,y1): faces.append((d,y,q,shade(col,k)))
    for o in ops:
        if o.get("leaf"):
            lf=o["leaf"]; h=min(lf["height_m"], cut or 9)
            for d,q,k,y in prism(slab(lf["hinge"],lf["tip"],0.05),0,h): faces.append((d,y,q,shade(GOLD,k)))
        elif o["kind"]=="window":
            x,_,z=o["position"]; hw=(o.get("width_m") or 0.9)/2; th=math.radians(-(o.get("rotation_deg") or 0))
            dx,dz=math.cos(th)*hw,math.sin(th)*hw; y0=o.get("sill_y_m") or 0.9; y1=min(y0+(o.get("height_m") or 1.2), cut or 9)
            if y1>y0: faces.append((x+z+0.02,y1,[iso(x-dx,z-dz,y0),iso(x+dx,z+dz,y0),iso(x+dx,z+dz,y1),iso(x-dx,z-dz,y1)],"#7FA7C9"))
    for ob in objs:
        for p in (ob.get("model") or {}).get("primitives",[]):
            ring,y0,y1=prim_rings(ob,p)
            for d,q,k,y in prism(ring,y0,y1): faces.append((d,y,q,shade(MAT.get(p.get("material"),"#FFFFFF"),k)))
    faces.sort(key=lambda f:(f[0],f[1]))
    for d,y,q,c in faces: ax.add_patch(Polygon(q,closed=True,fc=c,ec=INK,lw=0.3,zorder=2))
    ax.autoscale_view(); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(title,color=INK,fontsize=15,loc="left",fontweight="bold")
    fig.savefig(out,bbox_inches="tight",facecolor=CREAM); plt.close(fig)
ifc=json.load(open("eval/integration/scene_ifc_bathroom.json"))["response"]
render(ifc,"/tmp/iso_ifc_bath.png","Duplex Bathroom 1 (IFC) – shower, toilet and sink as simple 3D models",figsize=(10,8),cut=1.2)
pdf=json.load(open("eval/integration/scene_pdf_vector_school.json"))["response"]
render(pdf,"/tmp/iso_pdf_wc.png","School toilets (vector PDF, realised) – fixtures backed against the nearest wall",crop=(12.5,16.5,17.0,18.6),figsize=(13,9),cut=1.2)
