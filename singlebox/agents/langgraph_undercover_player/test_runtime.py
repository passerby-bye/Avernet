import asyncio
import pytest
from uuid import uuid4
from runtime import Runtime


def request(text, session='g:12345678'):
    return {'type': 'req', 'id': 'task-' + str(uuid4()), 'method': 'chat.send', 'params': {
        'session_key': session, 'bcs_session_id': session,
        'message': {'content': [{'type': 'text', 'text': text}]}}}


@pytest.mark.asyncio
async def test_abort_suppresses_model_that_ignores_cancellation():
    frames = []
    entered, release = asyncio.Event(), asyncio.Event()
    class Graph:
        async def ainvoke(self, state):
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            return {'answer': '迟到结果'}
    async def send(frame):
        frames.append(frame)
    runtime = Runtime(Graph(), send)
    await runtime.handle(request('你的词是【苹果】'))
    run_id = frames[0]['payload']['run_id']
    await entered.wait()
    abort = {'type': 'req', 'id': 'abort', 'method': 'chat.abort',
             'params': {'run_id': run_id, 'session_key': 'g:12345678'}}
    await runtime.handle(abort)
    release.set()
    await runtime.runs[run_id]['task']
    await runtime.handle(abort)
    assert [f['payload']['state'] for f in frames if f['type'] == 'event'] == ['aborted']
    assert runtime.secrets == {}
    assert frames[-1]['payload']['aborted_run_ids'] == []


@pytest.mark.asyncio
async def test_secret_isolation_and_inheritance():
    frames, seen = [], []
    class Graph:
        async def ainvoke(self, state):
            seen.append(state['secret'])
            return {'answer': '准备好了'}
    async def send(frame):
        frames.append(frame)
    runtime = Runtime(Graph(), send)
    for text, session in [('你的词是【苹果】', 'a:12345678'),
                          ('遗言', 'a:12345678'), ('遗言', 'b:12345678')]:
        await runtime.handle(request(text, session))
        await runtime.runs[frames[-1]['payload']['run_id']]['task']
    assert seen == ['苹果', '苹果', '']


@pytest.mark.asyncio
async def test_upstream_idempotency_key_becomes_run_id_and_is_idempotent():
    frames = []
    class Graph:
        async def ainvoke(self, state):
            return {'answer': '好'}
    async def send(frame):
        frames.append(frame)
    runtime = Runtime(Graph(), send)
    req = request('你的词是【苹果】')
    req['params']['idempotency_key'] = 'smnode-sm-abc-speak_1-0'
    await runtime.handle(req)
    await runtime.handle(req)
    acks = [f for f in frames if f['type'] == 'res']
    assert [a['payload']['run_id'] for a in acks] == ['smnode-sm-abc-speak_1-0'] * 2
    assert len(runtime.runs) == 1
    await runtime.runs['smnode-sm-abc-speak_1-0']['task']
    finals = [f for f in frames if f['type'] == 'event']
    assert len(finals) == 1 and finals[0]['payload']['runId'] == 'smnode-sm-abc-speak_1-0'


@pytest.mark.asyncio
async def test_same_key_in_another_session_is_rejected():
    frames = []
    class Graph:
        async def ainvoke(self, state):
            return {'answer': '好'}
    async def send(frame):
        frames.append(frame)
    runtime = Runtime(Graph(), send)
    first = request('你的词是【苹果】', 'a:12345678')
    first['params']['idempotency_key'] = 'smnode-sm-abc-speak_1-0'
    other = request('你的词是【香蕉】', 'b:12345678')
    other['params']['idempotency_key'] = 'smnode-sm-abc-speak_1-0'
    await runtime.handle(first)
    await runtime.handle(other)
    assert frames[0]['ok'] and frames[1]['ok'] is False
    assert frames[1]['error']['code'] == 'INVALID_REQUEST'
    assert list(runtime.runs) == ['smnode-sm-abc-speak_1-0']
    assert runtime.runs['smnode-sm-abc-speak_1-0']['session'] == 'a:12345678'


@pytest.mark.asyncio
async def test_timeout_ms_bounds_the_run():
    frames = []
    class Graph:
        async def ainvoke(self, state):
            await asyncio.Event().wait()
    async def send(frame):
        frames.append(frame)
    runtime = Runtime(Graph(), send)
    req = request('你的词是【苹果】')
    req['params']['timeout_ms'] = 20
    await runtime.handle(req)
    run_id = frames[0]['payload']['run_id']
    await asyncio.wait_for(runtime.runs[run_id]['task'], 5)
    events = [f['payload'] for f in frames if f['type'] == 'event']
    assert [(e['state'], e['errorCode']) for e in events] == [('error', 'PLAYER_TIMEOUT')]
    assert runtime.secrets == {}
    assert runtime.runs[run_id]['terminal']


@pytest.mark.asyncio
async def test_timeout_is_enforced_even_if_the_graph_swallows_cancellation():
    frames = []
    class Graph:
        async def ainvoke(self, state):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass
            return {'answer': '迟到结果'}
    async def send(frame):
        frames.append(frame)
    runtime = Runtime(Graph(), send)
    req = request('你的词是【苹果】')
    req['params']['timeout_ms'] = 10
    await runtime.handle(req)
    run_id = frames[0]['payload']['run_id']
    await asyncio.wait_for(runtime.runs[run_id]['task'], 5)
    events = [f['payload'] for f in frames if f['type'] == 'event']
    assert [(e['state'], e.get('errorCode')) for e in events] == [('error', 'PLAYER_TIMEOUT')]
    assert runtime.secrets == {}
