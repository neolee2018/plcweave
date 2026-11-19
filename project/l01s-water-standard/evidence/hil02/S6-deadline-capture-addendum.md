# Independent deadline capture strategy addendum

This addendum changes only D120 evidence capture for a future run02. All original S1 expectations, the frozen 28 supplemental procedures and every existing tolerance remain unchanged. Preserve run01 and its independent review without modification.

Starting at the existing near-deadline anchor (earliest trigger request + 50,050 ms), repeatedly read the single D120 word. After each read, require the latest two complete, chronological, nonoverlapping observations to equal 30000 and end no later than earliest trigger request + 50,200 ms. Stop on that qualified pair or the hard deadline. A bounded in-flight read crossing the deadline is recorded but cannot qualify. Never borrow effective-trigger read latency or select an older pair.

Missing or changing samples and an early 29940 value remain UNVERIFIED; communication errors remain infrastructure errors. No post-deadline plateau observation replaces the deadline assertion. The original 55 cases remain a capability-only UNVERIFIED audit.

Five independent deterministic fake-clock/transport fixtures were run before implementation: current code is RED (one failed, four passed), because it reads only twice and misses an available third complete cap observation. No serial connection or PLC source was used.
