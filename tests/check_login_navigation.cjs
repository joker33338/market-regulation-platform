/* 真实浏览器检查登录入口；仅使用临时服务的合成身份。 */
const { chromium }=require(process.env.PLAYWRIGHT_MODULE)
const assert=require('node:assert/strict'),fs=require('node:fs')
async function main(){
 const base=process.env.LOGIN_TEST_URL || 'http://127.0.0.1:18186'
 const browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,headless:true})
 const context=await browser.newContext(),page=await context.newPage(),errors=[],checks=[]
 page.on('pageerror',error=>errors.push(error.message))
 try{
  await page.goto(base+'/documents?page=2#position');await page.waitForLoadState('networkidle')
  assert.equal(new URL(page.url()).pathname,'/login','未登录必须先显示账号登录页')
  assert.equal(new URL(page.url()).searchParams.get('redirect'),'/documents?page=2#position')
  await page.getByRole('textbox',{name:'用户名',exact:true}).waitFor()
  await page.getByRole('tab',{name:'账号登录',exact:true}).waitFor()
  checks.push('匿名深链接跳转账号登录并保存原页面')
  if(process.env.LOGIN_TEST_PASSWORD){
   await page.getByRole('textbox',{name:'用户名',exact:true}).fill('synthetic-login-admin')
   await page.locator('#login-password').fill(process.env.LOGIN_TEST_PASSWORD)
   await page.getByRole('button',{name:'登录',exact:true}).click()
   await page.waitForURL(url=>url.pathname==='/documents')
   assert.equal(new URL(page.url()).searchParams.get('page'),'2');assert.equal(new URL(page.url()).hash,'#position')
   checks.push('真实合成密码登录返回原筛选页和位置')
   await page.getByRole('button',{name:'账户菜单',exact:true}).click()
   await page.getByText('退出登录（撤销会话）',{exact:true}).click()
   await page.waitForURL(url=>url.pathname==='/login')
   assert.equal(await page.evaluate(()=>sessionStorage.getItem('mrp_session_token')),null)
   checks.push('退出撤销会话并返回账号登录')
   await page.goto(base+'/login?redirect='+encodeURIComponent('//outside.invalid/path'))
   await page.getByRole('textbox',{name:'用户名',exact:true}).fill('synthetic-login-admin')
   await page.locator('#login-password').fill(process.env.LOGIN_TEST_PASSWORD)
   await page.locator('#login-password').press('Enter')
   await page.waitForURL(url=>url.pathname==='/dashboard')
   assert.equal(new URL(page.url()).origin,base)
   checks.push('外部返回地址被拒绝，键盘登录返回站内默认页')
   const stored=await page.evaluate(()=>!!sessionStorage.getItem('mrp_session_token'))
   assert.equal(stored,true)
   await page.goto(base+'/login')
   await page.getByRole('textbox',{name:'用户名',exact:true}).fill('synthetic-login-admin')
   await page.locator('#login-password').fill('synthetic-wrong-password')
   const denied=page.waitForResponse(r=>r.url().endsWith('/api/auth/login') && r.status()===401)
   await page.getByRole('button',{name:'登录',exact:true}).click();await denied
   await page.getByText(/用户名或密码不正确/).waitFor()
   assert.equal(new URL(page.url()).pathname,'/login')
   assert.equal(await page.evaluate(()=>!!sessionStorage.getItem('mrp_session_token')),true)
   checks.push('密码错误保留表单且不误清已有会话')
  }
  await page.evaluate(()=>sessionStorage.setItem('mrp_session_token','invalid-synthetic-token-for-expiry-check'))
  await page.goto(base+'/documents')
  await page.waitForURL(url=>url.pathname==='/login')
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('mrp_session_token')),null)
  await page.getByText('登录已失效，请重新登录。',{exact:true}).waitFor()
  checks.push('服务端401清除失效凭证并返回登录')
  for(const width of [320,768,1440]){
   await page.setViewportSize({width,height:950})
   assert.equal(await page.getByRole('button',{name:'登录',exact:true}).isVisible(),true)
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false)
  }
  checks.push('登录页三种屏幕尺寸可操作')
  assert.deepEqual(errors,[])
  if(process.env.LOGIN_TEST_EVIDENCE){fs.mkdirSync(process.env.LOGIN_TEST_EVIDENCE,{recursive:true});fs.writeFileSync(process.env.LOGIN_TEST_EVIDENCE+'/browser.json',JSON.stringify({checks,pageErrors:errors,status:'PASS'},null,2))}
  console.log(JSON.stringify({status:'PASS',checks:checks.length,pageErrors:errors.length}))
 }finally{await browser.close()}
}
main().catch(error=>{console.error(error.message);process.exitCode=1})
