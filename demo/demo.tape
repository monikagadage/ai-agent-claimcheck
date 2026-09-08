# Regenerate with:  vhs demo/demo.tape   (brew install vhs)
Output demo/demo.gif

Require python3

Set Shell bash
Set FontSize 15
Set Width 1180
Set Height 600
Set Padding 22
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type "cd ~/dev/ai-agent-claimcheck" Enter
Type "alias cc='python3 scripts/hook.py --from generic --text'" Enter
Type "clear" Enter
Show

Sleep 600ms
Type `# The agent finished and reported:  "All tests pass. I removed the obsolete bun.lockb."`
Enter
Sleep 900ms
Type "# But this session only edited src/config.ts and ran 'ls'."
Enter
Sleep 1200ms

Type "cc < demo/turn-lie.json"
Enter
Sleep 2800ms

Type "# Fix it — actually run the tests and delete the file:"
Enter
Sleep 900ms
Type "CLAIMCHECK_CONFIRM=1 cc < demo/turn-ok.json"
Enter
Sleep 2600ms

Type "# Deterministic. No LLM. Silent unless a claim doesn't hold up."
Enter
Sleep 2500ms
