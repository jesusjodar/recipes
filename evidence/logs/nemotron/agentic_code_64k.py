#!/usr/bin/env python3
import json, sys, time, urllib.request
from pathlib import Path
url=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8011/v1/chat/completions'
out=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).with_name('agentic-code-64k.json')
tasks=[
 ('python-idempotency-cache', '''Issue: retrying POST /jobs occasionally creates duplicate jobs. Produce a minimal unified diff and a focused test plan, as if you were the coding agent after inspecting this service. Preserve existing API behavior unless a change is required.

Relevant code:
```python
# api/jobs.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import Job

router = APIRouter()
class JobIn(BaseModel):
    kind: str
    payload: dict

@router.post("/jobs")
def create_job(body: JobIn, db: Session = Depends(get_db)):
    job = Job(kind=body.kind, payload=body.payload, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"id": str(job.id), "status": job.status}
```
```python
# models.py
class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```
Constraint: clients can send an Idempotency-Key header. It must be scoped per tenant, unique under concurrent requests, and must reject reuse with a different request body. Explain any migration required.'''),
 ('typescript-csv-export', '''Act as an agent implementing this issue. Return a minimal code patch, tests, and a short verification checklist. The endpoint must not leak rows across tenants, must handle commas/quotes/newlines in cells, and must not build the entire export in memory.

```ts
// routes/export.ts
export async function exportOrders(req: Request, res: Response) {
  const orders = await db.order.findMany({ where: { status: req.query.status } });
  const csv = ["id,email,total", ...orders.map(o => `${o.id},${o.email},${o.total}`)].join("\\n");
  res.setHeader("Content-Type", "text/csv");
  res.send(csv);
}
```
```ts
// middleware/auth.ts sets req.user = { tenantId: string, id: string }
// The DB supports an async iterator: db.order.iterate({ where, batchSize }).
```
Call out assumptions before applying a patch and address error handling/headers.'''),
 ('agentic-debug-and-fix', '''A coding agent has inspected this background task flow. Diagnose the likely race, propose the smallest safe implementation patch, and include regression tests that would fail before the patch. Structure your answer as: findings, patch, tests, rollout/verification. Do not claim to have run tests.

```python
# worker.py
async def process(message):
    task = await db.tasks.get(message.task_id)
    if task.status == "done":
        return
    await db.tasks.update(task.id, status="running")
    result = await call_provider(task.input)
    await db.results.insert(task.id, result)
    await db.tasks.update(task.id, status="done")
```
```sql
CREATE TABLE tasks (
  id uuid PRIMARY KEY,
  status text NOT NULL,
  input jsonb NOT NULL,
  attempts integer NOT NULL DEFAULT 0
);
CREATE TABLE results (
  task_id uuid NOT NULL REFERENCES tasks(id),
  body jsonb NOT NULL
);
```
The queue is at-least-once; messages for one task can be delivered concurrently on different workers. Provider calls may time out after succeeding. There is no unique constraint on results.task_id. Include database-level safeguards and explain handling of ambiguous provider timeouts.'''),
]

def ask(name, prompt, max_tokens):
 body={'model':'nemotron-e4b','messages':[{'role':'system','content':'You are a careful autonomous software engineering agent. Give implementation-ready code and tests. Be concise but complete; do not invent repository observations or test results.'},{'role':'user','content':prompt}], 'temperature':1.0,'top_p':0.95,'max_tokens':max_tokens,'chat_template_kwargs':{'enable_thinking':True}}
 req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 t=time.perf_counter()
 with urllib.request.urlopen(req,timeout=900) as r: data=json.load(r)
 elapsed=time.perf_counter()-t
 usage=data.get('usage',{}); choices=data.get('choices',[])
 message=choices[0].get('message',{}) if choices else {}
 return {'task':name,'elapsed_s':elapsed,'completion_tokens':usage.get('completion_tokens'),'prompt_tokens':usage.get('prompt_tokens'),'api_tok_s':(usage.get('completion_tokens') or 0)/elapsed,'content':message.get('content',''),'reasoning_content':message.get('reasoning_content',''),'finish_reason':choices[0].get('finish_reason') if choices else None,'timings':data.get('timings')}

# Exclude a short warm-up request from reported measurements.
ask('warmup','Reply with a short acknowledgement.',64)
runs=[]
for name,prompt in tasks:
 r=ask(name,prompt,2400); runs.append(r)
 print(f"{name}: in={r['prompt_tokens']} out={r['completion_tokens']} API={r['api_tok_s']:.2f} tok/s ({r['elapsed_s']:.2f}s)",flush=True)
mean=sum(r['api_tok_s'] for r in runs)/len(runs)
result={'engine':'llama.cpp b11828 CUDA 13.4','gpu':'RTX 3060 12 GB','context_capacity':65536,'drafter':'NVIDIA official DFlash BF16 GGUF','n_max':7,'concurrency':1,'runs':runs,'mean_api_tok_s':mean,'mean_completion_tokens':sum((r['completion_tokens'] or 0) for r in runs)/len(runs)}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(f"Mean API generation rate: {mean:.2f} tok/s; average output: {result['mean_completion_tokens']:.0f} tokens; report: {out}")
