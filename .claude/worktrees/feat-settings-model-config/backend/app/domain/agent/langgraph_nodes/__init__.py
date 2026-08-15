"""v0.8 LangGraph 自定义 node 集合.

子模块契约(spec §4.2):每个 node 是 Callable[[AgentState, Runtime], dict],
返回值会与 AgentState 自动合并(LangGraph TypedDict reducer 行为)。
"""
