# agent-skills

riko-yyy の自作 Agent Skill 集。

## Skills

| Skill | 用途 |
|---|---|
| [element-relation-protocol](skills/element-relation-protocol/SKILL.md) | コードや設計書から「要素・関係・プロトコル」でメンタルモデルを掴む。図(SVG)＋説明を出力 |

## 使い方

### Claude Code（プラグインとして）

```
/plugin marketplace add riko-yyy/agent-skills
/plugin install agent-skills@riko-yyy
```

### claude.ai

`skills/<name>/` フォルダを zip にして、設定の Skills からアップロードする。

## License

MIT
