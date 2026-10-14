import asyncio
import json
import httpx
import pytest
from backend.research import synthesize,validate_citations

def test_citation_validator_rejects_missing_and_unknown_ids():
    sources=[{'id':1}]
    with pytest.raises(ValueError):validate_citations('Uncited claim',sources)
    with pytest.raises(ValueError):validate_citations('Claim [99]',sources)
    assert validate_citations('Supplied observation [1]',sources)

def test_gemini_sends_key_in_header_and_only_supplied_evidence(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','gemini');monkeypatch.setenv('GEMINI_API_KEY','test-only-key')
    def handler(request):
        assert request.url.host=='generativelanguage.googleapis.com'
        assert request.headers['x-goog-api-key']=='test-only-key' and not request.url.query
        payload=json.loads(request.content)
        supplied=json.loads(payload['contents'][0]['parts'][0]['text'])
        assert supplied['instrument']=='BTC' and supplied['evidence'][0]['id']==1
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'Observed BTC quote [1].'}]}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await synthesize('What evidence?','BTC',[{'id':1,'summary':'Price 100'}],client)
    assert asyncio.run(run())==('Observed BTC quote [1].','gemini')

def test_off_mode_makes_no_model_request(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','off')
    assert asyncio.run(synthesize('Test','BTC',[{'id':1}]))==(None,None)
