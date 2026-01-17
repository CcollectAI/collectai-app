from pathlib import Path
from datetime import datetime

ROOT = Path(".")
ID = ROOT / "app/users/[id].tsx"

def backup(p: Path):
    if not p.exists():
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    b = p.with_suffix(p.suffix + f".bak.{ts}")
    b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

def main():
    ID.parent.mkdir(parents=True, exist_ok=True)
    backup(ID)
    ID.write_text(
        """import React from "react";
import { Redirect, useLocalSearchParams } from "expo-router";

/**
 * Compatibility wrapper:
 * Some older links may go to /users/[id].
 * We redirect to /users/[userId] so you only maintain one real screen.
 */
export default function UserIdCompatRoute() {
  const params = useLocalSearchParams();
  const id = String((params as any)?.id ?? "");
  if (!id) return <Redirect href="/users/me" />;
  return <Redirect href={{ pathname: "/users/[userId]", params: { userId: id } }} />;
}
""",
        encoding="utf-8",
    )
    print(f"OK: wrote {ID}")

if __name__ == "__main__":
    main()
