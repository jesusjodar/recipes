#!/usr/bin/env python3
import json, sys, time, urllib.request
from pathlib import Path
url=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8011/v1/chat/completions'
out=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).with_name('run.json')
tasks=[
 ('bug-triage','A Python API intermittently returns duplicate records after retries. Give a concise but operational investigation plan: hypotheses, exact evidence to collect, and the first safe fix to test. Use an agentic coding workflow and be precise.'),
 ('tool-workflow','A user asks to add CSV export to a web app. Provide a detailed sequence of repository inspection, implementation, test, and review actions. Include edge cases and how to verify the downloaded file.'),
 ('incident-response','A deploy caused a 500 error on one endpoint while other routes work. Write the step-by-step local agent response, with rollback criteria, diagnostic commands to consider, and evidence needed before a code change.'),
 ('code-review','Review this proposed behavior: cache API responses for 10 minutes using only the URL as the cache key. Explain concrete correctness/security risks and a safer implementation/verification plan.'),
]

def ask(prompt, max_tokens):
 body={'model':'nemotron-e4b','messages':[{'role':'system','content':'You are a careful software engineering agent. Reason about the task, then give an actionable, structured answer.'},{'role':'user','content':prompt}], 'temperature':1.0,'top_p':0.95,'max_tokens':max_tokens,'chat_template_kwargs':{'enable_thinking':True}}
 req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 t=time.perf_counter()
 with urllib.request.urlopen(req,timeout=600) as r: data=json.load(r)
 elapsed=time.perf_counter()-t
 usage=data.get('usage',{})
 choices=data.get('choices',[])
 text=choices[0].get('message',{}).get('content','') if choices else ''
 return {'elapsed_s':elapsed,'completion_tokens':usage.get('completion_tokens'),'prompt_tokens':usage.get('prompt_tokens'),'tok_s':(usage.get('completion_tokens') or 0)/elapsed,'text':text,'timings':data.get('timings')}

results=[]
# Warm-up excluded from results; short cap limits time while warming kernels/cache.
ask('Reply with a one-sentence acknowledgement.',32)
for name,prompt in tasks:
 r=ask(prompt,256); r['task']=name; results.append(r)
 print(f"{name}: {r['completion_tokens']} tokens, {r['tok_s']:.2f} tok/s, {r['elapsed_s']:.2f}s",flush=True)
result={'url':url,'runs':results,'mean_tok_s':sum(r['tok_s'] for r in results)/len(results),'mean_elapsed_s':sum(r['elapsed_s'] for r in results)/len(results)}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(f"Mean: {result['mean_tok_s']:.2f} tok/s; report: {out}")
