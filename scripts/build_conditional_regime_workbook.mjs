// Typed companion export. The Python package remains the calculation engine.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [payloadPath, outputPath] = process.argv.slice(2);
if (!payloadPath || !outputPath) throw new Error('Pass workbook_payload.json and output.xlsx');
const payload = JSON.parse(await fs.readFile(payloadPath, 'utf8'));
const outputDir = path.dirname(outputPath);
await fs.mkdir(outputDir, { recursive: true });
const wb = Workbook.create();
const names = ['Selected profile','Quarterly reference','Conditional profiles','Validation','Conditions','Events','ReadMe'];
const sheets = Object.fromEntries(names.map(n => [n, wb.worksheets.add(n)]));
const ink = '#282B30', blue = '#286C95', pale = '#ECECF3';
const qa = [];
function column(n){ let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s; }
function clean(v){if(v===undefined||v===null)return null;if(typeof v==='number')return Number.isFinite(v)?v:null;return typeof v==='object'?JSON.stringify(v):v;}
function sheetTable(name,title,columns,rows,note=''){
  const s=sheets[name]; s.showGridLines=false;
  s.getRange('A2').values=[[title]];
  s.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:ink};
  s.getRange(`A3:${column(columns.length)}3`).format={borders:{bottom:{style:'thin',color:'#4C94DF'}}};
  if(note){s.getRange('A4').values=[[note]];s.getRange(`A4:${column(columns.length)}4`).format.rowHeight=22;s.getRange('A4').format.font={name:'Arial',size:10,color:'#636870'};}
  const data=[columns.map(x=>x[0]),...rows.map(r=>columns.map(c=>clean(typeof c[1]==='function'?c[1](r):r[c[1]])))];
  const last=6+data.length;
  s.getRange(`A7:${column(columns.length)}${last}`).values=data;
  const all=s.getRange(`A7:${column(columns.length)}${last}`);
  all.format.font={name:'Arial',size:10,color:ink};
  all.format.rowHeight=20;all.format.verticalAlignment='center';
  s.getRange(`A7:${column(columns.length)}7`).format={fill:blue,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',rowHeight:34,wrapText:true};
  for(let i=0;i<columns.length;i++){
    const letter=column(i+1),config=columns[i];
    s.getRange(`${letter}7:${letter}${last}`).format.columnWidth=config[2]||17;
    if(config[3])s.getRange(`${letter}8:${letter}${last}`).setNumberFormat(config[3]);
  }
  if(data.length>25){s.freezePanes.freezeRows(7);s.freezePanes.freezeColumns(name==='Conditional profiles'||name==='Quarterly reference'?3:1);}
  if(rows.length){const table=s.tables.add(`A7:${column(columns.length)}${last}`,true,name.replaceAll(' ','')+'Table');}
  return {s,last};
}
const timeValue=r=>r.half_hour/48;
const main=sheetTable('Selected profile','Conditional limit profile · historical example',[
  ['Ending time',r=>String(Math.floor(r.half_hour/2)).padStart(2,'0')+':'+(r.half_hour%2?'30':'00'),14],['P10 MW','p10_mw',12,'#,##0.0'],['P50 MW','p50_mw',12,'#,##0.0'],['P90 MW','p90_mw',12,'#,##0.0'],
  ['Tight P10 MW','tight_p10_mw',14,'#,##0.0'],['Evidence status','status',22],['Analogue days','analogue_days',12,'0'],['Episodes','outage_episodes',10,'0'],
  ['Conditions relaxed',r=>r.relaxed_conditions,26]
],payload.selected,`VNI forward · Q1 · pre-PEC-market era · example scenario · observations through ${payload.data_end}`);
main.s.tabColor=blue;
main.s.getRange('A5').values=[['Bundle: '+payload.bundle_id]];
main.s.getRange('J7').values=[['Band width MW']];main.s.getRange('J7').format={fill:blue,font:{name:'Arial',bold:true,color:'#FFFFFF'},columnWidth:14,rowHeight:34,wrapText:true};
if(payload.selected.length){main.s.getRange('J8').formulas=[['=D8-B8']];main.s.getRange(`J8:J${main.last}`).fillDown();main.s.getRange(`J8:J${main.last}`).setNumberFormat('#,##0.0');}
main.s.getRange('L3').values=[['Lowest P10 MW']];main.s.getRange('M3').formulas=[[`=MIN(B8:B${main.last})`]];
main.s.getRange('L4').values=[['Profile median P50 MW']];main.s.getRange('M4').formulas=[[`=MEDIAN(C8:C${main.last})`]];
main.s.getRange('L3:M4').format.font={name:'Arial',size:11,color:ink};main.s.getRange('L3:L4').format.columnWidth=26;main.s.getRange('M3:M4').format.columnWidth=17;main.s.getRange('M3:M4').setNumberFormat('#,##0.0');
const chart=main.s.charts.add('line',main.s.getRange(`A7:D${main.last}`));
chart.title='Conditional range by interval ending time';chart.titleTextStyle.typeface='Arial';chart.hasLegend=true;
chart.xAxis={axisType:'textAxis',textStyle:{typeface:'Arial',fontSize:10}};
chart.yAxis={numberFormatCode:'#,##0',numberFormatSourceLinked:false,textStyle:{typeface:'Arial',fontSize:10}};
chart.setPosition('L7','U25');
const profileColumns=[['Connector','connector',16],['Direction','direction',15],['Era','era',21],['Quarter','quarter',12,'0'],['Ending time',timeValue,14,'hh:mm'],
  ['P10 MW','p10_mw',15,'#,##0.0'],['P50 MW','p50_mw',15,'#,##0.0'],['P90 MW','p90_mw',15,'#,##0.0'],['Tight P10 MW','tight_p10_mw',17,'#,##0.0'],
  ['Days','days',12,'0'],['Episodes','episodes',12,'0'],['Evidence','status',16]];
