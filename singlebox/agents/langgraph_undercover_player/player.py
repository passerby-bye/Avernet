"""Task-local LangGraph execution for an undercover player.

The transport supplies only the context visible to this player. It must discard
results for cancelled runs before updating session memory or sending artifacts.
"""
import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

MAX_ATTEMPTS = 3


class PlayerState(TypedDict):
    task: str
    secret: str
    answer: str
    attempts: int
    feedback: str


def instruction(task: str) -> str:
    return task.rsplit('[Instruction]\n', 1)[-1]


def task_secret(task: str, previous: str = '') -> str:
    match = re.search(r'(?:你的词是|词是)【([^】]+)】', instruction(task))
    return match.group(1) if match else previous


def validate(task: str, secret: str, answer: str) -> None:
    """Reject invalid output; never silently truncate or invent a vote."""
    rules = instruction(task)
    if not answer or '\n' in answer:
        raise ValueError('Expected one nonempty line')
    limit = re.search(r'不超过\s*(\d+)\s*(?:个)?字', rules)
    if limit and len(answer) > int(limit.group(1)):
        raise ValueError('Output exceeds task character limit')
    if secret and (secret in answer
                   or any(secret[i:i + 2] in answer for i in range(len(secret) - 1))
                   or all(char in answer for char in secret)):
        raise ValueError('Output reveals private word')
    if '我投N号' in rules:
        if answer == '我弃权':
            if '禁止弃权' in rules or '不能弃权' in rules:
                raise ValueError('Abstention forbidden')
            return
        vote = re.fullmatch(r'我投([1-9][0-9]*)号', answer)
        if not vote:
            raise ValueError('Invalid ballot format')
        candidates = re.search(r'可以投：([^；\n]+)', rules)
        if candidates and vote.group(1) not in re.findall(r'\d+', candidates.group(1)):
            raise ValueError('Target outside allowed candidates')
        own = re.search(r'你是\s*(\d+)\s*号', rules)
        if own and vote.group(1) == own.group(1):
            raise ValueError('Self vote forbidden')


def build_graph(model, player_rules: str):
    """Inject an async chat model; no network or configuration at import time.

    generate -> validate; a rejected answer is regenerated together with the
    rejection reason, at most MAX_ATTEMPTS times, then the last error propagates.
    """
    async def generate(state: PlayerState):
        messages = [('system', player_rules), ('human', state['task'])]
        if state.get('feedback'):
            messages += [('ai', state['answer']),
                         ('human', '上一次输出被拒绝：' + state['feedback']
                          + '。请严格按任务要求重新输出，只输出那一句。')]
        result = await model.ainvoke(messages)
        if not isinstance(result.content, str):
            raise ValueError('Expected text model output')
        return {'answer': result.content.strip(),
                'attempts': state.get('attempts', 0) + 1, 'feedback': ''}

    def check(state: PlayerState):
        try:
            validate(state['task'], state['secret'], state['answer'])
        except ValueError as error:
            if state['attempts'] >= MAX_ATTEMPTS:
                raise
            return {'feedback': str(error)}
        return {}

    def route(state: PlayerState):
        return 'generate' if state.get('feedback') else END

    graph = StateGraph(PlayerState)
    graph.add_node('generate', generate)
    graph.add_node('validate', check)
    graph.add_edge(START, 'generate')
    graph.add_edge('generate', 'validate')
    graph.add_conditional_edges('validate', route, ['generate', END])
    return graph.compile()
