# Herdr 专家团

## 这个 Skill 解决什么问题

一项软件改动常常需要有人查清设计约束、有人实现、还有人用实际候选版本做独立验证。手动开多个 Agent 会话时，你得把背景和验收条件逐个发过去，再转发问题、汇总结果。启用这个 Skill 后，你可以只和一个主 Agent 对话。它根据需求在 Herdr Core 里开专家会话，有需要你决定的事项再集中向你汇报。

- **主 Agent** 对接用户，澄清目标和授权，选专家、派任务、核对结果。可以用你正在使用的会话承担这个角色，具体专业背景由任务决定。
- **专家 Agent** 各自交付设计意见、代码、测试证据等，技术问题可直接找同组专家。例如实现工程师可以问架构师一个兼容性问题，架构师可直接回复。
- **Herdr Core** 启动和保留交互终端，处理消息投递与终端读取。**Skill** 把这套协作约定教给主 Agent。**`Expert_Team.toml`** 定义有哪些专家、各自的职责、沟通规则、harness 和模型。

有独立评审价值、实现和验收适合分工，或需要多个模型给出不同判断时，适合开团。查一条日志、临时改个配置等小任务，可以继续让主 Agent 直接处理。每次按需求挑人，局部功能可以只请实现和测试，涉及公共接口时再请架构师。 [常用专家团示例](references/dev.md)

例如，要让解析器兼容缺失 `timeout` 的旧配置，主 Agent 可以先请架构师查旧版本行为和调用方。若继续沿用旧默认值与改用新默认值会产生不同兼容性结果，主 Agent 把影响和建议交给你决定。方案确认后，实现工程师在候选 worktree 改代码，测试工程师独立验证旧配置和新配置。测试发现问题时可直接把复现步骤交给实现工程师，同时向主 Agent 报告影响。你收到一份汇总，包括改动位置、验证结果和待决定事项。专家回报后继续待命，方便下一轮追问。

## 使用方式

1. 在运行主 Agent 的 harness 中，按该工具的说明自行注册 `herdr-team`。在实际运行专家的开发机或容器上准备 Herdr Core、Python 3.11+ 和角色所用的交互式 harness，再按下文同步模板。Core 启动的终端需要能找到这些 harness，专家也需要能执行 `hc`。
2. 在项目目录打开主 Agent，会话可以在普通终端或 Herdr 终端。普通终端通过 `hc wait` 和 `hc read` 收取结果。Herdr 终端有回报地址，专家可以直接把消息送进主会话。两种方式都能派工和支持专家互聊。
3. 显式调用 Skill，把需求直接写进去。Claude Code 使用 `/herdr-team`，Codex 使用 `$herdr-team`。

```text
/herdr-team 给 profile 解析器加缺失字段兼容，并验证旧格式
$herdr-team 先评估缓存改造的两种方案，汇报取舍，暂时只读
```

开发任务里，主 Agent 先挑人并说明方案，等你确认后再改代码或补测试。整项任务明确结束后，由你手动结束，或由主 Agent 收回本次专家会话。 [通用协作流程](references/setup.md) · [软件开发团示例](references/dev.md)

