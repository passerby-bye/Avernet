"""Run with explicit local endpoints and a private identity file."""
import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
from langchain_openai import ChatOpenAI
from websockets.asyncio.client import connect

from player import build_graph
from runtime import Runtime


async def main(args):
    identity = Path(args.identity)
    stored = json.loads(identity.read_text()) if identity.exists() else {}
    model = ChatOpenAI(model=os.environ['OPENCLAW_OPENAI_MODEL_ID'],
                       base_url=os.environ['OPENCLAW_OPENAI_BASE_URL'],
                       api_key=os.environ['OPENCLAW_OPENAI_API_KEY'],
                       timeout=60, max_retries=1)
    rules = Path(args.rules).read_text(encoding='utf-8')
    async with connect(args.ws_url, proxy=None) as ws:
        async def send(frame):
            await ws.send(json.dumps(frame, ensure_ascii=False))
        params = {'protocol_version': 3, 'client_kind': 'custom-engine'}
        if stored.get('token'):
            params['token'] = stored['token']
        await send({'type': 'req', 'id': 'connect', 'method': 'bot.connect', 'params': params})
        response = json.loads(await asyncio.wait_for(ws.recv(), 15))
        if not response.get('ok'):
            raise RuntimeError('BCN handshake rejected')
        payload = response['payload']
        capabilities = payload.get('capabilities', {})
        if payload.get('protocol_version') != 3 or not all(
                capabilities.get(key) for key in ('unified_run_events', 'canonical_session_id')):
            raise RuntimeError('Required BCN V3 capabilities missing')
        identity.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(identity, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump({key: payload[key] for key in ('token', 'bot_uuid')}, output)
        async with httpx.AsyncClient(trust_env=False) as client:
            onboard = await client.post(args.http_url.rstrip('/') + '/bots/onboard',
                headers={'Authorization': 'Bearer ' + payload['token']},
                json={'name': args.name, 'summary': 'LangGraph undercover player',
                      'skills': [], 'domains': ['undercover-game'], 'scopes': ['local']})
            onboard.raise_for_status()
        print('Player onboarded: ' + payload['bot_uuid'], flush=True)
        runtime = Runtime(build_graph(model, rules), send)
        try:
            async for raw in ws:
                await runtime.handle(json.loads(raw))
        finally:
            await runtime.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for flag in ('ws-url', 'http-url', 'identity', 'rules'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--name', default='LangGraph玩家')
    asyncio.run(main(parser.parse_args()))
