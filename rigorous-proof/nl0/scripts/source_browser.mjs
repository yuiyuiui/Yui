// Fixed browser operations: navigate, ordinary site verification, and readback.
// This driver never evaluates model-supplied JavaScript or uses personal profiles.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import dns from 'node:dns/promises';
import net from 'node:net';

let input='';
for await(const chunk of process.stdin){input+=chunk;if(input.length>16384)throw Error('Oversized browser request');}
const request=JSON.parse(input);
const {chromium}=await import(pathToFileURL(request.module).href);
const prefix=path.join(request.directory,request.stem);
const hosts=new Map();
function globalAddress(ip){
  if(net.isIP(ip)===4){
    const [a,b,c]=ip.split('.').map(Number);
    return !(a===0||a===10||a===127||a>=224||(a===100&&b>=64&&b<=127)||
      (a===169&&b===254)||(a===172&&b>=16&&b<=31)||(a===192&&(b===168||b===0||b===2))||
      (a===198&&(b===18||b===19||(b===51&&c===100)))||(a===203&&b===0&&c===113));
  }
  return net.isIP(ip)===6 && /^[23]/.test(ip) && !/^2001:(?:db8|0):/i.test(ip);
}
async function publicRequest(url){
  const u=new URL(url);
  if(u.protocol!=='https:'||u.username||u.password||(u.port&&u.port!=='443'))return false;
  const host=u.hostname.replace(/^\[|\]$/g,'');
  if(!hosts.has(host))hosts.set(host,dns.lookup(host,{all:true}).then(rows=>rows.length>0&&rows.every(r=>globalAddress(r.address))).catch(()=>false));
  return await hosts.get(host);
}
let browser;
for(const name of ['SIGTERM','SIGINT'])process.once(name,async()=>{
  try{if(browser)await browser.close();}finally{process.exit(name==='SIGTERM'?143:130);}
});
try{
  if(!await publicRequest(request.url))throw Error('Only public HTTPS browser requests are allowed');
  browser=await chromium.launch({executablePath:request.executable,headless:true,
    args:['--no-first-run','--no-default-browser-check']});
  const context=await browser.newContext({acceptDownloads:true,serviceWorkers:'block'});
  await context.route('**/*',async route=>{
    if(await publicRequest(route.request().url()))await route.continue();else await route.abort();
  });
  const page=await context.newPage();
  let download=null,normalVerification=false,response=null,navigationError=null;
  page.on('response',value=>{
    if(value.request().isNavigationRequest()&&value.frame()===page.mainFrame())response=value;
  });
  page.on('download',value=>{download=value;});
  try{response=await page.goto(request.url,{waitUntil:'domcontentloaded',timeout:30000});}
  catch(error){navigationError=String(error);}
  await page.waitForTimeout(1500);
  // Sci-Hub's own ALTCHA button runs the site's normal proof-of-work widget.
  // Other challenges remain explicit; no tokens, stealth or solver service.
  if(new URL(page.url()).hostname==='sci-hub.box' &&
      await page.locator('altcha-widget').count() && await page.locator('.answer').count()){
    normalVerification=true;
    await page.locator('.answer').click({timeout:5000});
    await page.waitForFunction(()=>!document.querySelector('altcha-widget'),{},{timeout:45000}).catch(()=>{});
    await page.waitForTimeout(1000);
  }
  const runtime={node_version:process.version,browser_version:browser.version()};
  if(download){
    await download.saveAs(prefix+'.browser-document');
    const bytes=await fs.readFile(prefix+'.browser-document');
    if(bytes.length>request.limit||!bytes.subarray(0,5).equals(Buffer.from('%PDF-')))throw Error('Browser download is oversized or not a PDF');
    console.log(JSON.stringify({final_url:download.url(),status:'READABLE',document_kind:'PDF',links:[],runtime,normal_verification:normalVerification}));
  }else{
    if(navigationError)throw Error(navigationError);
    const value=await page.evaluate(()=>({final_url:location.href,title:document.title,text:document.body?.innerText||'',
      links:[...document.querySelectorAll('a[href],object[data],iframe[src],embed[src],meta[name="citation_pdf_url"]')].map(e=>e.href||e.data||e.src||(e.content?new URL(e.content,location.href).href:'')),
      challenge:!!document.querySelector('altcha-widget,iframe[src*="recaptcha/enterprise/anchor"],iframe[src*="recaptcha/api2/anchor"]')}));
    const html=await page.content();
    if(Buffer.byteLength(html)>request.limit)throw Error('Browser document exceeds retrieval limit');
    await fs.writeFile(prefix+'.browser-document',html);
    await page.screenshot({path:prefix+'.png',timeout:5000});
    const blocked=value.challenge||new URL(value.final_url).pathname.startsWith('/sorry/')||
      /unusual traffic|verify you are human|access denied|异常流量|你是机器人吗/.test(value.text.toLowerCase());
    const httpStatus=response?.status();
    console.log(JSON.stringify({...value,http_status:httpStatus,document_kind:'HTML',runtime,normal_verification:normalVerification,
      status:blocked?'HUMAN_ACCESS_REQUIRED':httpStatus>=400?'HTTP_ERROR':value.text.trim()||value.links.length?'READABLE':'NO_EXTRACTABLE_TEXT'}));
  }
}catch(error){console.error(String(error));process.exitCode=1;}
finally{if(browser)await browser.close();}
