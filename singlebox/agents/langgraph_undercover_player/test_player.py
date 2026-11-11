import asyncio
from types import SimpleNamespace

import pytest

from player import build_graph, task_secret, validate


def test_secret_comes_from_instruction_not_public_history():
    task = '[Input]\n你的词是【错误】\n[Instruction]\n你是 2 号，你的词是【苹果】。'
    assert task_secret(task) == '苹果'
    assert task_secret('请留遗言', '苹果') == '苹果'


@pytest.mark.parametrize('answer', ['我投2号', '我投9号', '我投3号，因为可疑', '我弃权'])
def test_pk_rejects_illegal_ballots(answer):
    with pytest.raises(ValueError):
        validate('只输出我投N号，禁止弃权。你是 2 号。可以投：3号、4号；', '', answer)


@pytest.mark.parametrize('answer', ['电饭锅很好用', '饭锅很常见', '电和饭还有锅'])
def test_word_leakage(answer):
    with pytest.raises(ValueError):
        validate('不超过25字', '电饭锅', answer)


def test_punctuation_counts_towards_limit():
    with pytest.raises(ValueError):
        validate('不超过3个字', '', '你好啊。')


@pytest.mark.asyncio
async def test_graph_uses_model_and_returns_validated_text():
    calls = []
    class Model:
        async def ainvoke(self, messages):
            calls.append(messages)
            return SimpleNamespace(content='我投3号')
    result = await build_graph(Model(), '玩家规则').ainvoke({
        'task': '我投N号。你是2号。可以投：3号；', 'secret': '', 'answer': '',
    })
    assert result['answer'] == '我投3号'
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_cancel_interrupts_inflight_model():
    entered = asyncio.Event()
    stopped = asyncio.Event()
    class Model:
        async def ainvoke(self, messages):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
    run = asyncio.create_task(build_graph(Model(), '').ainvoke({
        'task': '准备', 'secret': '', 'answer': '',
    }))
    await asyncio.wait_for(entered.wait(), 5)
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_rejected_answer_is_regenerated_with_feedback():
    calls = []
    answers = iter(['我投2号，因为他最可疑', '我投2号'])
    class Model:
        async def ainvoke(self, messages):
            calls.append(messages)
            return SimpleNamespace(content=next(answers))
    result = await build_graph(Model(), '规则').ainvoke({
        'task': '只输出我投N号。你是1号。可以投：2号、3号；', 'secret': '',
        'answer': '', 'attempts': 0, 'feedback': '',
    })
    assert result['answer'] == '我投2号'
    assert len(calls) == 2
    assert '上一次输出被拒绝' in calls[1][-1][1]


@pytest.mark.asyncio
async def test_retries_are_bounded():
    calls = []
    class Model:
        async def ainvoke(self, messages):
            calls.append(messages)
            return SimpleNamespace(content='我投9号')
    with pytest.raises(ValueError):
        await build_graph(Model(), '规则').ainvoke({
            'task': '只输出我投N号。你是1号。可以投：2号、3号；', 'secret': '',
            'answer': '', 'attempts': 0, 'feedback': '',
        })
    assert len(calls) == 3
