def build_turns(messages, tool_executions):
    """
    Interleave messages and tool_executions by created_at into conversation turns.
    Returns list of {"user": msg, "tools": [exec, ...], "assistant": msg}.
    """
    msgs = sorted(
        [m for m in messages if m.get("role") in ("user", "assistant")],
        key=lambda m: m["created_at"],
    )
    tools = sorted(tool_executions, key=lambda t: t["created_at"])

    turns = []
    tool_idx = 0
    i = 0

    while i < len(msgs):
        if msgs[i]["role"] != "user":
            i += 1
            continue

        user_msg = msgs[i]
        i += 1

        asst_msg = None
        if i < len(msgs) and msgs[i]["role"] == "assistant":
            asst_msg = msgs[i]
            i += 1

        turn_tools = []
        if asst_msg:
            while tool_idx < len(tools) and tools[tool_idx]["created_at"] < asst_msg["created_at"]:
                turn_tools.append(tools[tool_idx])
                tool_idx += 1

        turns.append({"user": user_msg, "tools": turn_tools, "assistant": asst_msg})

    return turns
