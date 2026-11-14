# agent-skills

riko-yyy の自作 Agent Skill 集。

## Skills

| Skill | 用途 |
|---|---|
| [element-relation-protocol](skills/element-relation-protocol/SKILL.md) | コード・plugin・文書群などを「要素(実行主体とリソース)・関連・プロトコル」に分解してメンタルモデルを掴む。図(SVG)＋説明を出力 |

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