sheetTable('Quarterly reference','Quarterly diurnal reference',profileColumns,payload.reference,'Calendar quarters; signed reported limits. Keep network/market eras separate when filtering.');
sheetTable('Conditional profiles','Named conditional profiles',[...profileColumns,['Condition','regime',34],['Forced share','forced_share',16,'0.0%'],['Restricted share','restricted_share',18,'0.0%'],['Condition definition','conditions',68]],payload.conditional,'Overlapping conditions. Indicative cells remain visible; effects are not independent additive deductions.');
sheetTable('Validation','Chronological conditional evaluation',[
  ['Connector','connector',16],['Direction','direction',15],['Method','method',19],['Matched rows','n',16,'#,##0'],['MAE MW','mae',16,'#,##0.0'],
  ['Bias MW','bias',15,'#,##0.0'],['Quantile loss','pinball',16,'#,##0.0'],['80% coverage','coverage80',18,'0.0%'],['80% width MW','width80',18,'#,##0.0'],
  ['P95 overstatement MW','p95_overstatement',24,'#,##0.0'],['Restriction recall','restriction_recall',22,'0.0%'],['False alerts/day','false_alerts_per_day',20,'0.00'],['Forced recall','forced_recall',19,'0.0%']
],payload.validation,'Known-state conditional research. Historical measured-receipt as-of evaluation is unavailable.');
const conditionSheet=sheetTable('Conditions','Measurable condition dictionary',[
  ['Condition','condition',34],['Units','units',12],['Historical coverage','historical_coverage',23,'0.0%'],['Source','source',75],['Availability','availability',100]
],payload.conditions,'Missing quantities stay unavailable. Electrical group membership and source coverage are recorded in the accompanying evidence.');
conditionSheet.s.getRange(`D8:E${conditionSheet.last}`).format.wrapText=true;conditionSheet.s.getRange(`A8:E${conditionSheet.last}`).format.rowHeight=42;
const eventSheet=sheetTable('Events','Event hypotheses and source evidence',[
  ['Event date',r=>Date.parse(r.start+'T00:00:00Z')/86400000+25569,16,'dd mmm yyyy'],['Case','title',58],['Links',r=>r.connectors.join(', '),32],
  ['Classification','classification',32],['Candidate conditions',r=>r.conditions.join('; '),85],['Source URL','url',100],['Interpretation','interpretation',110]
],payload.events,'WattClarity cases nominate hypotheses; dispatch evidence determines numerical ranges. Articles may be published after the event.');
eventSheet.s.getRange(`B8:G${eventSheet.last}`).format.wrapText=true;eventSheet.s.getRange(`A8:G${eventSheet.last}`).format.rowHeight=56;
const notes=[
  ['Purpose','Conditional distributions of AEMO reported dispatch limits, not maximum secure physical capability.'],
  ['Data cutoff',payload.data_end+' fixed NEM time (UTC+10)'],['Bundle identity',payload.bundle_id],
  ['Calendar quarters','Q1 Jan–Mar; Q2 Apr–Jun; Q3 Jul–Sep; Q4 Oct–Dec.'],
  ['Interval convention','Interval ending. 00:00 is half-hour 0; 23:30 is half-hour 47. Native five-minute observations are preserved.'],
  ['Targets','Main target: mean of all six five-minute directional limits. Tight target: minimum of those six. Incomplete half-hours are excluded.'],
  ['Signed limits','Reverse capacity is minus raw IMPORTLIMIT. Negative values can encode forced flow and are retained.'],
  ['Status','Supported analogue, broader analogue, modelled extrapolation and unavailable have different evidence. Inspect dates, episodes and relaxed conditions.'],
  ['Support convention','20 exact-condition days; outage-specific results also need 5 linked episodes. This does not establish tail calibration.'],
  ['Structural changes','Basslink separates MNSP and regulated eras at 1 July 2026; southern links separate the PEC market change at 1 October 2026.'],
  ['Current data gap','Complete October invocation and some geographic unit features are unavailable. Booked outages are not substituted for invocations.'],
  ['Refresh','This workbook contains Python-exported results. Run a new package query for new combinations, then refresh/rebuild the export. Editing labels does not run a model.'],
  ['Summary formulas','The selected-profile band widths, minimum P10 and median P50 link to exported values and recalculate in Excel.'],
  ['As-of evidence','Historical measured-receipt scorecard has zero eligible rows. New automatic suggestions retain receipt and vintage evidence.'],
  ['Primary data','https://nemweb.com.au/ · campaign source_manifest.json and condition_dictionary.csv'],
  ['Research and runbooks','Open reports/conditional_regimes_v1/index.html and its four downloadable runbooks.'],
  ['Source changes','Source, modelling and protocol changes invalidate dependent fits. Presentation rebuilds use cached evidence.']
];
sheetTable('ReadMe','Definitions and refresh instructions',[['Topic',r=>r[0],25],['Definition / action',r=>r[1],145]],notes);
sheets.ReadMe.getRange(`B8:B${7+notes.length}`).format.wrapText=true;sheets.ReadMe.getRange(`A8:B${7+notes.length}`).format.rowHeight=42;
wb.recalculate();
const key=await wb.inspect({kind:'table',range:'Selected profile!A7:J12',include:'values,formulas',tableMaxRows:6,tableMaxCols:10,maxChars:3500});
qa.push({kind:'selected_values',inspection:key.ndjson});
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:3000});
qa.push({kind:'formula_error_scan',inspection:errors.ndjson});
for(const name of names){
  const range=name==='Selected profile'?'A1:U26':name==='Events'?'A1:D13':name==='Conditions'?'A1:D14':name==='ReadMe'?'A1:B15':'A1:L15';
  const preview=await wb.render({sheetName:name,range,scale:1.5,format:'png'});
  const file='preview_'+name.replaceAll(' ','_')+'.png';await fs.writeFile(path.join(outputDir,file),new Uint8Array(await preview.arrayBuffer()));qa.push({kind:'render',sheet:name,file});
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(outputPath);
await fs.writeFile(path.join(outputDir,'workbook_qa.json'),JSON.stringify({bundle_id:payload.bundle_id,rows:{reference:payload.reference.length,conditional:payload.conditional.length,selected:payload.selected.length},checks:qa},null,2));
console.log(JSON.stringify({output:outputPath,sheets:names,reference_rows:payload.reference.length,conditional_rows:payload.conditional.length}));
