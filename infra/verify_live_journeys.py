"""Run 15 approved, reversible changes on the tagged local demo fixture.

Requires the updated API at localhost:8002 and execution credentials in .env.
Uses real MCP; never targets production resources or creates PRs.
"""
import json, sys, time
from pathlib import Path
import httpx
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1]
config=dotenv_values(root/'.env')
client=httpx.Client(base_url='http://127.0.0.1:8002/api', headers={'Authorization':'Bearer '+config['CLOUDPILOT_EXECUTION_TOKEN']},timeout=180)
def call(method,path,body=None):
    response=client.request(method,path,json=body)
    if response.status_code>=400:
        raise RuntimeError(f'{method} {path}: {response.status_code} '+str(response.json().get('message','Request failed')))
    return response.json()
rows=[]
try:
    call('POST','/execution/demo/setup?management=manual')
    resources=call('GET','/execution/resources')
    binding=next(r for r in resources if r['resource_id']=='demo-manual-01')
    original=binding['current']['instance_type']
    original_state=binding['current']['state']
    print('Registered tagged manual fixture; original shape:',original,flush=True)
    finding=next(r for r in call('GET','/recommendations?action=resize&limit=200')['items'] if r['resource_id']=='vm-115')
    prior=finding['decision']
    finding=call('PATCH','/recommendations/'+finding['id'],{'decision':'accepted','version':finding['version'],'expected_revision':finding['decision_revision']})
    options=call('GET','/execution/engine/candidates/'+finding['id'])['candidates']
    for index in range(15):
        live=next(r for r in call('GET','/execution/resources') if r['resource_id']=='demo-manual-01')['current']
        target='m5.xlarge' if live['instance_type']!='m5.xlarge' else 'm5.2xlarge'
        candidate=next(c for c in options if c['lab_eligible'] and c['lab_instance_type']==target)
        assert call('GET','/resources?limit=200')['total']==200
        call('GET','/resources/'+finding['resource_id']+'/metrics')
        proposal=call('POST','/execution/engine/proposals',{'recommendation_id':finding['id'],'target_plan_id':candidate['plan_id'],'binding_resource_id':'demo-manual-01','mode':'llm' if index == 0 else 'scripted'})
        pid=proposal['id']; payload={'digest':proposal['digest']}
        blocked=client.post('/execution/proposals/'+pid+'/execute',json=payload)
        assert blocked.status_code==409
        call('POST','/execution/proposals/'+pid+'/decision',{**payload,'decision':'approve'})
        result=call('POST','/execution/proposals/'+pid+'/execute',payload)
        assert result['status']=='APPLIED',result['status']
        assert result['result']['after']['instance_type']==target
        assert result['result']['after']['state']==live['state']
        assert call('POST','/execution/proposals/'+pid+'/execute',payload)['status']=='APPLIED'
        assert call('GET','/recommendations/'+finding['id'])['ready'] is False
        report=client.get('/optimization-plan/export?format=json'); assert report.status_code==200
        rows.append({'journey':index+1,'status':'passed','proposal_id':pid,'target':target,'unapproved_blocked':True,'verified':True,'repeat_execute':'APPLIED','transport':'real LocalStack MCP','planner':'llm' if index == 0 else 'scripted', 'dataset_version':finding['version']})
        (root/'docs/verification/live-journeys.json').write_text(json.dumps(rows,indent=2))
        print('Live journey',index+1,'passed',flush=True)
    if target!=original:
        inverse=call('POST','/execution/proposals/'+pid+'/rollback?mode=scripted',{})
        payload={'digest':inverse['digest']}
        call('POST','/execution/proposals/'+inverse['id']+'/decision',{**payload,'decision':'approve'})
        assert call('POST','/execution/proposals/'+inverse['id']+'/execute',payload)['status']=='APPLIED'
    latest=call('GET','/recommendations/'+finding['id'])
    call('PATCH','/recommendations/'+finding['id'],{'decision':prior,'version':latest['version'],'expected_revision':latest['decision_revision']})
    restored=next(r for r in call('GET','/execution/resources') if r['resource_id']=='demo-manual-01')['current']
    assert restored['instance_type']==original and restored['state']==original_state
    assert call('GET','/recommendations/'+finding['id'])['decision']==prior
    (root/'docs/verification/live-restoration.json').write_text(json.dumps({'instance_type':original,'state':original_state,'decision':prior,'verified':True},indent=2))
    print('Restored original fixture and source review decision.',flush=True)
except Exception as exc:
    print('Live verification stopped:',str(exc),flush=True)
    sys.exit(1)
