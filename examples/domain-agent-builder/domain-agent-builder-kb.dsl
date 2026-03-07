RULESET agent_construction_patterns
VERSION 1.0
SOURCE "Learn Claude Code - Anthropic 2026"

RULE s01 "One loop & Bash is all you need"
  DESCRIPTION "one tool + one loop = an agent"
  REQUIRES nothing
  PATTERN
    User --> messages[] --> LLM --> response
    IF stop_reason == "tool_use" THEN execute_tools AND loop_back
    ELSE return text
  END

RULE s02 "Adding a tool means adding one handler"
  DESCRIPTION "the loop stays the same; new tools register into the dispatch map"
  REQUIRES s01
  PATTERN
    tools = {name: handler_fn}
    dispatch(tool_name) --> tools[tool_name](input)
  END

RULE s03 "An agent without a plan drifts"
  DESCRIPTION "list the steps first, then execute; completion doubles"
  REQUIRES s01
  PATTERN
    plan = LLM.generate_plan(goal)
    FOR step IN plan DO execute(step)
  END

RULE s04 "Break big tasks down; each subtask gets a clean context"
  DESCRIPTION "subagents use independent messages[], keeping main conversation clean"
  REQUIRES s01, s03
  PATTERN
    subtasks = decompose(task)
    FOR subtask IN subtasks DO
      sub_messages = new_context()
      result = run_agent(sub_messages, subtask)
    END
  END

RULE s05 "Load knowledge when you need it, not upfront"
  DESCRIPTION "inject via tool_result, not the system prompt"
  REQUIRES s01, s02
  PATTERN
    ON tool_call("read_file", path) DO
      content = read(path)
      inject_as_tool_result(content)
  END

RULE s06 "Context will fill up; you need a way to make room"
  DESCRIPTION "three-layer compression strategy for infinite sessions"
  REQUIRES s01, s05
  PATTERN
    IF context_tokens > threshold THEN
      layer1: summarize_old_messages
      layer2: compress_to_key_facts
      layer3: archive_to_disk
  END

RULE s07 "Break big goals into small tasks, order them, persist to disk"
  DESCRIPTION "file-based task graph with dependencies for multi-agent collaboration"
  REQUIRES s03, s04
  PATTERN
    task_graph = {id, description, depends_on[], status}
    persist(task_graph, "tasks.json")
    execute_in_dependency_order(task_graph)
  END

RULE s08 "Run slow operations in the background; the agent keeps thinking"
  DESCRIPTION "daemon threads run commands, inject notifications on completion"
  REQUIRES s01, s02
  PATTERN
    thread = daemon(execute_command, cmd)
    ON thread.complete DO inject_notification(result)
    agent.continue_thinking()
  END

RULE s09 "When the task is too big for one, delegate to teammates"
  DESCRIPTION "persistent teammates + async mailboxes"
  REQUIRES s04, s07
  PATTERN
    teammates = [Agent(role) for role in roles]
    FOR task IN unassigned DO
      mailbox[best_teammate(task)].send(task)
    END
  END

RULE s10 "Teammates need shared communication rules"
  DESCRIPTION "one request-response pattern drives all negotiation"
  REQUIRES s09
  PATTERN
    protocol = {request: task, response: result, status: enum}
    all_communication CONFORMS_TO protocol
  END

RULE s11 "Teammates scan the board and claim tasks themselves"
  DESCRIPTION "no need for the lead to assign each one"
  REQUIRES s09, s10
  PATTERN
    EACH teammate DO
      unclaimed = board.filter(status="open", fits=self.skills)
      IF unclaimed THEN claim(unclaimed[0])
  END

RULE s12 "Each works in its own directory, no interference"
  DESCRIPTION "tasks manage goals, worktrees manage directories, bound by ID"
  REQUIRES s11
  PATTERN
    workspace = create_worktree(task.id)
    agent.execute_in(workspace)
    ON complete DO merge(workspace)
  END

END RULESET
