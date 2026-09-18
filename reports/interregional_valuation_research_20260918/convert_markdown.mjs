import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const {marked} = await import(pathToFileURL(process.argv[2]).href);
process.stdout.write(marked.parse(fs.readFileSync(process.argv[3], 'utf8'), {gfm:true}));
