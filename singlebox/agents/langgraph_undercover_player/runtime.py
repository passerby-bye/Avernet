"""BCN V3 request lifecycle. Secrets never leave their session scope."""
import asyncio
import json
import re
import time
from uuid import uuid4

from player import task_secret


def log(**fields):
    """One JSON line per lifecycle step; never includes the private word."""
    print(json.dumps({'ts': int(time.time() * 1000), **fields}, ensure_ascii=False), flush=True)


class Runtime:
    def __init__(self, graph, send):
        self.graph, self.send = graph, send
        self.secrets = {}
        self.runs = {}

    async def reply(self, request, payload=None, error=None):
        frame = {'type': 'res', 'id': request['id'], 'ok': error is None}
        frame.update({'error': {'code': error, 'message': error, 'retryable': False}}
                     if error else {'payload': payload or {}})
        await self.send(frame)

    async def event(self, run_id, state, **values):
        run = self.runs[run_id]
        log(event='chat', run_id=run_id, state=state, **values)
        await self.send({'type': 'event', 'event': 'chat', 'seq': 1, 'payload': {
            'runId': run_id, 'sessionId': run['session'], 'seq': 1,
            'ts': int(time.time() * 1000), 'state': state, **values,
        }})

    async def execute(self, run_id, text):
        run = self.runs[run_id]
        try:
            # timeout_ms is optional in the BCN contract and BCS leaves it null
            # for state-machine tasks; a run that carries one is bounded by it.
            # wait_for only cancels; a graph that swallows the cancellation can
            # still return, so the deadline is checked again on the way out.
            result = await asyncio.wait_for(self.graph.ainvoke({
                'task': text, 'secret': run['secret'], 'answer': '',
                'attempts': 0, 'feedback': '',
            }), run['timeout'])
            if run['terminal']:
                return
            if run['deadline'] and asyncio.get_running_loop().time() >= run['deadline']:
                raise TimeoutError
            run['terminal'] = True
            self.secrets[run['session']] = run['secret']
            await self.event(run_id, 'final', content=result['answer'])
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not run['terminal']:
                run['terminal'] = True
                code = 'PLAYER_TIMEOUT' if isinstance(error, TimeoutError) else 'PLAYER_ERROR'
                await self.event(run_id, 'error', errorCode=code,
                                 errorMessage='Player execution failed')

    async def handle(self, request):
        if request.get('type') != 'req':
            return
        method, params = request.get('method'), request.get('params', {})
        if not isinstance(params, dict):
            return await self.reply(request, error='INVALID_REQUEST')
        if method == 'chat.abort':
            run_id = params.get('run_id')
            run = self.runs.get(run_id)
            if run is None:
                return await self.reply(request, error='RUN_NOT_FOUND')
            if params.get('session_key') != run['session']:
                return await self.reply(request, error='SCOPE_MISMATCH')
            if run['terminal']:
                return await self.reply(request, {'aborted': False, 'aborted_run_ids': []})
            run['terminal'] = True
            run['task'].cancel()
            await self.event(run_id, 'aborted', stopReason='aborted')
            return await self.reply(request, {'aborted': True, 'aborted_run_ids': [run_id]})
        if method in ('chat.send', 'chat.inject'):
            session = params.get('bcs_session_id')
            if not isinstance(session, str) or not session.strip() or params.get('session_key') != session:
                return await self.reply(request, error='INVALID_REQUEST')
            if method == 'chat.inject':
                return await self.reply(request)
            content = params.get('message', {}).get('content', [])
            if not isinstance(content, list) or any(not isinstance(item, dict) for item in content):
                return await self.reply(request, error='INVALID_REQUEST')
            text = '\n'.join(item['text'] for item in content
                             if item.get('type') == 'text' and isinstance(item.get('text'), str))
            if not text:
                return await self.reply(request, error='INVALID_REQUEST')
            # Same precedence as the reference adapter: upstream idempotency key,
            # then the request frame id, then a local id. A repeated key is ACKed
            # again without starting a second run.
            run_id = (str(params.get('idempotency_key') or '').strip()
                      or str(request.get('id') or '').strip() or str(uuid4()))
            if run_id in self.runs:
                if self.runs[run_id]['session'] != session:
                    return await self.reply(request, error='INVALID_REQUEST')
                return await self.reply(request, {'run_id': run_id})
            timeout_ms = params.get('timeout_ms')
            timeout = timeout_ms / 1000 if isinstance(timeout_ms, (int, float)) and timeout_ms > 0 else None
            deadline = asyncio.get_running_loop().time() + timeout if timeout else None
            self.runs[run_id] = {'session': session, 'terminal': False,
                                 'timeout': timeout, 'deadline': deadline,
                                 'secret': task_secret(text, self.secrets.get(session, ''))}
            node = re.search(r'node_id:\s*(\S+)', text)
            log(event='task', run_id=run_id, session=session,
                node=node.group(1) if node else None, chars=len(text))
            await self.reply(request, {'run_id': run_id})
            self.runs[run_id]['task'] = asyncio.create_task(self.execute(run_id, text))
            return
        if method == 'chat.history':
            return await self.reply(request, {'session_key': params.get('session_key'), 'messages': []})
        await self.reply(request, error='unknown_method')

    async def close(self):
        tasks = []
        for run in self.runs.values():
            run['terminal'] = True
            if 'task' in run:
                run['task'].cancel()
                tasks.append(run['task'])
        await asyncio.gather(*tasks, return_exceptions=True)
