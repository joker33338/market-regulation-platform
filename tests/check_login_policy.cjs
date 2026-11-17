/* 内存路由与合成凭据验证；不访问服务或使用真实用户信息。 */
const path=require('node:path'),fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{createRequire}=require('node:module')
const root=path.resolve('frontend'),dependencies=createRequire(path.join(root,'package.json')),ts=dependencies('typescript')
const {createRouter,createMemoryHistory}=dependencies('vue-router')
const cache=new Map()
function load(file){
 file=path.resolve(file)
 if(cache.has(file))return cache.get(file).exports
 const module={exports:{}};cache.set(file,module)
 const output=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
 const requireFor=specifier=>specifier.startsWith('.')?load(path.resolve(path.dirname(file),specifier+'.ts')):dependencies(specifier)
 vm.runInThisContext('(function(require,module,exports){'+output+'\n})',{filename:file})(requireFor,module,module.exports)
 return module.exports
}
async function main(){
 const {safeLoginReturn,installLoginNavigation}=load(path.join(root,'src/router/authNavigation.ts'))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/login',name:'Login',component:{}},{path:'/dashboard',name:'Dashboard',component:{}},{path:'/documents',name:'Documents',component:{}}]})
 let token='',clearCount=0,listener
 const stop=installLoginNavigation(router,{hasToken:()=>!!token,clearSession:()=>{token='';clearCount++},subscribe:fn=>{listener=fn;return()=>{listener=undefined}}})
 await router.push('/documents?page=2#position')
 assert.equal(router.currentRoute.value.name,'Login');assert.equal(router.currentRoute.value.query.redirect,'/documents?page=2#position')
 token='synthetic-current';await router.push('/documents?page=2#position');assert.equal(router.currentRoute.value.name,'Documents')
 for(const status of [403,404,503])listener(status)
 assert.equal(clearCount,0);assert.equal(token,'synthetic-current')
 listener(401);await new Promise(resolve=>setTimeout(resolve,0))
 assert.equal(router.currentRoute.value.name,'Login');assert.equal(token,'');assert.equal(router.currentRoute.value.query.reason,'expired')
 assert.equal(safeLoginReturn(router,'/documents?page=2#position'),'/documents?page=2#position')
 for(const value of ['https://outside.invalid','//outside.invalid','/\\outside.invalid','/login?redirect=/login','/missing','/documents\n',null,['/documents'],'/'+('x'.repeat(4100))])assert.equal(safeLoginReturn(router,value),'/dashboard')
 stop()
 const client=load(path.join(root,'src/api/client.ts')),events=load(path.join(root,'src/api/authEvents.ts')),axios=dependencies('axios')
 const statuses=[];events.onAuthStateChange(status=>statuses.push(status))
 const reject=(config,status)=>new axios.AxiosError('synthetic',undefined,config,undefined,{status,statusText:'synthetic',data:{error:{code:'synthetic_denied'}},headers:{},config})
 client.setToken('synthetic-current')
 client.default.defaults.adapter=async config=>{throw reject(config,401)}
 await client.default.get('/api/documents').catch(()=>{});assert.deepEqual(statuses,[401]);statuses.length=0
 await client.default.post('/api/auth/login',{}).catch(()=>{});assert.deepEqual(statuses,[])
 let pending
 client.default.defaults.adapter=config=>new Promise((resolve,rejectPromise)=>{pending=()=>rejectPromise(reject(config,401))})
 const old=client.default.get('/api/documents').catch(()=>{})
 while(!pending)await new Promise(resolve=>setTimeout(resolve,0))
 client.setToken('synthetic-new-session');pending();await old
 assert.deepEqual(statuses,[]);assert.equal(client.getToken(),'synthetic-new-session')
 client.default.defaults.adapter=async config=>{throw reject(config,503)}
 await client.default.get('/api/documents').catch(()=>{});assert.deepEqual(statuses,[]);assert.equal(client.getToken(),'synthetic-new-session')
 console.log(JSON.stringify({status:'PASS',scope:'memory router, safe return and Axios auth invalidation'}))
}
main().catch(error=>{console.error(error.stack);process.exitCode=1})
