# On Writing Well: an agent skill

A Cursor agent skill that teaches your AI assistant to write and edit like William Zinsser. It distills all four parts of *On Writing Well* into a workflow, a set of rules and references the agent can apply to anything you write, from essays to READMEs to incident emails.

Zinsser's four articles of faith are **clarity, simplicity, brevity and humanity**. The skill holds every draft to them.

## What's inside

```
skills/writing-well/
├── SKILL.md               The core: beliefs, a six-step workflow, sentence rules, voice, editing
├── principles.md          Part I: the transaction, simplicity, clutter, style, audience, words, usage
├── methods.md             Part II: unity, leads and endings, every "bits & pieces" rule, rewriting
├── forms.md               Part III: interviews, travel, memoir, science, business, sports, criticism, humor
├── attitudes.md           Part IV: voice, confidence, organizing long pieces, editors and standards
├── clutter-and-usage.md   Lookup tables: inflated phrases, jargon, clichés, usage distinctions
├── examples.md            Before-and-after rewrites, from the book and from everyday work
└── scripts/
    └── clutter_check.py   A clutter linter (Python 3, no dependencies)
```

The agent reads `SKILL.md` first and opens the other files only when it needs them, so the skill stays light in context.

## Install

**For all your projects** (user-level):

```bash
git clone https://github.com/<your-username>/on-writing-well.git
mkdir -p ~/.cursor/skills
cp -r on-writing-well/skills/writing-well ~/.cursor/skills/
```

**For one project:** copy `skills/writing-well` into that project's `.cursor/skills/` folder.

**From the zip:** unzip `writing-well-skill.zip` and move the `writing-well` folder into `~/.cursor/skills/` or a project's `.cursor/skills/`.

The skill follows the open Agent Skills format, so the same folder also works in other tools that read `SKILL.md` skills (for example, `~/.claude/skills/` for Claude Code).

## Use

In Cursor's agent chat, type `/writing-well` and then your request:

- `/writing-well tighten this README`
- `/writing-well edit my blog post draft in posts/launch.md and explain each change`
- `/writing-well write the incident email for yesterday's outage`

The skill runs only when you call it (`disable-model-invocation: true` in `SKILL.md`). If you want the agent to reach for it on its own whenever you're writing prose, delete that line.

## The clutter linter

`clutter_check.py` automates Zinsser's brackets. It flags inflated phrases, qualifiers, jargon, clichés, passives, concept nouns, long sentences and more, with a line number and a suggested fix for each:

```bash
python3 skills/writing-well/scripts/clutter_check.py draft.md
python3 skills/writing-well/scripts/clutter_check.py draft.md --json
cat draft.txt | python3 skills/writing-well/scripts/clutter_check.py -
```

```
draft.md:7: At this point in time we are basically on track due to the fact that...
  col   1  [inflated] "At this point in time" -> now
  col  30  [qualifier] "basically" -> cut
  col  49  [inflated] "due to the fact that" -> because
```

It skips front matter, code blocks, inline code and URLs. *On Writing Well* itself scores about 1.3 flags per 100 words. Treat each flag as a bracket, not a verdict: read the sentence without the flagged words and decide.

## Working on this repo

`.cursor/skills/writing-well` is a symlink to `skills/writing-well`, so the skill is live as a project skill when you open this repo in Cursor. Edit the files under `skills/`.

## Credit

The skill summarizes and briefly quotes William Zinsser's *On Writing Well* (25th anniversary edition) for teaching purposes. It isn't a substitute for the book, which is a pleasure to read. Buy a copy. This project isn't affiliated with the author's estate or publisher.
