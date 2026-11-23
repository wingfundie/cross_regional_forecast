/* Offline evidence explorer. External participant text is always escaped. */
(async function(){
  const el=id=>document.getElementById(id),esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>x===null||x===undefined?'—':Number(x).toLocaleString('en-AU',{maximumFractionDigits:2});
  const tm=x=>x?x.replace('T',' ').slice(5,19):'—';
  try{
    const bytes=Uint8Array.from(atob(el('embedded-data').textContent.trim()),c=>c.charCodeAt(0));
    const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    const data=JSON.parse(await new Response(stream).text());
    window.rebidDataCounts={revisions:data.revisions.length,segments:data.segments.length};
    const byOffer=new Map(),byUnit=new Map(),byEff=new Map(),byForecast=new Map(),bySnapshot=new Map();
    for(const s of data.segments){const id=s[0];if(!byOffer.has(id))byOffer.set(id,[]);byOffer.get(id).push(s);}
    for(const [arr,map] of [[data.panel,byUnit],[data.effective,byEff],[data.forecast,byForecast],[data.snapshots,bySnapshot]])for(const s of arr){if(!map.has(s.DUID))map.set(s.DUID,[]);map.get(s.DUID).push(s);}
    const revById=new Map(data.revisions.map(r=>[r.offer_id,r]));
    for(const name of ['region','technology','controller','plant'])for(const value of [...new Set(data.revisions.map(r=>r[name]))].sort()){const o=document.createElement('option');o.value=value;o.textContent=value;el(name).appendChild(o);}
    let page=0,filtered=[],selected=null;
    const config={responsive:true,displaylogo:false};
    const layout=(title,ylabel,height=430)=>({title:{text:title,x:.03,font:{size:18}},height,margin:{l:70,r:30,t:85,b:70},paper_bgcolor:'white',plot_bgcolor:'#ececf3',font:{family:'Arial',size:12,color:'#444'},legend:{orientation:'h',y:1.03},xaxis:{gridcolor:'white'},yaxis:{title:{text:ylabel},gridcolor:'white'},colorway:['#5696b9','#ce9a48','#8370b4','#268a87'],hovermode:'x unified'});
    function filter(){
      const q=el('query').value.toLowerCase(),from=el('from').value,to=el('to').value;
      filtered=data.revisions.filter(r=>['region','technology','controller','plant','direction'].every(k=>!el(k).value||r[k]===el(k).value)&&(!el('block').value||r.blocks.includes(el('block').value))&&(!from||r.offer_time>=from)&&(!to||r.offer_time<=to+':59')&&(!q||(r.reason+' '+r.DUID).toLowerCase().includes(q))).sort((a,b)=>a.offer_time.localeCompare(b.offer_time));
      page=0;render();
    }
    function render(){
      el('count').textContent=`${filtered.length.toLocaleString()} matching revisions · showing ${filtered.length?page*50+1:0}–${Math.min((page+1)*50,filtered.length)}. All power movements are MW.`;
      el('revisions').innerHTML=filtered.slice(page*50,(page+1)*50).map(r=>`<tr><td><button data-id="${esc(r.offer_id)}">${esc(r.offer_id)}</button></td><td>${tm(r.offer_time)}</td><td>${esc(r.plant)}<br>${esc(r.DUID)}</td><td>${esc(r.direction)}</td><td>${num(r.peak_abs_le300_mw)}</td><td>${esc(r.reason)}</td></tr>`).join('');
      el('previous').disabled=page===0;el('next').disabled=(page+1)*50>=filtered.length;
      el('revisions').querySelectorAll('[data-id]').forEach(b=>b.addEventListener('click',()=>selectOffer(b.dataset.id)));
    }
    function selectOffer(id){
      const r=revById.get(id);if(!r)return;selected=r;
      const segments=(byOffer.get(id)||[]).map(row=>Object.fromEntries(data.segment_columns.map((c,i)=>[c,row[i]])));
      el('detail').innerHTML=`<h3>${esc(r.DUID)} · ${esc(r.offer_id)} · ${tm(r.offer_time)}</h3><p><b>Verbatim reason:</b> ${esc(r.reason)}</p><p>Participant-supplied clocks — event ${esc(r.REBID_EVENT_TIME)}, awareness ${esc(r.REBID_AWARE_TIME)}, decision ${esc(r.REBID_DECISION_TIME)}. Category ${esc(r.REBID_CATEGORY)}; reference ${esc(r.REFERENCE_ID)}. These time-only fields remain unvalidated; a calendar date is not inferred.</p><p>Previous offer: ${esc(r.previous_offer_id)}. ${r.future_changed_intervals} changed future intervals; ${r.past_changed_intervals} changed running/elapsed intervals. Observed category: ${esc(r.reason_category)}. A reason category does not establish strategic intent.</p>`+
        (segments.length?`<label>Inspect a changed delivery segment <select id="segment-choice">${segments.map((s,i)=>`<option value="${i}">${tm(s.delivery_from)} → ${tm(s.delivery_to)} · ${esc(s.block)} · ${s.future_at_offer?'future at submission':'already started/elapsed'}</option>`).join('')}</select></label><div id="band-table"></div>`:'<p>No band or period-parameter change relative to the previous accepted offer. The reason/revision is still retained.</p>');
      if(segments.length){el('segment-choice').addEventListener('change',()=>drawSegment(segments[Number(el('segment-choice').value)]));drawSegment(segments[0]);}else Plotly.purge('stackplot');
      drawUnit(r.DUID,r.direction);
    }
    function drawSegment(s){
      let rows='';for(let i=0;i<10;i++)rows+=`<tr><td>${i+1}</td><td>${num(s.before_prices[i])}</td><td>${num(s.after_prices[i])}</td><td>${num(s.before_bands[i])}</td><td>${num(s.after_bands[i])}</td><td>${num(s.after_bands[i]-s.before_bands[i])}</td></tr>`;
      el('band-table').innerHTML=`<p>Availability ${num(s.before_maxavail)} → ${num(s.after_maxavail)} MW; offered ramp capability over five minutes ${num(s.before_rampup*5)} → ${num(s.after_rampup*5)} MW. Minimum identifiable redistribution ${num(s.minimum_redistribution_mw)} MW; net added offered volume ${num(s.added_offered_mw)} MW; net removed ${num(s.removed_offered_mw)} MW.</p><div class="table-wrap"><table><thead><tr><th>Band</th><th>Before price ($/MWh)</th><th>After price ($/MWh)</th><th>Before (MW)</th><th>After (MW)</th><th>Change (MW)</th></tr></thead><tbody>${rows}</tbody></table></div>`;
      function curve(vol,prices,name){let x=[0],y=[prices[0]],total=0;for(let i=0;i<10;i++){x.push(total);y.push(prices[i]);total+=vol[i];x.push(total);y.push(prices[i]);}return{x,y,name,mode:'lines',line:{width:3}};}
      const l=layout(`${esc(s.DUID)} ${esc(s.direction)} offer stack · ${tm(s.delivery_from)}–${tm(s.delivery_to)}`,'Offer price ($/MWh)');l.xaxis.title={text:'Cumulative offered MW'};l.hovermode='closest';
      Plotly.react('stackplot',[curve(s.before_bands,s.before_prices,'Before'),curve(s.after_bands,s.after_prices,'After')],l,config);
    }
    function drawUnit(duid,direction){
      const p=(byUnit.get(duid)||[]).sort((a,b)=>a.delivery.localeCompare(b.delivery)),ef=(byEff.get(duid)||[]).filter(x=>x.direction===direction),f=byForecast.get(duid)||[];
      const traces=[['actual_mw','Observed MW'],['target_mw','Dispatch target MW'],['baseline_mw','Pre-signal observed reference']].map(([key,name])=>({x:p.map(x=>x.delivery),y:p.map(x=>x[key]),name,mode:'lines',connectgaps:false}));
      traces.push({x:ef.map(x=>x.delivery),y:ef.map(x=>x.maxavail),name:`${direction} offered availability`,mode:'lines',line:{dash:'dot'}});
      traces.push({x:f.map(x=>x.delivery),y:f.map(x=>x.forecast_mw),name:'Pre-signal AEMO projection',mode:'markers',marker:{size:5}});
      const l=layout(`${duid} · willingness, instruction and observed output`,'Power (MW)',490);l.shapes=[{type:'line',xref:'x',yref:'paper',x0:'2026-10-10T07:15:13',x1:'2026-10-10T07:15:13',y0:0,y1:1,line:{color:'#af4260',dash:'dash'}}];
      if(p.some(x=>x.soc_quality==='capacity-matched')){traces.push({x:p.map(x=>x.delivery),y:p.map(x=>x.soc_quality==='capacity-matched'?x.initial_soc_pct:null),name:'Initial storage (%)',mode:'lines',yaxis:'y2',visible:'legendonly'});l.yaxis2={title:{text:'Storage (%)'},overlaying:'y',side:'right',range:[0,100],showgrid:false};l.margin.r=70;}
      Plotly.react('unitplot',traces,l,config);
      if(direction==='LOAD'){Plotly.purge('heatplot');el('heatplot').textContent='Charging bids express willingness to buy: inspect the LOAD price/volume table and stack above. The generation-only low-price heatmap is hidden for LOAD to avoid reversing the economic interpretation.';return;}
      Plotly.purge('heatplot');el('heatplot').textContent='';
      const ss=(bySnapshot.get(duid)||[]).filter(x=>x.direction===direction),labels=['pre_signal','plus15','plus30','plus60','evening_entry','overnight_entry'];
      const base=new Map(ss.filter(x=>x.snapshot==='pre_signal').map(x=>[x.delivery,x.le_300]));
      const x=[...base.keys()].sort(),z=labels.map(label=>{const m=new Map(ss.filter(s=>s.snapshot===label).map(s=>[s.delivery,s.le_300]));return x.map(t=>m.has(t)?m.get(t)-base.get(t):null);});
      const hl=layout(`${duid} · same-delivery offer change from pre-signal (MW ≤$300)`,'Offer snapshot',400);hl.margin.l=125;hl.hovermode='closest';
      Plotly.react('heatplot',[{type:'heatmap',x,y:labels,z,colorscale:'RdBu',zmid:0,colorbar:{title:{text:'MW'}},hovertemplate:'Delivery %{x}<br>Snapshot %{y}<br>Change %{z} MW<extra></extra>'}],hl,config);
    }
    for(const id of ['region','technology','controller','plant','direction','block','from','to','query'])el(id).addEventListener(id==='query'?'input':'change',filter);
    el('previous').addEventListener('click',()=>{page--;render();});el('next').addEventListener('click',()=>{page++;render();});
    document.querySelectorAll('[data-offer]').forEach(a=>a.addEventListener('click',()=>selectOffer(a.dataset.offer)));
    filter();const first=filtered.find(r=>r.DUID==='TALWB1')||filtered.find(r=>r.DUID==='MP1')||filtered[0];if(first)selectOffer(first.offer_id);
    window.rebidExplorerReady=true;
  }catch(error){el('count').textContent='Explorer could not initialise: '+error.message+'. Use the accompanying evidence downloads.';console.error(error);}
})();
