"""
Read-only diagnostics for the Jaumo admin bot. Changes nothing.

Run it from the project root (same place the server runs), so it uses the same STORAGE_DIR:
    python -m tools.diagnose

It prints:
  - account counts by status,
  - the "blocked" accounts split into verification (code 4031), the ~daily like-limit, and real blocks,
  - the most common failure reasons across recent sessions,
  - the last error line of the latest failed/blocked session per affected account.
"""
from collections import Counter

from sqlmodel import Session, select

from api.models import Account, BotRun, RunLog, engine


def main():
    with Session(engine) as s:
        accounts = s.exec(select(Account)).all()
        print(f"\n=== Accounts: {len(accounts)} total ===")
        by_status = Counter(a.status for a in accounts)
        for st, n in by_status.most_common():
            print(f"  {st:24} {n}")

        # blocked accounts: why?
        blocked = [a for a in accounts if a.status == "blocked"]
        print(f"\n=== 'blocked' accounts: {len(blocked)} — what really happened ===")
        groups = Counter()
        rows = []
        for a in blocked:
            last = s.exec(select(BotRun).where(BotRun.account_id == a.id, BotRun.kind != "sync",
                                               BotRun.status == "blocked").order_by(BotRun.id.desc())).first()
            reason = (last.reason if last else "") or a.verify_info or ""
            likes = a.liked_count or 0
            low = reason.lower()
            if "verification" in low or "4031" in reason:
                kind = "verification required (should be relabelled)"
            elif "term" in low or "violation" in low or "ban" in low:
                kind = "real block — terms/violation (permanent)"
            else:
                kind = f"stopped after ~{likes} likes — reason unconfirmed (check the session log body)"
            groups[kind] += 1
            rows.append((a.id, a.name, likes, kind, reason[:90]))
        for kind, n in groups.most_common():
            print(f"  {n:3}  {kind}")
        if rows:
            print("\n  id   name                 likes  category / reason")
            for aid, name, likes, kind, reason in sorted(rows, key=lambda r: -r[2]):
                print(f"  #{aid:<4} {str(name)[:18]:18} {likes:6}  {kind}")

        # recent sessions: failure reasons
        recent = s.exec(select(BotRun).where(BotRun.status.in_(("blocked", "failed")))
                        .order_by(BotRun.id.desc()).limit(300)).all()
        print(f"\n=== Failure reasons in the last {len(recent)} failed/blocked sessions ===")
        for reason, n in Counter((r.reason or "?")[:80] for r in recent).most_common(15):
            print(f"  {n:4}  {reason}")

        # photos rejected
        from api.models import Photo
        rej = s.exec(select(Photo).where(Photo.rejected_reason != "")).all()
        if rej:
            print(f"\n=== Rejected photos: {len(rej)} ===")
            for p in rej[:15]:
                print(f"  {p.filename}  — {p.rejected_reason[:80]}")

        # last error log line per recently failed account (where did it stop?)
        print("\n=== Last error line of the newest failed/blocked session (up to 15 accounts) ===")
        seen = set()
        for r in recent:
            if r.account_id in seen or len(seen) >= 15:
                continue
            seen.add(r.account_id)
            err = s.exec(select(RunLog).where(RunLog.run_id == r.id, RunLog.level.in_(("error", "warning")))
                         .order_by(RunLog.id.desc())).first()
            line = (err.msg.splitlines()[0] if err and err.msg else r.reason or "")[:120]
            print(f"  #{r.account_id} (session {r.id}, {r.status}): {line}")
    print()


if __name__ == "__main__":
    main()
