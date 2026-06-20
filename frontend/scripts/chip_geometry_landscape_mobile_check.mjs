// LANDSCAPE MOBILE — valida geometria da mesa landscape (telefone fullscreen).
// Mesma lógica do landscape desktop (chip_geometry_check.mjs), com pod SINGLE-LINE
// compacto + cartas MAIORES. Objetivo: 0 sobreposições E 0 cortes (POD/CARD dentro do
// viewBox) em 6/8/9-max. Tune os números no topo e rode:
//   node scripts/chip_geometry_landscape_mobile_check.mjs
const S=1;                          // landscape: pods full-size
const CX=580, CY=355, RX_SEAT=472, RY_SEAT=250;
const HW=75*S, HH=20*S;             // pod single-line (150×40 × S)
const CARD_HW=83*S, CH=116*S;       // cartas MAIORES (80×116 × S, gap 6 → (2*80+6)/2=83)
const CARD_DY=Math.round(CH*0.67)-HH;
const CLU_HW=28, CLU_UP=30, CLU_DN=28; // cluster de fichas (acima/abaixo da âncora)
const DRX=20, DRY=12;
const GAP=14;
const VB={x1:4,y1:4,x2:1156,y2:706}; // viewBox
const BOARD_W=68, BOARD_GAP=8, BOARD_H=110;
function buildLayout(seatNums, heroSeat){
  const n=seatNums.length, heroIdx=seatNums.indexOf(heroSeat);
  const rot=180-(360/n)*heroIdx, L={};
  seatNums.forEach((s,i)=>{
    const a=(-90+(360/n)*i+rot)*Math.PI/180;
    const x=Math.round(CX+RX_SEAT*Math.cos(a)), y=Math.round(CY+RY_SEAT*Math.sin(a));
    L[s]={x,y,dir:y<CY?'top':'bottom'};
  });
  return L;
}
const overlap=(a,b,pad=0)=> a.x1<b.x2-pad&&a.x2>b.x1+pad&&a.y1<b.y2-pad&&a.y2>b.y1+pad;
const inside=(a)=> a.x1>=VB.x1&&a.x2<=VB.x2&&a.y1>=VB.y1&&a.y2<=VB.y2;
const podBox =p=>({x1:p.x-HW,y1:p.y-HH,x2:p.x+HW,y2:p.y+HH});
function cardBox(p){ const by=p.y-HH, cy=by-Math.round(CH*0.67); return {x1:p.x-CARD_HW,y1:cy,x2:p.x+CARD_HW,y2:cy+CH}; }
const cluBox =(cx,by)=>({x1:cx-CLU_HW,y1:by-CLU_UP,x2:cx+CLU_HW,y2:by+CLU_DN});
const dlrBox =(dx,dy)=>({x1:dx-DRX,y1:dy-DRY,x2:dx+DRX,y2:dy+DRY+7});
const boardBox={x1:CX-(5*BOARD_W+4*BOARD_GAP)/2,y1:CY-BOARD_H/2-6,x2:CX+(5*BOARD_W+4*BOARD_GAP)/2,y2:CY+BOARD_H/2-6};
const RXF=440, RYF=232, FELT_MX=24, FELT_MY=22;
function inFelt(x,y){ return ((x-CX)/(RXF-FELT_MX))**2 + ((y-CY)/(RYF-FELT_MY))**2 <= 1; }

function farAlong(cBx,cBy, hwB,hhB, px,py, ux,uy){
  const d=(cBx-px)*ux+(cBy-py)*uy;
  return d + hwB*Math.abs(ux)+hhB*Math.abs(uy);
}

function place(p){
  const dvx=CX-p.x, dvy=CY-p.y, len=Math.hypot(dvx,dvy)||1;
  const ux=dvx/len, uy=dvy/len;
  const tx=-uy, ty=ux;
  const cardCY = (p.y-HH) - Math.round(CH*0.67) + CH/2;
  const podFar  = farAlong(p.x,p.y, HW,HH, p.x,p.y, ux,uy);
  const cardFar = farAlong(p.x,cardCY, CARD_HW,CH/2, p.x,p.y, ux,uy);
  const far = Math.max(podFar, cardFar);
  const cx = Math.round(p.x + (far+GAP+CLU_UP)*ux);
  const by = Math.round(p.y + (far+GAP+CLU_UP)*uy);
  let best=null;
  for(const d of [40,54,68,84,100,116,132]){
    for(const L of [0,50,-50,78,-78,106,-106,136,-136]){
      const dx=Math.round(p.x + ux*d + tx*L);
      const dy=Math.round(p.y + uy*d + ty*L);
      if(!inFelt(dx,dy)) continue;
      const db=dlrBox(dx,dy);
      if(overlap(db,podBox(p),0)||overlap(db,cardBox(p),0)||overlap(db,cluBox(cx,by),0)||overlap(db,boardBox,0)) continue;
      const distPod=Math.hypot(dx-p.x,dy-p.y);
      const score = -distPod - Math.abs(L)*0.12;
      if(!best||score>best.score) best={dx,dy,score};
    }
  }
  return {cx,by,dealer:best,ux,uy};
}

function validate(seats,heroSeat,label){
  const L=buildLayout(seats,heroSeat);
  console.log(`\n### ${label} (hero seat ${heroSeat}) ###`);
  let bad=0;
  for(const s of seats){
    const p=L[s], r=place(p);
    const cb=cluBox(r.cx,r.by), iss=[];
    if(overlap(cb,podBox(p),0))iss.push('CHIP×POD');
    if(overlap(cb,cardBox(p),0))iss.push('CHIP×CARDS');
    if(overlap(cb,boardBox,0))iss.push('CHIP×BOARD');
    if(!inside(cb))iss.push('CHIP×OOB');
    if(!inside(podBox(p)))iss.push('POD×CORTADO');
    if(!inside(cardBox(p)))iss.push('CARD×CORTADO');
    if(!r.dealer)iss.push('DEALER:nenhum-lado-valido');
    else {
      const db=dlrBox(r.dealer.dx,r.dealer.dy);
      if(overlap(db,cb,0))iss.push('DLR×CHIP');
      if(overlap(db,podBox(p),0))iss.push('DLR×POD');
      if(overlap(db,cardBox(p),0))iss.push('DLR×CARDS');
      if(!inFelt(r.dealer.dx,r.dealer.dy))iss.push('DLR×FORA-DO-FELTRO');
    }
    if(iss.length)bad++;
    const dl=r.dealer?`(${r.dealer.dx},${r.dealer.dy})`:'—';
    console.log(`${s} ${p.dir.padEnd(6)} pod(${String(p.x).padStart(4)},${String(p.y).padStart(3)}) chip(${String(r.cx).padStart(4)},${String(r.by).padStart(3)}) dlr${dl.padEnd(12)} ${iss.join(' ')||'ok'}`);
  }
  console.log(bad? `>>> ${bad} assento(s) com problema`:'>>> 0 sobreposições ✓');
  return bad;
}
let total=0;
total+=validate([1,2,3,4,5,6,7,8,9],9,'9-max hero embaixo');
total+=validate([1,2,3,4,5,6,7,8],8,'8-max');
total+=validate([1,2,3,4,5,6],6,'6-max');
total+=validate([1,2,3,4,5,6,7,8,9],4,'9-max hero no topo');
console.log(`\n===== TOTAL: ${total} assento(s) com problema =====`);
