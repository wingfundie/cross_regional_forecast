'use strict';
const $ = id => document.getElementById(id);
const fmt = (n,d=2) => Number(n).toLocaleString('en-AU',{minimumFractionDigits:d,maximumFractionDigits:d});
const money = n => (n<0?'−$':'$')+fmt(Math.abs(n),n!==0&&Math.abs(n)<.005?4:2);
const colors={energy:'#83b6d9',scarcity:'#073c64',total:'#b08b42'};
const config={responsive:true,displaylogo:false,modeBarButtonsToRemove:['select2d','lasso2d','autoScale2d'],toImageButtonOptions:{format:'png',scale:2}};
function layout(ytitle,height=350){return {...BASE_LAYOUT,height,title:undefined,margin:{l:68,r:22,t:48,b:54},legend:{orientation:'h',x:0,y:1.14,font:{size:12}},xaxis:{...BASE_LAYOUT.xaxis,gridcolor:'#edf0f2',automargin:true},yaxis:{...BASE_LAYOUT.yaxis,title:{text:ytitle,font:{size:12}},gridcolor:'#e8edf1',zeroline:true,zerolinecolor:'#97a8b6',automargin:true},paper_bgcolor:'#fff',plot_bgcolor:'#fff',hovermode:'x unified'};}
const routes=[['VIC to NSW',false,'VIC → NSW'],['VIC to NSW',true,'NSW → VIC'],['NSW to QLD',false,'NSW → QLD'],['NSW to QLD',true,'QLD → NSW'],['VIC to SA',false,'VIC → SA'],['VIC to SA',true,'SA → VIC']];
function route(){const r=routes[+$('direction').value];return {base:r[0],sign:r[1]?-1:1,reverse:r[1],label:r[2]};}
function updateHistory(){
 const r=route(),q=$('quarter').value;
 const rows=DATA.spreads.filter(x=>x.complete&&x.direction===r.base),v=rows.find(x=>x.quarter===q);
 if(!v)throw new Error('Missing history '+r.base+' '+q);
 $('selectedRoute').textContent=r.label+' · '+q;
 $('totalValue').textContent=money(r.sign*v.spread);
 $('energyValue').textContent=money(r.sign*v.energy);
 $('scarcityValue').textContent=money(r.sign*v.scarcity);
 $('quarterValue').textContent=money(r.sign*v.spread*v.hours);
 $('hoursNote').textContent=fmt(v.hours,0)+' delivery hours · one MW';
 Plotly.react('historyChart',[
 {type:'bar',name:'Capped energy',x:rows.map(x=>x.quarter),y:rows.map(x=>r.sign*x.energy),marker:{color:colors.energy},hovertemplate:'%{x}<br>Capped energy: $%{y:.2f}/MWh<extra></extra>'},
 {type:'bar',name:'Scarcity excess',x:rows.map(x=>x.quarter),y:rows.map(x=>r.sign*x.scarcity),marker:{color:colors.scarcity},hovertemplate:'%{x}<br>Scarcity excess: $%{y:.2f}/MWh<extra></extra>'},
 {type:'scatter',mode:'lines+markers',name:'Total spread',x:rows.map(x=>x.quarter),y:rows.map(x=>r.sign*x.spread),line:{color:colors.total,width:2},marker:{size:7},hovertemplate:'%{x}<br>Total: $%{y:.2f}/MWh<extra></extra>'}
 ],{...layout('AUD/MWh'),barmode:'relative'},config);
 const states=DATA.regimes.filter(x=>x.direction===r.base&&x.quarter===q).map(x=>({...x,state:r.reverse?({destination_only:'origin_only',origin_only:'destination_only'}[x.state]||x.state):x.state,spread_contribution:x.spread_contribution*r.sign,energy_contribution:x.energy_contribution*r.sign,scarcity_contribution:x.scarcity_contribution*r.sign}));
 const labels={neither:'Neither region',destination_only:'Destination only',origin_only:'Origin only',both:'Both regions'};
 const ordered=['neither','destination_only','origin_only','both'].map(s=>states.find(x=>x.state===s));
 $('regimeBody').innerHTML=ordered.map(x=>`<tr><th scope="row">${labels[x.state]}</th><td>${fmt(x.hours)}</td><td>${fmt(x.frequency_pct,3)}%</td><td>${money(x.energy_contribution)}</td><td>${money(x.scarcity_contribution)}</td><td>${money(x.spread_contribution)}</td></tr>`).join('');
 $('identityCheck').textContent='Accounting check: '+money(r.sign*v.energy)+' + '+money(r.sign*v.scarcity)+' = '+money(r.sign*v.spread)+'/MWh (calculated before rounding).';
 const dominant=Math.abs(v.energy)>Math.abs(v.scarcity)?'capped energy':'scarcity excess';
 $('historyInsight').textContent='For '+r.label+' in '+q+', '+dominant+' was the larger component in absolute dollars. Components can offset; a percentage of total can become misleading when the net spread is small.';
}
function updateRegion(){
 const region=$('region').value,quarter=$('eventQuarter').value;
 const rows=DATA.regions.filter(x=>x.complete&&x.region===region),v=rows.find(x=>x.quarter===quarter);
 $('eventHours').textContent=fmt(v.above300_hours)+' h';$('eventSeverity').textContent=money(v.excess_when_above);$('eventCap').textContent=money(v.cap_excess);$('eventConcentration').textContent=fmt(v.top5days_cap_pct,1)+'%';
 $('eventIdentity').textContent=region.replace('1','')+' · '+quarter+': '+fmt(v.above300_pct,3)+'% of intervals × '+money(v.excess_when_above)+' mean excess = '+money(v.cap_excess)+'/MWh cap payout. '+fmt(v.episodes,0)+' strict five-minute episodes; episode count is sensitive to the gap definition.';
 Plotly.react('eventChart',[
 {type:'bar',name:'Hours above $300 (left)',x:rows.map(x=>x.quarter),y:rows.map(x=>x.above300_hours),marker:{color:colors.energy},hovertemplate:'%{x}<br>%{y:.2f} hours<extra></extra>'},
 {type:'scatter',mode:'lines+markers',name:'Cap payout (right)',x:rows.map(x=>x.quarter),y:rows.map(x=>x.cap_excess),yaxis:'y2',line:{color:colors.scarcity,width:2},hovertemplate:'%{x}<br>$%{y:.2f}/MWh cap payout<extra></extra>'}
 ],{...layout('Hours above $300'),margin:{l:65,r:68,t:48,b:54},yaxis2:{title:{text:'Cap payout · AUD/MWh',font:{size:12}},overlaying:'y',side:'right',showgrid:false,zeroline:false}},config);
}
function inputs(ids){return Object.fromEntries(ids.map(id=>[id,$(id).value.trim()===''?NaN:Number($(id).value)]));}
function updateMarket(){
 const v=inputs(['baseA','baseB','capA','capB','deliveryHours','severity','rho','physicalSpread','unitPrice','unitMean','unitFees','hurdle']);
 const valid=Object.values(v).every(Number.isFinite)&&v.capA>=0&&v.capB>=0&&v.deliveryHours>0&&v.severity>0&&v.rho>-1&&v.unitPrice>=0&&v.unitMean>=0&&v.unitFees>=0;
 $('calcError').hidden=valid;if(!valid)return;
 const total=v.baseB-v.baseA,scarcity=v.capB-v.capA,energy=total-scarcity,physicalCap=v.capB/(1+v.rho),hours=v.deliveryHours*physicalCap/v.severity;
 $('marketTotal').textContent=money(total);$('marketEnergy').textContent=money(energy);$('marketScarcity').textContent=money(scarcity);$('marketEdge').textContent=money(v.physicalSpread-total);
 $('longShort').textContent='Long destination B; short origin A. Delivery value: '+money(total*v.deliveryHours)+' per MW-quarter. Inputs are illustrative until you enter matched, dated quotes.';
 $('impliedHours').textContent=fmt(hours)+' hours';
 $('scarcityInference').textContent='Under the selected severity and multiplicative risk loading, the destination cap is consistent with '+fmt(hours)+' scarcity hours. This is a scenario-implied quantity, not an identified market forecast.';
 $('infeasibleWarning').hidden=hours<=v.deliveryHours;
 const severityGrid=[250,500,1000,2000,4000,8000,16000,22900];
 Plotly.react('impliedChart',[{type:'scatter',mode:'lines+markers',name:'Consistent scarcity hours',x:severityGrid,y:severityGrid.map(s=>v.deliveryHours*physicalCap/s),line:{color:colors.scarcity},hovertemplate:'Mean excess $%{x:,.0f}/MWh<br>%{y:.2f} hours<extra></extra>'},{type:'scatter',mode:'markers',name:'Your assumption',x:[v.severity],y:[hours],marker:{color:colors.total,size:11},hovertemplate:'Your assumption<br>%{y:.2f} hours<extra></extra>'}],{...layout('Consistent scarcity hours',300),xaxis:{type:'log',title:{text:'Conditional mean excess above $300 · AUD/MWh',font:{size:12}},tickvals:[250,1000,4000,16000],ticktext:['250','1,000','4,000','16,000'],automargin:true}},config);
 const unitEdge=v.unitMean-v.unitFees-v.unitPrice-v.hurdle;
 $('unitEdge').textContent=money(unitEdge)+' / unit';
 $('unitBridge').textContent=money(v.unitMean)+' expected discounted distributions − '+money(v.unitFees)+' additional costs − '+money(v.unitPrice)+' purchase price − '+money(v.hurdle)+' valuation reserve = '+money(unitEdge)+'. Enter distributions net of the effective settlement rules; do not deduct fees twice.';
}
function jump(id){const el=$(id);if(!el)return;const d=el.closest('details');if(d)d.open=true;location.hash=id;el.scrollIntoView({behavior:'smooth',block:'start'});}
function initNavigation(){
 const chapters=[...document.querySelectorAll('details.chapter')];
 $('expandChapters').onclick=()=>chapters.forEach(d=>d.open=true);
 $('collapseChapters').onclick=()=>chapters.forEach(d=>d.open=false);
 $('printReport').onclick=()=>{chapters.forEach(d=>d.open=true);window.print();};
 document.querySelectorAll('a[href^="#"]').forEach(a=>a.addEventListener('click',e=>{const id=decodeURIComponent(a.hash.slice(1));if($(id)){e.preventDefault();jump(id);}}));
 const index=chapters.map(d=>({id:d.querySelector('h2').id,title:d.querySelector('h2').textContent,text:d.textContent.toLowerCase()}));
 $('reportSearch').addEventListener('input',()=>{const q=$('reportSearch').value.toLowerCase().trim(),found=q.length<2?[]:index.filter(x=>x.text.includes(q));const out=$('searchResults');out.replaceChildren();if(q.length>=2){const p=document.createElement('p');p.textContent=found.length+' matching chapters';out.append(p);found.forEach(x=>{const b=document.createElement('button');b.textContent=x.title;b.onclick=()=>jump(x.id);out.append(b);});}});
 const observer=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){document.querySelectorAll('.toc a').forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id));}});},{rootMargin:'-8% 0px -72% 0px'});
 document.querySelectorAll('h2[id]').forEach(h=>observer.observe(h));
 if(location.hash)requestAnimationFrame(()=>jump(decodeURIComponent(location.hash.slice(1))));
 window.addEventListener('beforeprint',()=>chapters.forEach(d=>d.open=true));
}
function init(){
 $('direction').innerHTML=routes.map((r,i)=>`<option value="${i}">${r[2]}</option>`).join('');
 const quarters=[...new Set(DATA.spreads.filter(x=>x.complete).map(x=>x.quarter))];
 ['quarter','eventQuarter'].forEach(id=>{$(id).innerHTML=quarters.map(q=>`<option value="${q}">${q}</option>`).join('');$(id).value='2026Q2';});
 ['quarter','direction'].forEach(id=>$(id).addEventListener('change',updateHistory));
 ['region','eventQuarter'].forEach(id=>$(id).addEventListener('change',updateRegion));
 document.querySelectorAll('#valuationLab input').forEach(el=>el.addEventListener('input',updateMarket));
 $('resetInputs').onclick=()=>{document.querySelectorAll('#valuationLab input').forEach(el=>el.value=el.defaultValue);updateMarket();};
 updateHistory();updateRegion();updateMarket();initNavigation();
 document.documentElement.classList.add('ready');
}
init();