**Codex** 从 `agents/openai.yaml` 读取 `allow_implicit_invocation: false`。`$herdr-team` 仍然可用，Codex 的隐式选择关闭。删除该文件会恢复 Codex 默认允许隐式选择。 [Codex 配置说明](https://developers.openai.com/codex/skills/)

**Claude Code** 从 `SKILL.md` 读取 `disable-model-invocation: true`，正常注册 Skill 后即可用 `/herdr-team` 手动触发。`agents/claude-code.settings.json` 是可选的 `skillOverrides` 设置片段。要在 Claude Code 设置层声明同一策略，可把其中的 `herdr-team` 条目合并到项目的 `.claude/settings.local.json`，或显式用 `claude --settings /path/to/herdr-team/agents/claude-code.settings.json` 加载。 [Claude Code 调用控制](https://code.claude.com/docs/en/skills#control-who-invokes-a-skill) · [设置覆盖](https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings)

## 选择 harness 和模型

在 `[roles.<角色>]` 中编辑 `harness`、`model`、`access`、职责和初始提示。切换模型时，直接修改对应角色的 `model`，然后手动同步模板。省略 `model` 时使用该 harness 的默认模型。内置模板生成支持 Claude Code 和 Codex 作为专家，也支持它们通过现有网关使用第三方模型。Claude Code 可指定现有 `settings` 文件，Codex 可指定已有 `profile` 或 `provider`。凭证由原有 harness 配置管理。 [Expert_Team.toml](Expert_Team.toml) · [同步步骤](#同步或更新模板)

所有专家共享 `[worker].prompt` 中的原生 `hc` 通信、授权、汇报和待命约定。每个角色的 `prompt` 补充本职工作的边界和交付物。`access` 同时写进初始提示，Codex 模板还将它传给 `--sandbox`。Claude Code 的只读角色按提示词约定开展工作，实际工具权限沿用 Claude Code 的配置。若 harness 提示需要批准运行 `hc`，按它的授权流程处理。 [通信与回报](references/setup.md#交接与回报)

同一职责需要换 harness 或模型时，添加 `base = "<基座角色>"` 的变体，只写差异。例如 `[roles.architect-codex]` 复用架构师的职责和提示，改用 Codex 独立给一套方案，用于兼听。变体继承 `harness`、`access`、`model` 等运行参数；写了 `prompt` 时追加在基座之后；写了 `description` 或 `responsibility` 时覆盖基座。省略 `description` 时自动标注运行环境，例如「…（codex）」，在 `hc templates` 里能直接区分。同步后得到独立模板 `herdr-team-<基座>-<后缀>`，派工和 `--label herdr-team-role` 都用模板名。角色名有 32 字符上限，`herdr-team-` 已占 11 个，变体后缀建议不超过 8 个字符。

每个角色对应一个 `herdr-team-<角色>` 模板。新增角色时添加 `[roles.<角色>]` 并同步模板，主 Agent 即可按职责选用。派工用原生 `hc run`，Herdr 先用模板的 `command` 启动指定 harness，再把模板正文和本次任务一起发进交互会话。 [实际派工命令](references/setup.md#交接与回报)

## 同步或更新模板

首次使用、修改专家配置或升级 Skill 后，在每台实际运行专家的开发机或容器上，用运行 Core 的账号手动同步。Linux 和 macOS 默认路径为 `~/.config/herdr-core/templates/`，Windows 默认路径为 `%APPDATA%\herdr-core\templates`。如果设置了 `XDG_CONFIG_HOME`，模板位于其下的 `herdr-core/templates/`。模板的 `command` 由 `sh` 执行，Windows 上需要 `sh` 在 PATH，例如随 Git 安装的 shell。

```sh
cd /sandbox/skills/herdr-team
python3 scripts/sync_templates.py --check  # 查看哪些模板需要变更
python3 scripts/sync_templates.py          # 生成或更新模板
hc templates                              # 确认模板名和启动命令
```

第一步只预览差异。退出码 `0` 表示已同步，`2` 表示有变更可同步，`1` 表示处理错误，例如配置有误或模板同名。同步会清理本 Skill 生成且已废弃的模板。同名的自有模板会保留并报冲突。更新在下一次启动专家时生效。有自定义的旧版配置时，先确认已包含 `[worker]` 段，并把需要沿用的模型参数写进对应角色，再运行同步。

生成的是 Herdr 原生 `.md` 模板，文件名去掉扩展名就是 `hc run` 使用的名称。两行 `---` 之间是逐行读取的字段，`description` 用于列表展示，`command` 是经 `sh` 执行的交互式启动命令，包含模型参数。同步脚本用 `herdr-team-managed` 识别自己生成的文件，Herdr 会忽略该字段。正文依次包含共享约定、角色访问范围、职责和角色提示。

模板沿用 Herdr 默认的就绪检查，等待专家通过 OSC 7501 上报状态后才发送首条任务。运行专家的机器需要已有对应 harness 的状态上报配置。若任务没有送达，先用 `hc read` 查看终端是否有信任或权限提示，再检查状态上报。 [Herdr 官方模板规则](https://github.com/herdrdev/herdr-core/blob/master/docs/templates.md)

## 文件与脚本

| 文件 | 用途 |
| --- | --- |
| `SKILL.md` | 主 Agent 的通用工作流 |
| `Expert_Team.toml` | 共享专家提示与各角色的职责、提示、harness 和模型 |
| `references/setup.md` | 主 Agent 与专家的交接、通信、待命和回收约定 |
| `references/dev.md` | 常用专家团的搭配、多视角评审和工作流示例 |
| `scripts/sync_templates.py` | 由用户执行，检查和同步原生 Herdr 模板 |
| `scripts/team_config.py` | 校验 TOML 并生成模板的内部模块 |
| `agents/openai.yaml` | Codex 自动读取的调用策略，保留手动触发 |
| `agents/claude-code.settings.json` | 可显式加载或合并到现有设置的 Claude Code 调用策略 |
