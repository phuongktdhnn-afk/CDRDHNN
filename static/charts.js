
(function(){
  'use strict';
  const NS='http://www.w3.org/2000/svg';
  const fmt=n=>Number(n||0).toLocaleString('vi-VN');
  const pct=n=>Number(n||0).toFixed(2)+'%';
  const esc=s=>String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));

  function svgRoot(el, w=900, h=310){
    if(!el) return null;
    el.innerHTML='';
    const svg=document.createElementNS(NS,'svg');
    svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
    svg.setAttribute('role','img');
    el.appendChild(svg);
    return svg;
  }
  function line(svg,x1,y1,x2,y2,attrs={}){
    const e=document.createElementNS(NS,'line');
    Object.entries({x1,y1,x2,y2,...attrs}).forEach(([k,v])=>e.setAttribute(k,v));
    svg.appendChild(e); return e;
  }
  function rect(svg,x,y,w,h,attrs={}){
    const e=document.createElementNS(NS,'rect');
    Object.entries({x,y,width:w,height:h,...attrs}).forEach(([k,v])=>e.setAttribute(k,v));
    svg.appendChild(e); return e;
  }
  function text(svg,x,y,t,attrs={}){
    const e=document.createElementNS(NS,'text');
    e.textContent=t;
    Object.entries({x,y,...attrs}).forEach(([k,v])=>e.setAttribute(k,v));
    svg.appendChild(e); return e;
  }
  function grid(svg,left,top,width,height,max){
    for(let i=0;i<=5;i++){
      const y=top+height-(height*i/5);
      line(svg,left,y,left+width,y,{'stroke':'#e7edf4','stroke-width':1});
      text(svg,left-10,y+4,fmt(Math.round(max*i/5)),{'text-anchor':'end','font-size':11,'fill':'#718096'});
    }
  }
  function tooltip(el,html){
    let t=el.querySelector('.chart-tip');
    if(!t){
      t=document.createElement('div'); t.className='chart-tip';
      t.style.cssText='position:absolute;display:none;pointer-events:none;background:#183b66;color:#fff;padding:7px 9px;border-radius:7px;font:12px Segoe UI,Arial,sans-serif;box-shadow:0 4px 12px #0002;z-index:5;white-space:nowrap';
      el.appendChild(t);
    }
    t.innerHTML=html;
    return t;
  }
  function addHover(el,node,html){
    const t=tooltip(el,html);
    node.addEventListener('mouseenter',()=>{t.style.display='block';});
    node.addEventListener('mousemove',ev=>{
      const r=el.getBoundingClientRect();
      t.style.left=(ev.clientX-r.left+12)+'px'; t.style.top=(ev.clientY-r.top+12)+'px';
    });
    node.addEventListener('mouseleave',()=>{t.style.display='none';});
  }

  window.CDRCharts={
    bar:function(id,data,opts={}){
      const el=document.getElementById(id); const svg=svgRoot(el,Math.max(900,data.length*125),340); if(!svg)return;
      const W=Math.max(900,data.length*125),H=340,L=65,R=25,T=22,B=60;
      const width=W-L-R,height=H-T-B;
      const vals=data.map(d=>opts.value?opts.value(d):d.value);
      const numeric=vals.filter(v=>v!=null && Number.isFinite(Number(v))).map(Number);
      const max=Math.max(1,opts.max||Math.max(...numeric,0)*1.15);
      grid(svg,L,T,width,height,max);
      const gap=width/Math.max(1,data.length), bw=Math.min(72,gap*.62);
      data.forEach((d,i)=>{
        const raw=vals[i], isNull=raw==null || !Number.isFinite(Number(raw));
        const v=isNull?0:Number(raw), bh=isNull?0:v/max*height, x=L+gap*i+(gap-bw)/2, y=T+height-bh;
        const color=opts.color?opts.color(d,i):'#2475c9';
        if(!isNull){
          const r=rect(svg,x,y,bw,bh,{rx:5,fill:color});
          addHover(el,r,`${esc(opts.label?opts.label(d):d.label||'')}: <b>${fmt(v)}</b>${opts.extra?'<br>'+opts.extra(d,i):''}`);
          text(svg,x+bw/2,y-7,fmt(v),{'text-anchor':'middle','font-size':12,'font-weight':700,'fill':'#183b66'});
        }else{
          text(svg,x+bw/2,T+height/2,opts.nullLabel||'—',{'text-anchor':'middle','font-size':15,'font-weight':700,'fill':'#94a3b8'});
        }
        text(svg,x+bw/2,H-28,String(opts.x?opts.x(d):d.label||''),{'text-anchor':'middle','font-size':13,'font-weight':600,'fill':'#52677d'});
      });
    },
    horizontalBar:function(id,data,opts={}){
      const el=document.getElementById(id); if(!el)return;
      const W=1200, rowH=38, H=Math.max(470,data.length*rowH+55), L=285, R=120, T=20, B=20;
      el.innerHTML='';
      const svg=document.createElementNS(NS,'svg');
      svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
      svg.setAttribute('width',W); svg.setAttribute('height',H);
      svg.setAttribute('role','img'); el.appendChild(svg);
      const vals=data.map(d=>Number(opts.value?opts.value(d):d.value||0));
      const max=Math.max(1,opts.max||Math.max(...vals,0)*1.12);
      const barW=W-L-R;
      // grid and scale
      for(let i=0;i<=5;i++){
        const x=L+barW*i/5;
        line(svg,x,T,x,H-B,{'stroke':'#e7edf4','stroke-width':1});
        text(svg,x,H-2,fmt(Math.round(max*i/5)),{'text-anchor':'middle','font-size':12,'fill':'#718096'});
      }
      data.forEach((d,i)=>{
        const y=T+i*rowH;
        const v=vals[i], bw=(v/max)*barW;
        const label=opts.label?opts.label(d):d.label||'';
        text(svg,L-14,y+20, label,{'text-anchor':'end','font-size':13,'font-weight':600,'fill':'#52677d'});
        const r=rect(svg,L,y+6,Math.max(2,bw),24,{rx:5,fill:opts.color?opts.color(d,i):'#2475c9'});
        addHover(el,r,`${esc(label)}: <b>${fmt(v)}</b>${opts.extra?'<br>'+opts.extra(d,i):''}`);
        text(svg,L+bw+10,y+23,fmt(v),{'font-size':13,'font-weight':750,'fill':'#183b66'});
      });
    },
    groupedBar:function(id,data,series,opts={}){
      const el=document.getElementById(id); const svg=svgRoot(el,Math.max(1000,data.length*120),360); if(!svg)return;
      const W=Math.max(1000,data.length*120),H=360,L=65,R=25,T=22,B=65,width=W-L-R,height=H-T-B;
      const all=[]; data.forEach(d=>series.forEach(s=>all.push(Number(s.value(d)||0))));
      const max=Math.max(1,opts.max||Math.max(...all)*1.15); grid(svg,L,T,width,height,max);
      const gap=width/Math.max(1,data.length), bw=Math.min(58,(gap*.68)/series.length);
      data.forEach((d,i)=>{
        const start=L+gap*i+(gap-bw*series.length)/2;
        series.forEach((s,j)=>{
          const v=Number(s.value(d)||0),bh=v/max*height,x=start+j*bw,y=T+height-bh;
          const r=rect(svg,x,y,bw-3,bh,{rx:4,fill:s.color||'#2475c9'});
          addHover(el,r,`${esc(s.label)} – ${esc(opts.x?opts.x(d):d.label||'')}: <b>${fmt(v)}</b>${s.percent?` (${Number(s.percent(d)).toFixed(2)}%)`:''}`);
          text(svg,x+(bw-3)/2,y-5,fmt(v),{'text-anchor':'middle','font-size':12,'font-weight':700,'fill':'#183b66'});
        });
        text(svg,L+gap*i+gap/2,H-30,String(opts.x?opts.x(d):d.label||''),{'text-anchor':'middle','font-size':13,'font-weight':600,'fill':'#52677d'});
      });
      const lx=L,ly=H-8; series.forEach((s,i)=>{rect(svg,lx+i*145,ly-10,10,10,{rx:2,fill:s.color||'#2475c9'});text(svg,lx+15+i*145,ly,s.label,{'font-size':13,'font-weight':600,'fill':'#52677d'});});
    },
    line:function(id,data,opts={}){
      const el=document.getElementById(id); const svg=svgRoot(el,900,310); if(!svg)return;
      const W=900,H=310,L=65,R=25,T=20,B=55,width=W-L-R,height=H-T-B;
      const vals=data.map(d=>Number(opts.value?opts.value(d):d.value||0));
      const max=opts.max??Math.max(1,...vals)*1.12, min=opts.min??0; grid(svg,L,T,width,height,max);
      const pts=data.map((d,i)=>[L+(data.length<=1?width/2:i*width/(data.length-1)),T+height-(vals[i]-min)/(max-min)*height]);
      if(pts.length>1){
        const p=document.createElementNS(NS,'polyline'); p.setAttribute('points',pts.map(x=>x.join(',')).join(' ')); p.setAttribute('fill','none'); p.setAttribute('stroke',opts.color||'#2475c9'); p.setAttribute('stroke-width','3'); svg.appendChild(p);
      }
      pts.forEach((p,i)=>{
        const c=document.createElementNS(NS,'circle'); c.setAttribute('cx',p[0]);c.setAttribute('cy',p[1]);c.setAttribute('r',5);c.setAttribute('fill',opts.color||'#2475c9');svg.appendChild(c);
        addHover(el,c,`${esc(opts.x?opts.x(data[i]):data[i].label||'')}: <b>${opts.percent?pct(vals[i]):fmt(vals[i])}</b>`);
        text(svg,p[0],p[1]-10,opts.percent?pct(vals[i]):fmt(vals[i]),{'text-anchor':'middle','font-size':12,'font-weight':700,'fill':'#183b66'});
        text(svg,p[0],H-28,String(opts.x?opts.x(data[i]):data[i].label||''),{'text-anchor':'middle','font-size':13,'font-weight':600,'fill':'#52677d'});
      });
    },
    donut:function(id,data,opts={}){
      const el=document.getElementById(id); const svg=svgRoot(el,900,310); if(!svg)return;
      const total=data.reduce((a,d)=>a+Number(d.value||0),0)||1, cx=250,cy=155,r=105,stroke=48;
      let angle=-Math.PI/2;
      data.forEach((d,i)=>{
        const v=Number(d.value||0), a=v/total*Math.PI*2, end=angle+a;
        const x1=cx+r*Math.cos(angle),y1=cy+r*Math.sin(angle),x2=cx+r*Math.cos(end),y2=cy+r*Math.sin(end);
        const large=a>Math.PI?1:0;
        const path=document.createElementNS(NS,'path');
        path.setAttribute('d',`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`);
        path.setAttribute('fill','none');path.setAttribute('stroke',d.color||'#2475c9');path.setAttribute('stroke-width',stroke);
        svg.appendChild(path);
        addHover(el,path,`${esc(d.label)}: <b>${fmt(v)}</b> (${(v/total*100).toFixed(2)}%)`);
        angle=end;
      });
      text(svg,cx,cy-3,'Tổng',{'text-anchor':'middle','font-size':13,'fill':'#718096'});
      text(svg,cx,cy+22,fmt(total),{'text-anchor':'middle','font-size':23,'font-weight':800,'fill':'#183b66'});
      data.forEach((d,i)=>{
        const y=48+i*34;rect(svg,470,y-11,12,12,{rx:3,fill:d.color||'#2475c9'});text(svg,490,y,`${d.label} – ${fmt(d.value)} (${(Number(d.value||0)/total*100).toFixed(2)}%)`,{'font-size':12,'fill':'#52677d'});
      });
    }
  };
})();
