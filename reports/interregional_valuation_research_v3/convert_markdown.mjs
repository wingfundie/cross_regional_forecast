// Markdown -> HTML with server-side KaTeX, Virtual Barrels semantic callouts, and inline exhibit directives.
// Usage: node convert_markdown.mjs <report.md>
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const localModules = path.join(here, 'tools', 'node_modules');
const v2Modules = path.resolve(here, '..', 'interregional_valuation_research_v2', 'tools', 'node_modules');
const modRoot = fs.existsSync(path.join(localModules, 'katex')) ? localModules : v2Modules;
const mod = p => pathToFileURL(path.join(modRoot, p)).href;
const {marked} = await import(mod('marked/lib/marked.esm.js'));
const katex = (await import(mod('katex/dist/katex.mjs'))).default;

let count = 0;
const render = (tex, displayMode) => {
  count += 1;
  return katex.renderToString(tex, {displayMode, output: 'htmlAndMathml', throwOnError: true, strict: 'error', trust: false});
};

const blockMath = {
  name: 'blockMath', level: 'block',
  start(src) { return src.match(/^\$\$/m)?.index; },
  tokenizer(src) {
    const m = /^\$\$\n?([\s\S]+?)\n?\$\$(?:\n|$)/.exec(src);
    if (m) return {type: 'blockMath', raw: m[0], text: m[1].trim()};
  },
  renderer(t) { return `<div class="math-display">${render(t.text, true)}</div>\n`; },
};

const inlineMath = {
  name: 'inlineMath', level: 'inline',
  start(src) { return src.indexOf('$'); },
  tokenizer(src) {
    const m = /^\$(?!\$)((?:\\\$|[^$\n])+?)\$(?![0-9A-Za-z])/.exec(src);
    if (m && !/^[\s0-9]|\s$/.test(m[1]) && /[\\^_{}=+\-<>|()a-zA-Z]/.test(m[1])) return {type: 'inlineMath', raw: m[0], text: m[1]};
  },
  renderer(t) { return render(t.text, false); },
};

const embedDirective = {
  name: 'embedDirective', level: 'block',
  start(src) { return src.match(/^\{\{(?:exhibit|diagram|interactive|part):/m)?.index; },
  tokenizer(src) {
    const m = /^\{\{(exhibit|diagram|interactive|part):([^}]+)\}\}(?:\n|$)/.exec(src);
    if (m) return {type: 'embedDirective', raw: m[0], kind: m[1], arg: m[2].trim()};
  },
  renderer(t) { return `<div class="embed-slot" data-kind="${t.kind}" data-arg="${t.arg.replace(/"/g, '&quot;')}"></div>\n`; },
};

const renderer = {
  blockquote(token) {
    const inner = this.parser.parse(token.tokens);
    const m = /^<p>\[!(MECHANISM|CONTEXT|TAKEAWAY|RISK)\]\s*([^\n<]*)(?:<br>|\n)?([\s\S]*)/i.exec(inner.trim());
    if (!m) return `<blockquote>${inner}</blockquote>\n`;
    const kind = m[1].toUpperCase();
    const cls = kind === 'CONTEXT' ? 'context' : kind === 'TAKEAWAY' ? 'takeaway' : kind === 'RISK' ? 'risk' : 'mechanism';
    const title = m[2] ? `${kind} · ${m[2].trim()}` : kind;
    const rest = m[3].trim();
    const body = rest.startsWith('<p>') || rest.startsWith('<ul>') || rest.startsWith('<ol>') ? rest : `<p>${rest}`;
    return `<div class="vb-callout ${cls}"><span class="vb-callout-title">${title}</span>${body}</div>\n`;
  },
};

marked.use({extensions: [blockMath, inlineMath, embedDirective], renderer, gfm: true});
const source = fs.readFileSync(process.argv[2], 'utf8');
const html = marked.parse(source);
process.stdout.write(html);
process.stderr.write(JSON.stringify({math: count, modRoot}) + '\n');
