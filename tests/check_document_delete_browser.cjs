/** 仅合成凭证和短期候选入口，不读取正式runtime。 */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('node:fs');
const assert=require('node:assert/strict');
const base=process.env.DELETE_BROWSER_BASE;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(base)||base.endsWith(':8180'))throw Error('需要独立短期测试入口');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.DELETE_BROWSER_EXE,headless:true});
 const evidence=[];
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage();
  let token='a'.repeat(32);
  await context.addInitScript(()=>{if(!sessionStorage.getItem('mrp_session_token'))sessionStorage.setItem('mrp_session_token','a'.repeat(32));});
  const requests=[];
  page.on('response',r=>{const u=new URL(r.url());if(u.pathname.startsWith('/api/'))requests.push({method:r.request().method(),path:u.pathname,status:r.status()});});
  async function open(letter='a') {
   token=letter.repeat(32);
   await page.goto(base+'/documents');
   await page.evaluate(t=>sessionStorage.setItem('mrp_session_token',t),token);
   await page.reload();
   await page.getByRole('heading',{name:'文档管理',exact:true}).waitFor();
   await page.getByRole('row').filter({hasText:'synthetic-success.pdf'}).waitFor();
  }
  function row(name){return page.getByRole('row').filter({hasText:'synthetic-'+name+'.pdf'});}
  async function remove(name,status) {
   const count=requests.length;
   const response=page.waitForResponse(r=>r.request().method()==='DELETE');
   const refreshed=page.waitForResponse(r=>r.request().method()==='GET'&&new URL(r.url()).pathname==='/api/documents');
   await row(name).getByRole('button',{name:'删除',exact:true}).click();
   await page.getByRole('button',{name:'提交删除请求',exact:true}).click();
   assert.equal((await response).status(),status);
   await refreshed;
   if(status===200)await row(name).waitFor({state:'detached'});
   else if(status!==404)assert.equal(await row(name).count(),1);
   const trace=requests.slice(count);
   assert(trace.some(r=>r.method==='GET'&&r.path==='/api/documents'));
   if(status!==200)assert.equal(await page.getByText(/后端已接受 \d+ 个删除请求/).count(),0);
   else await page.getByText('后端已接受 1 个删除请求，正在刷新列表确认',{exact:true}).waitFor();
   evidence.push({case:name,status,refreshed:true,row_present:await row(name).count()===1});
   await page.screenshot({path:process.env.DELETE_BROWSER_EVIDENCE+'/'+name+'.png'});
  }
  await open('a');
  assert.equal(await row('success').getByRole('button',{name:'删除',exact:true}).isEnabled(),true);
  evidence.push({case:'runtime_method_gate',delete_declared:true,button_enabled:true});
  const schemaRoute=async route=>{
   const response=await route.fetch();const schema=await response.json();
   delete schema.paths['/api/documents/{file_id}'].delete;
   await route.fulfill({response,json:schema});
  };
  // 仅方法门控负向场景使用受控契约；删除流程均为真实服务响应。
  await page.route('**/api/openapi.json',schemaRoute);
  await page.reload();await row('success').waitFor();
  assert.equal(await row('success').getByRole('button',{name:'删除',exact:true}).isDisabled(),true);
  evidence.push({case:'method_absent_controlled_schema',button_disabled:true});
  await page.unroute('**/api/openapi.json',schemaRoute);
  await page.reload();await row('success').waitFor();
  await remove('conflict',409);
  await remove('unavailable',503);
  await open('b');
  await remove('forbidden',403);
  await open('a');
  const rows=await (await context.request.get(base+'/api/documents',{headers:{Authorization:'Bearer '+'a'.repeat(32)}})).json();
  const repeated=rows.list.find(r=>r.file_name==='synthetic-repeated.pdf');
  const response=await context.request.delete(base+'/api/documents/'+repeated.file_id,{headers:{Authorization:'Bearer '+'a'.repeat(32)}});
  assert.equal(response.status(),200);
  await remove('repeated',404);
  await remove('success',200);
  const final=await (await context.request.get(base+'/api/documents',{headers:{Authorization:'Bearer '+'a'.repeat(32)}})).json();
  assert(!final.list.some(r=>r.file_name==='synthetic-success.pdf'));
  assert(final.list.some(r=>r.file_name==='synthetic-forbidden.pdf'));
  fs.writeFileSync(process.env.DELETE_BROWSER_EVIDENCE+'/browser.json',JSON.stringify({evidence,requests},null,2));
  console.log(JSON.stringify({browser_checks:evidence,success:true}));
 } finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
