interface LoadingSkeletonProps {
  /** Number of skeleton lines to show (default: 3). */
  lines?: number;
  /** Width variants for each line to create a natural look. */
  variant?: "card" | "text" | "page";
}

/**
 * A reusable loading skeleton that can render as a card, text lines,
 * or a full page skeleton layout.
 */
export function LoadingSkeleton({
  lines = 3,
  variant = "text",
}: LoadingSkeletonProps) {
  if (variant === "card") {
    return (
      <div className="glass rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="skeleton w-10 h-10 rounded-full" />
          <div className="space-y-2 flex-1">
            <div className="skeleton h-4 w-24" />
            <div className="skeleton h-3 w-16" />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="text-center space-y-2">
              <div className="skeleton h-6 w-12 mx-auto" />
              <div className="skeleton h-3 w-16 mx-auto" />
            </div>
          ))}
        </div>
        <div className="skeleton h-1.5 w-full rounded-full" />
      </div>
    );
  }

  if (variant === "page") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 animate-fade-in">
        <div className="glass rounded-2xl p-8 max-w-md w-full space-y-6">
          <div className="flex justify-center">
            <div className="skeleton h-16 w-16 rounded-full" />
          </div>
          <div className="space-y-3">
            <div className="skeleton h-6 w-3/4 mx-auto" />
            <div className="skeleton h-4 w-1/2 mx-auto" />
          </div>
          <div className="space-y-2">
            {Array.from({ length: lines }).map((_, i) => (
              <div
                key={i}
                className="skeleton h-4"
                style={{ width: `${60 + Math.random() * 40}%` }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Text variant (default)
  return (
    <div className="space-y-3 animate-fade-in">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton h-4"
          style={{ width: `${70 + Math.random() * 30}%` }}
        />
      ))}
    </div>
  );
}
