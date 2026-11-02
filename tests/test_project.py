import csv
from pathlib import Path
from app.app import app
from controller.forecasting import persistence, ewma, evaluate
from controller.scoring import pressure, preferences, shares, bounded_weights
from controller.controller import cycle
from controller import controller
from benchmark.analyze_results import percentile, summarize, analyze
from benchmark.load_generator import schedule

def test_backend():
    client=app.test_client()
    for url in ('/','/health','/work/cpu?iterations=10','/work/io?ms=0','/metrics'):
        assert client.get(url).status_code==200
    assert client.get('/work/cpu?iterations=-1').status_code==400
    assert client.get('/health').json['replica']=='local'
    assert b'app_requests_total' in client.get('/metrics').data

def test_forecast_no_leakage():
    assert persistence([1,2,3])==3
    assert ewma([1,3],.5)==2
    assert evaluate([1,2,3,100])['persistence']['mae']==97
    assert evaluate([1,2,3,4,100],horizon=2)['persistence']['mae']==97

def test_pressure_missing_and_bounds():
    assert pressure({}) is None
    assert pressure({'cpu':99})==1
    assert pressure({'cpu':-1})==0

def test_weights_health_and_fallback():
    samples={'app1':{'healthy':True,'cpu':.2,'memory':100,'inflight':1,'latency':.1},'app2':{'healthy':False}}
    pref=preferences(samples,{'app1':1,'app2':1})
    assert pref['app1']>0 and pref['app2']==0
    assert shares(pref,{'app1':1,'app2':1})['app2']==0
    weights, actual=bounded_weights({'app1':.8,'app2':.2},{'app1':.5,'app2':.5})
    assert actual['app1']<=.55 and all(0<=w<=256 for w in weights.values())
    missing={name:{'healthy':True} for name in ('app1','app2','app3')}
    assert cycle(missing,[],{k:1/3 for k in missing})[2]=='static_fallback'

def test_analysis_csv(tmp_path):
    rows=[{'status':'200','latency_seconds':'.1','failure':'','replica':'app1'} for _ in range(20)]
    result=summarize(rows,2)
    assert result['p99_seconds']==.1 and result['throughput_rps']==10
    path=tmp_path/'run.csv'
    with path.open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    analyze([path],2,tmp_path/'charts')
    assert (tmp_path/'charts'/'summary.csv').exists()
    assert (tmp_path/'charts'/'latency.png').exists()
    assert percentile([1,2],.99) is None

def test_schedule_deterministic():
    assert list(schedule(2,10,'burst',42))==list(schedule(2,10,'burst',42))

def test_stale_metrics(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'status':'success','data':{'result':[{'metric':{'instance':'app1:8000'},'value':[10,'1']}]}}
    monkeypatch.setattr(controller.requests,'get',lambda *a,**k: Response())
    assert controller.query('up',now=30,max_age=15)=={}
