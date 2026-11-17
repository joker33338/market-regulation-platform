/* 使用既有 Playwright 与真实隔离 HTTP，不模拟业务成功。 */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE)
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

async function main() {
  const output = process.env.WORKBENCH_EVIDENCE || 'local/workbench-evidence'
  fs.mkdirSync(output, { recursive: true })
  const browser = await chromium.launch({ executablePath: process.env.BROWSER_EXECUTABLE, headless: true })
  const context = await browser.newContext({ viewport: { width:1440,height:1000 } })
  await context.addInitScript(() => sessionStorage.setItem('mrp_session_token','a'.repeat(32)))
  const page = await context.newPage()
  const errors = [], results = []
  page.on('pageerror', error => errors.push(error.message))
  const loaded = async () => {
    await page.waitForFunction(() => !document.querySelector('.el-loading-mask'))
    await page.waitForTimeout(150)
  }
  const query = () => page.getByRole('textbox',{name:'搜索文件',exact:true})
  const rows = () => page.locator('.el-table__body-wrapper tbody tr')
  try {
    await page.goto((process.env.WORKBENCH_URL || 'http://127.0.0.1:18186')+'/documents')
    await page.getByText('共 25 条',{exact:true}).waitFor()
    assert.equal(await rows().count(),20)
    results.push('真实HTTP列表及分页')

    await query().fill('synthetic-01')
    await query().press('Enter')
    await page.getByText('共 1 条',{exact:true}).waitFor()
    assert.equal(await rows().count(),1)
    await page.getByRole('button',{name:'保存常用筛选',exact:true}).click()
    await page.getByRole('button',{name:'清空筛选',exact:true}).click()
    await page.getByText('共 25 条',{exact:true}).waitFor()
    await page.getByRole('button',{name:'使用常用筛选',exact:true}).click()
    await page.getByText('共 1 条',{exact:true}).waitFor()
    assert.equal(await query().inputValue(),'synthetic-01')
    results.push('关键词查询/重置/常用筛选恢复')

    await page.getByRole('button',{name:'清空筛选',exact:true}).click()
    await page.getByText('共 25 条',{exact:true}).waitFor()
    await rows().first().locator('.el-checkbox').click()
    await page.locator('.el-pagination .btn-next').click()
    await page.waitForFunction(() => document.querySelectorAll('.el-table__body-wrapper tbody tr').length===5)
    await loaded()
    await rows().first().locator('.el-checkbox').click()
    await page.getByText('已选 2 份（跨页保留）',{exact:true}).waitFor()
    await page.locator('.el-pagination .btn-prev').click()
    await page.waitForFunction(() => document.querySelectorAll('.el-table__body-wrapper tbody tr').length===20)
    await loaded()
    assert.equal(await rows().first().locator('input[type=checkbox]').isChecked(),true)
    results.push('跨页选择保留')

    await page.getByRole('button',{name:'取消选择',exact:true}).click()
    await page.getByRole('button',{name:'选择全部筛选结果（25）',exact:true}).click()
    await page.getByText('已选 25 份（全部匹配的固定范围）',{exact:true}).waitFor()
    await page.getByRole('button',{name:'取消选择',exact:true}).click()
    results.push('全匹配真实服务端范围固定')

    await page.locator('.file-link').first().click()
    await page.getByRole('dialog').waitFor()
    const first = await page.locator('.preview-toolbar strong').innerText()
    await page.getByRole('button',{name:'下一份',exact:true}).click()
    assert.notEqual(await page.locator('.preview-toolbar strong').innerText(),first)
    await page.getByRole('button',{name:'上一份',exact:true}).click()
    assert.equal(await page.locator('.preview-toolbar strong').innerText(),first)
    await page.keyboard.press('Escape')
    await page.getByRole('dialog').waitFor({state:'hidden'})
    assert.equal(await rows().count(),20)
    results.push('原件连续预览及原列表保留')

    await query().fill('no-matching-synthetic')
    await query().press('Enter')
    await page.getByText('当前条件下没有文件，可调整或清空筛选。',{exact:true}).waitFor()
    assert.equal(await query().isVisible(),true)
    await page.getByRole('button',{name:'清空筛选',exact:true}).click()
    await page.getByText('共 25 条',{exact:true}).waitFor()
    results.push('空状态仍可修改查询')

    for(const width of [320,768,1024,1440]) {
      await page.setViewportSize({width,height:1000})
      await loaded()
      const overflow=await page.evaluate(() => document.documentElement.scrollWidth>window.innerWidth+1)
      assert.equal(overflow,false,'页面横向溢出 '+width)
      await page.screenshot({path:path.join(output,`workbench-${width}.png`),fullPage:true})
      results.push('响应式布局 '+width)
    }
    await page.setViewportSize({width:1440,height:1000})
    const payload=Buffer.from('%PDF-1.7 synthetic upload browser batch')
    await page.locator('input[type=file]').first().setInputFiles([
      {name:'browser-batch-law.pdf',mimeType:'application/pdf',buffer:payload},
      {name:'browser-batch-duplicate.pdf',mimeType:'application/pdf',buffer:payload},
      {name:'unsupported.txt',mimeType:'text/plain',buffer:Buffer.from('not-supported')}
    ])
    await page.locator('.upload-content .el-select').click()
    await page.getByRole('option',{name:'整批确认为法规',exact:true}).click()
    const prepared=page.waitForResponse(response=>response.request().method()==='POST' && /workbench\/documents\/[^/]+\/prepare$/.test(response.url()))
    await page.getByRole('button',{name:'上传并开始处理（2）',exact:true}).click()
    const response=await prepared
    assert.equal(response.status(),202)
    assert.equal((await response.json()).document_type,'law')
    await page.getByText('本批上传已结束，请查看已提交与需处理数量',{exact:true}).waitFor()
    await page.getByText('本批内容重复，已跳过',{exact:true}).waitFor()
    await page.getByText('格式不支持',{exact:true}).waitFor()
    results.push('批量上传真实提交、整批归类、重复与不支持项分别显示')
    assert.deepEqual(errors,[])
    fs.writeFileSync(path.join(output,'browser-result.json'),JSON.stringify({status:'PASS',results,pageErrors:errors,
      scope:'真实合成HTTP及临时SQLite；无正式数据库、无OCR引擎、无入库发布'},null,2))
    console.log(JSON.stringify({status:'PASS',checks:results.length,pageErrors:errors.length}))
  } finally { await browser.close() }
}
main().catch(error => { console.error(error.stack);process.exitCode=1 })
