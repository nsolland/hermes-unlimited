import {build} from 'esbuild';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
await mkdir(new URL('./dist/',import.meta.url),{recursive:true});
const built = await build({entryPoints:[new URL('./view.mjs',import.meta.url).pathname],bundle:true,platform:'browser',format:'iife',write:false,minify:true,target:['es2022']});
const inline = built.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const html=(await readFile(new URL('./view.html',import.meta.url),'utf8')).replace('<script type="module" src="./view.mjs"></script>',() => `<script>${inline}</script>`);
await writeFile(new URL('./dist/view.html',import.meta.url),html);
console.log('Built self-contained MCP Apps UI');
