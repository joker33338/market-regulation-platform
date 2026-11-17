/* 使用现有 TypeScript 和 Vue 编译器检查 SFC 脚本，不安装依赖。 */
const fs=require('node:fs'),path=require('node:path')
const root=path.resolve('frontend'),ts=require(path.join(root,'node_modules/typescript'))
const {parse}=require(path.join(root,'node_modules/@vue/compiler-sfc'))
const config=ts.readConfigFile(path.join(root,'tsconfig.json'),ts.sys.readFile)
const parsed=ts.parseJsonConfigFileContent(config.config,ts.sys,root)
const changed=['src/views/FileWorkbenchView.vue','src/views/WorkbenchIngestionView.vue','src/views/ReviewView.vue','src/views/SearchView.vue',
'src/components/workbench/PrepareDocumentsDialog.vue','src/components/workbench/BulkReviewDialog.vue','src/components/workbench/BatchUploadPanel.vue','src/components/workbench/ReviewBatchResults.vue']
const virtual=new Map()
for(const relative of changed){
 const file=path.join(root,relative),{descriptor,errors}=parse(fs.readFileSync(file,'utf8'))
 if(errors.length)throw new Error(relative+': '+errors)
 const code=(descriptor.script?.content || '')+'\n'+(descriptor.scriptSetup?.content || '')
 virtual.set(ts.normalizePath(file+'.sfc-check.ts'),"import { defineProps, defineEmits, defineExpose, withDefaults, defineOptions, defineSlots, defineModel } from 'vue';\n"+code)
}
const host=ts.createCompilerHost(parsed.options),read=host.readFile,exists=host.fileExists
host.fileExists=file=>virtual.has(ts.normalizePath(file))||exists(file)
host.readFile=file=>virtual.get(ts.normalizePath(file))??read(file)
const getSource=host.getSourceFile
host.getSourceFile=(file,languageVersion,onError,shouldCreateNewSourceFile)=>{
 const content=virtual.get(ts.normalizePath(file))
 return content===undefined?getSource(file,languageVersion,onError,shouldCreateNewSourceFile):ts.createSourceFile(file,content,languageVersion,true)
}
const program=ts.createProgram([...parsed.fileNames,...virtual.keys()],parsed.options,host)
const diagnostics=ts.getPreEmitDiagnostics(program)
console.log(ts.formatDiagnosticsWithColorAndContext(diagnostics,{getCurrentDirectory:()=>root,getCanonicalFileName:f=>f,getNewLine:()=>'\n'}))
console.log('Checked Vue script blocks:',virtual.size,'diagnostics:',diagnostics.length)
process.exitCode=diagnostics.length?1:0
