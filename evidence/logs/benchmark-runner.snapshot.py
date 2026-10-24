import json,os,sys,time,subprocess,signal,urllib.request,pathlib,statistics,importlib.util
ROOT=pathlib.Path('<recipes-checkout>'); NAME=sys.argv[1] if len(sys.argv)>1 else 'qwen3.6'; OUT=ROOT/'evidence/logs'/NAME;OUT.mkdir(parents=True,exist_ok=True)
p=json.loads((ROOT/'profiles'/(NAME+'.json')).read_text());base='http://127.0.0.1:1929';proc=None

def api(path,body=None):
 r=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=300) as s:return json.load(s)
active=subprocess.run(['systemctl','--user','is-active','--quiet','nemotron-e4b.service']).returncode==0
if active:
 for attempt in range(120):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8000/slots',timeout=2) as response: slots=json.load(response)
   if any(x.get('is_processing') for x in slots):raise RuntimeError('Nemotron is busy; retry later')
   break
  except (OSError,ValueError):time.sleep(.5)
 else:raise RuntimeError('Nemotron not ready')
 subprocess.run(['systemctl','--user','stop','nemotron-e4b.service'],check=True)

try:
 env=dict(os.environ);env.pop('PYTHONPATH',None)
 gpu=[l.split(',')[0] for l in subprocess.check_output(['nvidia-smi','--query-gpu=uuid,name','--format=csv,noheader'],text=True).splitlines() if 'RTX 3060' in l][0];env['CUDA_VISIBLE_DEVICES']=gpu
 model=pathlib.Path.home()/'.freetoken/models'/p['model']['local_directory']
 cmd=[sys.executable,'-m','freetoken.cli','serve','--model-path',str(model),'--gpu','0','--host','127.0.0.1','--port','1929','--served-model-name',NAME,*p['server_arguments']]
 with (OUT/'server.log').open('w') as log:
  proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  for _ in range(1200):
   if proc.poll() is not None:raise RuntimeError(NAME+' failed loading')
   try:
    if api('/v1/cache/status').get('state')=='serving':break
   except Exception:pass
   time.sleep(.5)
  else:raise RuntimeError('Startup timeout')
  rebuild=api('/v1/cache/rebuild',p['cache_rebuild']) if p.get('cache_rebuild') else None;print('rebuild',rebuild,flush=True)
  from transformers import AutoTokenizer
  tok=AutoTokenizer.from_pretrained(model,local_files_only=True)
  records=[]
  for i in range(4):
   target=256 if i==0 else 4096
   prefix=f'Benchmark case {chr(65+i)} {time.time_ns()}. '
   ids=tok.encode(prefix+'Read these synthetic records. '+('The subsystem handles jobs and returns results. '*1500),add_special_tokens=False)[:target]
   content=tok.decode(ids)
   # The actual API usage includes the model chat template.
   body={'model':NAME,'messages':[{'role':'user','content':content}], 'max_tokens':32 if i==0 else 200,'temperature':0,'ignore_eos':True,'stream':True,'stream_options':{'include_usage':True}}
   started=time.perf_counter();first=None;last=None;usage={};events=[]
   req=urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=300) as response:
    for line in response:
     if not line.startswith(b'data: '):continue
     data=line[6:].strip()
     if data==b'[DONE]':break
     event=json.loads(data);events.append(event)
     if event.get('usage'):usage=event['usage']
     if any(c.get('delta',{}).get('content') or c.get('delta',{}).get('reasoning_content') for c in event.get('choices',[])):
      now=time.perf_counter();first=now if first is None else first;last=now
   elapsed=time.perf_counter()-started
   record={'run':i,'warmup':i==0,'requested_raw_content_tokens':target,'max_tokens':body['max_tokens'],'ignore_eos':True,'usage':usage,'elapsed_s':elapsed,'ttft_s':first-started,'prefill_effective_tok_s':usage['prompt_tokens']/(first-started),'decode_http_tok_s':(usage['completion_tokens']-1)/(last-first),'events':events}
   records.append(record);(OUT/'requests.json').write_text(json.dumps({'date':'2026-10-24','engine':'FreeToken 0.2.0+gfe5a5ec9c','cache_rebuild':p['cache_rebuild'],'method':'HTTP stream; first nonempty content or reasoning event; warmup excluded. Synthetic content truncated to 4096 tokens before chat template. Three distinct prefixes.','runs':records},indent=2)+'\n');print({k:v for k,v in record.items() if k!='events'},flush=True)
finally:
 if proc:
  try:os.killpg(proc.pid,signal.SIGINT)
  except ProcessLookupError:pass
  try:proc.wait(timeout=25)
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGKILL);proc.wait()
 if active:subprocess.run(['systemctl','--user','start','nemotron-e4b.service'],check=True)
 print('Nemotron service restored',flush=True)
