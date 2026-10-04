// Markdown -> HTML with server-side KaTeX. Math is tokenised before emphasis parsing,
// so `_` and `*` inside $...$ or $$...$$ are never treated as Markdown. Invalid TeX fails the build.
// Usage: node convert_markdown.mjs <report.md>   (dependencies pinned in ./tools/package.json)
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const mod = p => pathToFileURL(path.join(here, 'tools', 'node_modules', p)).href;
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
    // $...$ with no leading/trailing space inside; a literal dollar amount such as "$300" is left alone
    // because it has no closing delimiter on the same line that satisfies the pattern.
    const m = /^\$(?!\$)((?:\\\$|[^$\n])+?)\$(?![0-9A-Za-z])/.exec(src);
    if (m && !/^[\s0-9]|\s$/.test(m[1]) && /[\\^_{}=+\-<>|()a-zA-Z]/.test(m[1])) return {type: 'inlineMath', raw: m[0], text: m[1]};
  },
  renderer(t) { return render(t.text, false); },
};

marked.use({extensions: [blockMath, inlineMath], gfm: true});
const source = fs.readFileSync(process.argv[2], 'utf8');
const html = marked.parse(source);
process.stdout.write(html);
process.stderr.write(JSON.stringify({math: count}) + '\n');
