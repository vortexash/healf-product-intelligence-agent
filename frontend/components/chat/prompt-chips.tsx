export function PromptChips({ prompts, onPick }: { prompts: string[]; onPick: (p: string) => void }) {
  if (!prompts.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {prompts.map((p) => (
        <button
          key={p}
          onClick={() => onPick(p)}
          className="rounded-full border border-line bg-card px-3 py-1.5 text-sm text-ink transition-colors hover:border-healf-ring hover:bg-healf-soft"
        >
          {p}
        </button>
      ))}
    </div>
  );
}
