// MODELO NOVO — bet chips + dealer. Valida 0 sobreposições nos 9 assentos.
const CX=560, CY=340, RX_SEAT=452, RY_SEAT=272;
const HW=84, HH=32;                 // meio-pod
const CARD_HW=64+6/2, CH=96;        // cartas (CW+CG/2=67)
const CARD_DY=Math.round(CH*0.67)-HH; // centro das cartas acima do centro do pod: cardCenterY = py - CARD_DY... (calc abaixo)
const CLU_HW=28, CLU_UP=30, CLU_DN=28; // cluster de fichas (acima/abaixo da âncora)
const DRX=20, DRY=12;
const GAP=14;
const VB={x1:4,y1:4,x2:1116,y2:638}; // viewBox; y2 folgado pois SVG usa overflow:visible (pod do hero já vive em ~644)

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
const boardBox={x1:CX-(5*68+4*8)/2,y1:CY-110/2-6,x2:CX+(5*68+4*8)/2,y2:CY+110/2-6};

// projeção do half-extent de uma box (centro cB, meio hwB/hhB) sobre u, somada
// ao deslocamento do centro da box relativo ao pod — dá a distância da borda
// distante da box ao longo de u, medida a partir do CENTRO do pod.
function farAlong(cBx,cBy, hwB,hhB, px,py, ux,uy){
  const d=(cBx-px)*ux+(cBy-py)*uy;       // centro da box projetado em u
  return d + hwB*Math.abs(ux)+hhB*Math.abs(uy);
}

function place(p){
  const dvx=CX-p.x, dvy=CY-p.y, len=Math.hypot(dvx,dvy)||1;
  const ux=dvx/len, uy=dvy/len;          // inboard (pod→centro)
  const tx=-uy, ty=ux;                    // tangente

  // far edge de (pod ∪ cartas) ao longo de u, a partir do centro do pod:
  const cardCY = (p.y-HH) - Math.round(CH*0.67) + CH/2; // centro vertical das cartas
  const podFar  = farAlong(p.x,p.y, HW,HH, p.x,p.y, ux,uy);
  const cardFar = farAlong(p.x,cardCY, CARD_HW,CH/2, p.x,p.y, ux,uy);
  const far = Math.max(podFar, cardFar);
  // âncora do cluster: far + GAP + meio-cluster, ao longo de u
  const cx = Math.round(p.x + (far+GAP+CLU_UP)*ux);
  const by = Math.round(p.y + (far+GAP+CLU_UP)*uy);

  // DEALER: "lateral, colado no pod". 4 candidatos (dir/esq/baixo/cima), colados
  // na borda do pod + GAP. Escolhe o válido (sem overlap c/ pod/cartas/fichas/board,
  // dentro do felt), preferindo o lado OUTBOARD (afastado do centro) e mais baixo.
  const cand=[
    {dx:Math.round(p.x+(HW+GAP+DRX)), dy:p.y},     // direita
    {dx:Math.round(p.x-(HW+GAP+DRX)), dy:p.y},     // esquerda
    {dx:p.x, dy:Math.round(p.y+(HH+GAP+DRY+7))},   // baixo
    {dx:p.x, dy:Math.round(p.y-(HH+GAP+DRY+7))},   // cima
  ];
  let best=null;
  for(const c of cand){
    const db=dlrBox(c.dx,c.dy);
    const bad = overlap(db,podBox(p),0)||overlap(db,cardBox(p),0)||overlap(db,cluBox(cx,by),0)||overlap(db,boardBox,0)||!inside(db);
    if(bad) continue;
    // score: outboard (longe do centro) + levemente preferindo abaixo do pod
    const outboard = Math.hypot(c.dx-CX, c.dy-CY);
    const score = outboard + (c.dy>p.y?12:0);
    if(!best||score>best.score) best={dx:c.dx,dy:c.dy,score};
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
    if(!r.dealer)iss.push('DEALER:nenhum-lado-valido');
    else {
      const db=dlrBox(r.dealer.dx,r.dealer.dy);
      if(overlap(db,cb,0))iss.push('DLR×CHIP');
      if(overlap(db,podBox(p),0))iss.push('DLR×POD');
      if(overlap(db,cardBox(p),0))iss.push('DLR×CARDS');
    }
    if(iss.length)bad++;
    const dl=r.dealer?`(${r.dealer.dx},${r.dealer.dy})`:'—';
    console.log(`${s} ${p.dir.padEnd(6)} pod(${String(p.x).padStart(4)},${String(p.y).padStart(3)}) chip(${String(r.cx).padStart(4)},${String(r.by).padStart(3)}) dlr${dl.padEnd(12)} ${iss.join(' ')||'ok'}`);
  }
  console.log(bad? `>>> ${bad} assento(s) com problema`:'>>> 0 sobreposições ✓');
}

validate([1,2,3,4,5,6,7,8,9],9,'9-max hero embaixo');
validate([1,2,3,4,5,6,7,8],8,'8-max');
validate([1,2,3,4,5,6],6,'6-max');
validate([1,2,3,4,5,6,7,8,9],4,'9-max hero no topo (seat 4)');
