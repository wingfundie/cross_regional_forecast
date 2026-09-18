'use strict';
const $ = id => document.getElementById(id);
const fmt = (n,d=2) => Number(n).toLocaleString('en-AU',{minimumFractionDigits:d,maximumFractionDigits:d});
const money = n => (n<0?'−$':'$')+fmt(Math.abs(n),n!==0&&Math.abs(n)<.005?4:2);
const colors={energy:'#83b6d9',scarcity:'#073c64',total:'#b08b42',teal:'#268a87',purple:'#7658c9',slate:'#66717e',pale:'#d9e7f1'};
const regionColors={NSW1:'#4c94df',QLD1:'#b08b42',SA1:'#7658c9',VIC1:'#268a87'};
const stateColors={neither:'#8da0ae',destination_only:'#268a87',origin_only:'#b44d5e',both:'#7658c9'};
const config={responsive:true,displaylogo:false,modeBarButtonsToRemove:['select2d','lasso2d','autoScale2d'],toImageButtonOptions:{format:'png',scale:2}};
function layout(ytitle,height=350){return {...BASE_LAYOUT,height,title:undefined,margin:{l:68,r:22,t:48,b:54},legend:{orientation:'h',x:0,y:1.14,font:{size:12}},xaxis:{...BASE_LAYOUT.xaxis,gridcolor:'#edf0f2',automargin:true},yaxis:{...BASE_LAYOUT.yaxis,title:{text:ytitle,font:{size:12}},gridcolor:'#e8edf1',zeroline:true,zerolinecolor:'#97a8b6',automargin:true},paper_bgcolor:'#fff',plot_bgcolor:'#fff',hovermode:'x unified'};}
const routes=[['VIC to NSW',false,'VIC → NSW'],['VIC to NSW',true,'NSW → VIC'],['NSW to QLD',false,'NSW → QLD'],['NSW to QLD',true,'QLD → NSW'],['VIC to SA',false,'VIC → SA'],['VIC to SA',true,'SA → VIC']];
const stateLabels={neither:'Neither region',destination_only:'Destination only',origin_only:'Origin only',both:'Both regions'};
function route(){const r=routes[+$('direction').value];return {base:r[0],sign:r[1]?-1:1,reverse:r[1],label:r[2]};}
function transformState(x,r){return {...x,state:r.reverse?({destination_only:'origin_only',origin_only:'destination_only'}[x.state]||x.state):x.state,spread_contribution:x.spread_contribution*r.sign,energy_contribution:x.energy_contribution*r.sign,scarcity_contribution:x.scarcity_contribution*r.sign};}
function updateHistory(){
 const r=route(),q=$('quarter').value;
 const rows=DATA.spreads.filter(x=>x.complete&&x.direction===r.base),v=rows.find(x=>x.quarter===q);
 if(!v)throw new Error('Missing history '+r.base+' '+q);
 $('selectedRoute').textContent=r.label+' · '+q;
 $('totalValue').textContent=money(r.sign*v.spread);$('energyValue').textContent=money(r.sign*v.energy);$('scarcityValue').textContent=money(r.sign*v.scarcity);$('quarterValue').textContent=money(r.sign*v.spread*v.hours);
 $('hoursNote').textContent=fmt(v.hours,0)+' delivery hours · one MW';
 Plotly.react('historyChart',[
  {type:'bar',name:'Capped energy',x:rows.map(x=>x.quarter),y:rows.map(x=>r.sign*x.energy),marker:{color:colors.energy},hovertemplate:'%{x}<br>Capped energy: $%{y:.2f}/MWh<extra></extra>'},
  {type:'bar',name:'Scarcity excess',x:rows.map(x=>x.quarter),y:rows.map(x=>r.sign*x.scarcity),marker:{color:colors.scarcity},hovertemplate:'%{x}<br>Scarcity excess: $%{y:.2f}/MWh<extra></extra>'},
  {type:'scatter',mode:'lines+markers',name:'Total spread',x:rows.map(x=>x.quarter),y:rows.map(x=>r.sign*x.spread),line:{color:colors.total,width:2},marker:{size:7},hovertemplate:'%{x}<br>Total: $%{y:.2f}/MWh<extra></extra>'}
 ],{...layout('AUD/MWh'),barmode:'relative'},config);
 const states=DATA.regimes.filter(x=>x.direction===r.base&&x.quarter===q).map(x=>transformState(x,r));
 const ordered=['neither','destination_only','origin_only','both'].map(s=>states.find(x=>x.state===s));
 $('regimeBody').innerHTML=ordered.map(x=>`<tr><th scope="row">${stateLabels[x.state]}</th><td>${fmt(x.hours)}</td><td>${fmt(x.frequency_pct,3)}%</td><td>${money(x.energy_contribution)}</td><td>${money(x.scarcity_contribution)}</td><td>${money(x.spread_contribution)}</td></tr>`).join('');
 $('identityCheck').textContent='Accounting check: '+money(r.sign*v.energy)+' + '+money(r.sign*v.scarcity)+' = '+money(r.sign*v.spread)+'/MWh (calculated before rounding).';
 const dominant=Math.abs(v.energy)>Math.abs(v.scarcity)?'capped energy':'scarcity excess';
 $('historyInsight').textContent='For '+r.label+' in '+q+', '+dominant+' was the larger component in absolute dollars. Components can offset; a percentage of total can become misleading when the net spread is small.';
 const allStates=DATA.regimes.filter(x=>x.direction===r.base&&rows.some(y=>y.quarter===x.quarter)).map(x=>transformState(x,r));
 Plotly.react('regimeChart',['neither','destination_only','origin_only','both'].map(state=>({type:'bar',name:stateLabels[state],x:rows.map(x=>x.quarter),y:rows.map(x=>(allStates.find(s=>s.quarter===x.quarter&&s.state===state)||{}).spread_contribution||0),marker:{color:stateColors[state]},hovertemplate:'%{x}<br>'+stateLabels[state]+': $%{y:.2f}/MWh<extra></extra>'})),{...layout('Contribution to quarterly spread · AUD/MWh',360),barmode:'relative'},config);
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
 $('impliedHours').textContent=fmt(hours)+' hours';$('scarcityInference').textContent='Under the selected severity and multiplicative risk loading, the destination cap is consistent with '+fmt(hours)+' scarcity hours. This is a scenario-implied quantity, not an identified market forecast.';$('infeasibleWarning').hidden=hours<=v.deliveryHours;
 const severityGrid=[250,500,1000,2000,4000,8000,16000,22900];
 Plotly.react('impliedChart',[{type:'scatter',mode:'lines+markers',name:'Consistent scarcity hours',x:severityGrid,y:severityGrid.map(s=>v.deliveryHours*physicalCap/s),line:{color:colors.scarcity},hovertemplate:'Mean excess $%{x:,.0f}/MWh<br>%{y:.2f} hours<extra></extra>'},{type:'scatter',mode:'markers',name:'Your assumption',x:[v.severity],y:[hours],marker:{color:colors.total,size:11},hovertemplate:'Your assumption<br>%{y:.2f} hours<extra></extra>'}],{...layout('Consistent scarcity hours',300),xaxis:{type:'log',title:{text:'Conditional mean excess above $300 · AUD/MWh',font:{size:12}},tickvals:[250,1000,4000,16000],ticktext:['250','1,000','4,000','16,000'],automargin:true}},config);
 const unitEdge=v.unitMean-v.unitFees-v.unitPrice-v.hurdle;$('unitEdge').textContent=money(unitEdge)+' / unit';$('unitBridge').textContent=money(v.unitMean)+' expected discounted distributions − '+money(v.unitFees)+' additional costs − '+money(v.unitPrice)+' purchase price − '+money(v.hurdle)+' valuation reserve = '+money(unitEdge)+'. Enter distributions net of the effective settlement rules; do not deduct fees twice.';
 const destinationPrices=[];for(let p=-100;p<=1100;p+=25)destinationPrices.push(p);
 const originSpot=v.baseA,basePayoff=destinationPrices.map(p=>p-originSpot),scarcityPayoff=destinationPrices.map(p=>Math.max(p-300,0)-Math.max(originSpot-300,0)),energyPayoff=destinationPrices.map((p,i)=>basePayoff[i]-scarcityPayoff[i]);
 Plotly.react('payoffChart',[
  {type:'scatter',mode:'lines',name:'Base spread',x:destinationPrices,y:basePayoff,line:{color:colors.total,width:2.5}},
  {type:'scatter',mode:'lines',name:'Capped-energy spread',x:destinationPrices,y:energyPayoff,line:{color:colors.energy,width:2.5}},
  {type:'scatter',mode:'lines',name:'Scarcity spread',x:destinationPrices,y:scarcityPayoff,line:{color:colors.scarcity,width:2.5}}
 ],{...layout('Illustrative realised payoff · AUD/MWh',350),xaxis:{title:{text:'Destination spot price · AUD/MWh',font:{size:12}},gridcolor:'#edf0f2',automargin:true},shapes:[{type:'line',x0:300,x1:300,y0:0,y1:1,yref:'paper',line:{color:'#8798a5',dash:'dot'}}],annotations:[{x:300,y:1,yref:'paper',text:'$300 strike',showarrow:false,yanchor:'bottom',font:{size:11,color:'#66717e'}}]},config);
}
function initEvidenceVisuals(){
 const quarters=[...new Set(DATA.spreads.filter(x=>x.complete).map(x=>x.quarter))],complete=DATA.regions.filter(x=>x.complete);
 Plotly.react('scarcityMap',Object.keys(regionColors).map(region=>{const rows=complete.filter(x=>x.region===region);return {type:'scatter',mode:'markers',name:region.replace('1',''),x:rows.map(x=>x.above300_hours),y:rows.map(x=>x.excess_when_above),text:rows.map(x=>x.quarter),customdata:rows.map(x=>[x.cap_excess,x.episodes,x.top5days_cap_pct]),marker:{color:regionColors[region],size:rows.map(x=>Math.max(8,Math.sqrt(Math.max(x.cap_excess,0))*4.3)),opacity:.78,line:{color:'#fff',width:1}},hovertemplate:'%{text}<br>%{x:.2f} hours above $300<br>$%{y:,.0f}/MWh mean excess<br>$%{customdata[0]:.2f}/MWh cap payout<br>%{customdata[1]:.0f} episodes<br>Top five days: %{customdata[2]:.1f}%<extra>%{fullData.name}</extra>'};}),{...layout('Conditional mean excess · AUD/MWh',390),hovermode:'closest',xaxis:{title:{text:'Hours above $300 in quarter',font:{size:12}},gridcolor:'#edf0f2',automargin:true}},config);
 const regionOrder=['NSW1','QLD1','SA1','VIC1'];
 Plotly.react('concentrationChart',[{type:'heatmap',x:quarters,y:regionOrder.map(r=>r.replace('1','')),z:regionOrder.map(region=>quarters.map(q=>{const x=complete.find(r=>r.region===region&&r.quarter===q);return x&&x.cap_excess>0?x.top5days_cap_pct:null;})),colorscale:[[0,'#e9f1f6'],[.5,'#83b6d9'],[1,'#073c64']],zmin:70,zmax:100,colorbar:{title:{text:'%',side:'right'},thickness:12},texttemplate:'%{z:.0f}%',hovertemplate:'%{y} · %{x}<br>Top five days: %{z:.1f}%<extra></extra>',hoverongaps:false}],{...layout('',320),margin:{l:60,r:35,t:30,b:48},xaxis:{side:'bottom',automargin:true},yaxis:{autorange:'reversed',automargin:true},hovermode:'closest'},config);
 function updateHeatmap(){
  const metric=$('heatMetric').value,canonical=[['VIC to NSW','NSW − VIC'],['NSW to QLD','QLD − NSW'],['VIC to SA','SA − VIC']];
  const z=canonical.map(([direction])=>quarters.map(q=>{const x=DATA.spreads.find(r=>r.complete&&r.direction===direction&&r.quarter===q);if(metric==='scarcity_share'){const den=Math.abs(x.energy)+Math.abs(x.scarcity);return den?100*Math.abs(x.scarcity)/den:null;}return x[metric];}));
  const share=metric==='scarcity_share',maxAbs=Math.max(...z.flat().filter(Number.isFinite).map(Math.abs));
  const compact=window.innerWidth<=600;
  Plotly.react('spreadHeatmap',[{type:'heatmap',x:quarters,y:canonical.map(x=>x[1]),z,colorscale:share?[[0,'#edf3f7'],[.5,'#83b6d9'],[1,'#073c64']]:[[0,'#b44d5e'],[.5,'#fff'],[1,'#073c64']],zmin:share?0:-maxAbs,zmax:share?100:maxAbs,zmid:share?undefined:0,showscale:!compact,colorbar:{title:{text:share?'%':'AUD/MWh',side:'right'},thickness:13},texttemplate:share?'%{z:.0f}%':'%{z:.1f}',hovertemplate:'%{y} · %{x}<br>'+({'spread':'Total spread','energy':'Capped energy','scarcity':'Scarcity excess','scarcity_share':'Scarcity share'}[metric])+': %{z:.2f}'+(share?'%':' AUD/MWh')+'<extra></extra>'}],{...layout('',340),margin:{l:compact?84:90,r:compact?6:48,t:25,b:compact?70:48},xaxis:{side:'bottom',automargin:true,tickangle:compact?-45:0,tickfont:{size:compact?10:12}},yaxis:{autorange:'reversed',automargin:true,tickfont:{size:compact?10:12}},hovermode:'closest'},config);
 }
 $('heatMetric').addEventListener('change',updateHeatmap);window.matchMedia('(max-width: 600px)').addEventListener('change',()=>setTimeout(updateHeatmap,150));updateHeatmap();
 const clean=s=>s.replaceAll('1','').replace(' to ',' → ');
 Plotly.react('flowBridge',[
  {type:'bar',orientation:'h',name:'Product of means',y:DATA.flows.map(x=>clean(x.direction)),x:DATA.flows.map(x=>x.product_means),marker:{color:colors.energy},customdata:DATA.flows.map(x=>[x.mean_effective_flow,x.mean_positive_spread]),hovertemplate:'%{y}<br>Product of means: $%{x:,.0f}/h<br>Mean effective flow: %{customdata[0]:.1f} MW<br>Mean positive spread: $%{customdata[1]:.2f}/MWh<extra></extra>'},
  {type:'bar',orientation:'h',name:'Flow–spread covariance',y:DATA.flows.map(x=>clean(x.direction)),x:DATA.flows.map(x=>x.covariance),marker:{color:colors.scarcity},customdata:DATA.flows.map(x=>x.tail_proxy_pct),hovertemplate:'%{y}<br>Covariance: $%{x:,.0f}/h<br>Tail proxy share: %{customdata:.1f}%<extra></extra>'}
 ],{...layout('Positive gross revenue proxy · AUD/hour',390),barmode:'stack',margin:{l:90,r:22,t:48,b:54},xaxis:{title:{text:'AUD/hour',font:{size:12}},gridcolor:'#edf0f2',automargin:true},yaxis:{autorange:'reversed',automargin:true}},config);
}
function jump(id){const el=$(id);if(!el)return;const d=el.closest('details');if(d)d.open=true;location.hash=id;el.scrollIntoView({behavior:'smooth',block:'start'});}
function initNavigation(){
 const chapters=[...document.querySelectorAll('details.chapter')];$('expandChapters').onclick=()=>chapters.forEach(d=>d.open=true);$('collapseChapters').onclick=()=>chapters.forEach(d=>d.open=false);$('printReport').onclick=()=>{chapters.forEach(d=>d.open=true);window.print();};
 document.querySelectorAll('a[href^="#"]').forEach(a=>a.addEventListener('click',e=>{const id=decodeURIComponent(a.hash.slice(1));if($(id)){e.preventDefault();jump(id);}}));
 const index=chapters.map(d=>({id:d.querySelector('h2').id,title:d.querySelector('h2').textContent,text:d.textContent.toLowerCase()}));
 $('reportSearch').addEventListener('input',()=>{const q=$('reportSearch').value.toLowerCase().trim(),found=q.length<2?[]:index.filter(x=>x.text.includes(q));const out=$('searchResults');out.replaceChildren();if(q.length>=2){const p=document.createElement('p');p.textContent=found.length+' matching chapters';out.append(p);found.forEach(x=>{const b=document.createElement('button');b.textContent=x.title;b.onclick=()=>jump(x.id);out.append(b);});}});
 const observer=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){document.querySelectorAll('.toc a').forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id));}});},{rootMargin:'-8% 0px -72% 0px'});document.querySelectorAll('h2[id]').forEach(h=>observer.observe(h));if(location.hash)requestAnimationFrame(()=>jump(decodeURIComponent(location.hash.slice(1))));window.addEventListener('beforeprint',()=>chapters.forEach(d=>d.open=true));
}
function init(){
 $('direction').innerHTML=routes.map((r,i)=>`<option value="${i}">${r[2]}</option>`).join('');const quarters=[...new Set(DATA.spreads.filter(x=>x.complete).map(x=>x.quarter))];['quarter','eventQuarter'].forEach(id=>{$(id).innerHTML=quarters.map(q=>`<option value="${q}">${q}</option>`).join('');$(id).value='2026Q2';});
 ['quarter','direction'].forEach(id=>$(id).addEventListener('change',updateHistory));['region','eventQuarter'].forEach(id=>$(id).addEventListener('change',updateRegion));document.querySelectorAll('#valuationLab input').forEach(el=>el.addEventListener('input',updateMarket));$('resetInputs').onclick=()=>{document.querySelectorAll('#valuationLab input').forEach(el=>el.value=el.defaultValue);updateMarket();};
 updateHistory();updateRegion();updateMarket();initEvidenceVisuals();initNavigation();document.documentElement.classList.add('ready');
}
init();
