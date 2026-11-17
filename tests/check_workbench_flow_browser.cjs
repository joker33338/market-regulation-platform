/* 只操作隔离服务中的合成资料；所有业务响应来自真实API及PG/MySQL。 */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE)
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict')
async function main(){
 const fixture=JSON.parse(fs.readFileSync(process.env.WORKBENCH_FLOW_FIXTURE,'utf8'))
 const output=process.env.WORKBENCH_EVIDENCE,url=process.env.WORKBENCH_URL
 const browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,headless:true})
 const context=await browser.newContext({viewport:{width:1440,height:1000}})
 await context.addInitScript(()=>sessionStorage.setItem('mrp_session_token','a'.repeat(32)))
 const page=await context.newPage(),errors=[],checks=[]
 page.on('pageerror',error=>errors.push(error.message))
 try{
  for(const item of fixture.items){
   await page.goto(url+'/documents?keyword='+encodeURIComponent(item.file_name))
   await page.getByText('共 1 条',{exact:true}).waitFor()
   await page.locator('.file-link').first().click()
   await page.getByRole('button',{name:'确认归类并准备入库',exact:true}).click()
   const dialog=page.getByRole('dialog',{name:'确认资料信息与入库范围',exact:true})
   await dialog.getByRole('textbox',{name:'资料名称',exact:true}).fill(item.title)
   await dialog.locator('.el-select').click()
   await page.getByRole('option',{name:item.kind==='law'?'法规':'处罚案例',exact:true}).click()
   await dialog.getByRole('button',{name:'确认并交给后台处理',exact:true}).click()
   await dialog.waitFor({state:'hidden'})
  }
  checks.push('逐文件确认法规和案例归类，真实保存入库准备')
  const law=fixture.items[0]
  await page.goto(url+'/review?parse='+encodeURIComponent(law.parse_id))
  await page.getByRole('button',{name:'保存人工修订',exact:true}).waitFor()
  await page.getByRole('button',{name:'保存人工修订',exact:true}).click()
  const revision=page.getByRole('dialog',{name:'确认保存人工修订',exact:true})
  await revision.locator('textarea').fill('第一条 浏览器整页修订。第二条 合成条文。')
  await revision.getByRole('button',{name:'确认提交',exact:true}).click()
  await revision.waitFor({state:'hidden'})
  await page.getByText('第一条 浏览器整页修订。第二条 合成条文。',{exact:true}).first().waitFor()
  checks.push('浏览器整页修订保存及审核副本显示')
  await page.goto(url+'/documents?keyword='+encodeURIComponent(fixture.keyword))
  await page.getByText('共 3 条',{exact:true}).waitFor()
  await page.getByRole('button',{name:'选择全部筛选结果（3）',exact:true}).click()
  await page.getByRole('button',{name:'批量审核',exact:true}).click()
  const review=page.getByRole('dialog',{name:'确认批量审核范围',exact:true})
  const submit=review.getByRole('button',{name:'确认提交批量审核',exact:true})
  assert.equal(await submit.isDisabled(),true)
  await review.locator('.el-checkbox').click()
  await submit.click();await review.waitFor({state:'hidden'})
  await page.getByText(/本批审核：成功 3 份，失败 0 份，待处理 0 份/).waitFor({timeout:30000})
  checks.push('显式勾选确认后批量审核，真实台账三份成功')
  await page.goto(url+'/knowledge/ingestion')
  await page.getByText('待发布',{exact:true}).first().waitFor({timeout:30000})
  await page.getByRole('button',{name:'准备全部待发布资料',exact:true}).click()
  const manifest=page.getByRole('dialog',{name:'确认本次发布清单',exact:true})
  await manifest.getByText('本次 3 份资料：法规 2 份，处罚案例 1 份。',{exact:true}).waitFor()
  assert.equal(await manifest.locator('.el-table__body-wrapper tbody tr').count(),3)
  checks.push('真实候选构建和明确的三份发布清单')
  await manifest.getByRole('button',{name:'确认发布这份清单',exact:true}).click()
  await manifest.waitFor({state:'hidden',timeout:30000})
  await page.getByText('已执行发布',{exact:true}).first().waitFor()
  checks.push('浏览器显式发布成功及发布状态刷新')
  await page.goto(url+'/library/laws')
  await page.getByText(fixture.items[0].title,{exact:true}).first().waitFor()
  await page.getByText(fixture.items[1].title,{exact:true}).first().waitFor()
  await page.goto(url+'/library/cases')
  await page.getByText(fixture.items[2].title,{exact:true}).first().waitFor()
  checks.push('已发布两部法规和一份案例分别在目标库可见')
  for(const route of ['/knowledge/ingestion','/review?parse='+law.parse_id]){
   await page.goto(url+route);await page.waitForLoadState('networkidle')
   for(const width of [320,768,1024,1440]){
    await page.setViewportSize({width,height:1000})
    await page.waitForTimeout(150)
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'流程页横向溢出 '+route+' '+width)
   }
  }
  checks.push('审核和发布页面四种屏幕宽度无页面横向溢出')
  assert.deepEqual(errors,[])
  fs.writeFileSync(path.join(output,'flow-result.json'),JSON.stringify({status:'PASS',checks,pageErrors:errors,scope:'合成PDF、真实隔离PG/MySQL、固定测试向量；无OCR和真实模型推理'},null,2))
  console.log(JSON.stringify({status:'PASS',checks:checks.length,pageErrors:errors.length}))
 }catch(error){await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});throw error}
 finally{await browser.close()}
}
main().catch(error=>{console.error(error.stack);process.exitCode=1})
