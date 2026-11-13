# claude-skills

riko-yyy の自作 Claude Skill 集。

## Skills

| Skill | 用途 |
|---|---|
| [element-relation-protocol](skills/element-relation-protocol/SKILL.md) | コードや設計書から「要素・関係・プロトコル」でメンタルモデルを掴む。図(SVG)＋説明を出力 |

## 使い方

### Claude Code（プラグインとして）

```
/plugin marketplace add riko-yyy/claude-skills
/plugin install riko-skills@riko-skills
```

### claude.ai

`skills/<name>/` フォルダを zip にして、設定の Skills からアップロードする。
